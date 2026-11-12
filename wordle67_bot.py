#!/usr/bin/env python3
"""wordle67_bot.py - daily Discord bot for wordle67.

Every run:
  1. gets today's Wordle answer (Paris date) from the NYT API
  2. runs the wordle67 solver on it for every colour combination
  3. posts to Discord only if at least one combination works
On Sundays it also posts a health report (API status + last 7 days of runs),
so silence on a Sunday means the bot itself is broken.

Config (environment variables):
  DISCORD_WEBHOOK_URL   required, the channel's webhook URL
  WORDLE67_WORDS        word list path      (default: words.txt next to this file)
  WORDLE67_STATE        run history file    (default: state.json next to this file)
"""
import argparse
import datetime as dt
import itertools
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wordle67  # noqa: E402  (the solver, unchanged)

TZ = ZoneInfo("Europe/Paris")
API_URL = "https://www.nytimes.com/svc/wordle/v2/{date}.json"
USER_AGENT = "wordle67-bot/1.0 (+https://github.com/)"
HEARTBEAT_WEEKDAY = 6          # 0 = Monday ... 6 = Sunday
SPOILERS = True                # hide the words behind Discord ||spoiler|| tags
API_RETRIES = 3
API_RETRY_DELAY = 60           # seconds between API retries
DISCORD_LIMIT = 2000           # max characters per Discord message
SQUARES = {"G": "🟩", "Y": "🟨", "B": "⬛"}

WORDS = Path(os.environ.get("WORDLE67_WORDS", HERE / "words.txt"))
STATE = Path(os.environ.get("WORDLE67_STATE", HERE / "state.json"))


# ---------------------------------------------------------------- helpers
def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch_answer(date):
    """Return (wordle_number, answer) for a date, retrying on failure."""
    last = None
    for attempt in range(1, API_RETRIES + 1):
        try:
            data = http_get_json(API_URL.format(date=date.isoformat()))
            word = str(data["solution"]).strip().lower()
            if len(word) != 5 or not word.isalpha():
                raise ValueError(f"unexpected solution {word!r}")
            return data.get("days_since_launch"), word
        except Exception as e:  # network error, bad JSON, missing field...
            last = e
            print(f"API attempt {attempt}/{API_RETRIES} failed: {e}", file=sys.stderr)
            if attempt < API_RETRIES:
                time.sleep(API_RETRY_DELAY)
    raise RuntimeError(f"Wordle API failed after {API_RETRIES} tries: {last}")


def solve(target, words):
    """Return [(c6, c7, bg, [(guess, pattern) x6]), ...] for every working combo."""
    first = {}
    for w in words:
        first.setdefault(wordle67.score(w, target), w)
    found = []
    for c6, c7, bg in itertools.permutations("GYB"):
        rows = wordle67.build_rows(c6, c7, bg)
        if all(p in first for p in rows):
            found.append((c6, c7, bg, [(first[p], p) for p in rows]))
    return found


def post_discord(webhook, text, dry_run=False):
    """Send text to Discord, split into <=2000-char messages on blank lines."""
    chunks, cur = [], ""
    for block in text.split("\n\n"):
        cand = f"{cur}\n\n{block}" if cur else block
        if len(cand) > DISCORD_LIMIT and cur:
            chunks.append(cur)
            cand = block
        cur = cand
    chunks.append(cur)

    for chunk in chunks:
        if dry_run:
            print("----- discord message -----\n" + chunk)
            continue
        body = json.dumps({"content": chunk[:DISCORD_LIMIT]}).encode()
        req = urllib.request.Request(webhook, data=body, method="POST", headers={
            "Content-Type": "application/json", "User-Agent": USER_AGENT})
        for attempt in range(3):
            try:
                urllib.request.urlopen(req, timeout=20).close()
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 2:      # rate limited
                    time.sleep(float(e.headers.get("Retry-After", 2)))
                    continue
                raise
        time.sleep(1)


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {"runs": []}


def save_state(state):
    state["runs"] = state["runs"][-60:]
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)


def spoil(s):
    return f"||{s}||" if SPOILERS else s


# --------------------------------------------------------------- messages
def answers_message(number, date, target, found):
    n = len(found)
    head = (f"**Wordle {'#' + str(number) if number else ''} ({date:%d/%m/%Y}) - "
            f"67 is possible!** {n} colour combination{'s' if n > 1 else ''} "
            f"work{'' if n > 1 else 's'}. Answer: {spoil(target.upper())}")
    blocks = [head]
    for c6, c7, bg, rows in found:
        lines = [f"6 = {wordle67.COLOR_NAMES[c6]}, 7 = {wordle67.COLOR_NAMES[c7]}, "
                 f"background = {wordle67.COLOR_NAMES[bg]}"]
        for i, (guess, pat) in enumerate(rows, 1):
            lines.append(f"{''.join(SQUARES[c] for c in pat)}  {i}. {spoil(guess.upper())}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def heartbeat_message(today, today_run, runs):
    by_date = {r["date"]: r for r in runs}
    first_run = min(dt.date.fromisoformat(d) for d in by_date)  # ignore pre-install days
    week = [d for d in (today - dt.timedelta(days=i) for i in range(6, -1, -1))
            if d >= first_run]
    ok = [d for d in week if by_date.get(d.isoformat(), {}).get("status") == "ok"]
    failed = [d for d in week if by_date.get(d.isoformat(), {}).get("status") == "error"]
    missed = [d for d in week if d.isoformat() not in by_date]
    hits = [d for d in ok if by_date[d.isoformat()].get("combos", 0) > 0]

    fmt = lambda ds: ", ".join(f"{d:%a %d/%m}" for d in ds)
    all_good = today_run["status"] == "ok" and not failed and not missed
    lines = [f"{'✅' if all_good else '⚠️'} **wordle67 weekly check ({today:%d/%m/%Y})**"]
    if today_run["status"] == "ok":
        lines.append(f"• Wordle API: working (today's answer fetched)")
        lines.append(f"• Word list: {today_run['words']} words loaded")
    else:
        lines.append(f"• ❌ Today's run failed: {today_run['error']}")
    lines.append(f"• Last {len(week)} days: {len(ok)}/{len(week)} runs OK")
    if failed:
        lines.append(f"• ❌ Failed runs: {fmt(failed)}")
    if missed:
        lines.append(f"• ⚠️ Missing runs (bot/server didn't run): {fmt(missed)}")
    lines.append(f"• Days with a 67: {fmt(hits) if hits else 'none this week'}")
    return "\n".join(lines)


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Daily wordle67 Discord bot.")
    ap.add_argument("--date", help="run for this date (YYYY-MM-DD) instead of today")
    ap.add_argument("--heartbeat", action="store_true",
                    help="send the weekly check now, whatever the day")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the messages instead of sending them")
    args = ap.parse_args()

    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook and not args.dry_run:
        sys.exit("error: set DISCORD_WEBHOOK_URL (or use --dry-run)")

    today = (dt.date.fromisoformat(args.date) if args.date
             else dt.datetime.now(TZ).date())
    run = {"date": today.isoformat(),
           "time": dt.datetime.now(TZ).isoformat(timespec="seconds")}
    message = None

    try:
        number, target = fetch_answer(today)
        try:
            words = wordle67.load(str(WORDS))
        except SystemExit as e:         # wordle67.load exits on a missing file
            raise RuntimeError(str(e)) from None
        if not words:
            raise RuntimeError(f"no 5-letter words in {WORDS}")
        found = solve(target, words)
        run.update(status="ok", number=number, words=len(words), combos=len(found))
        if found:
            message = answers_message(number, today, target, found)
    except Exception as e:
        traceback.print_exc()
        run.update(status="error", error=str(e))

    state = load_state()
    state["runs"] = [r for r in state["runs"] if r["date"] != run["date"]] + [run]
    save_state(state)

    send = lambda text: post_discord(webhook, text, args.dry_run)
    if message:
        send(message)
    elif run["status"] == "error":
        send(f"❌ **wordle67 bot error ({today:%d/%m/%Y})**: {run['error']}")
    else:
        print(f"{today}: no 67 possible today, nothing sent")

    if args.heartbeat or today.weekday() == HEARTBEAT_WEEKDAY:
        send(heartbeat_message(today, run, state["runs"]))

    return 0 if run["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
