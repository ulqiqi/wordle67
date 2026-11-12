#!/usr/bin/env python3
"""wordle67.py - find Wordle guesses that draw '67' on the grid."""
import argparse
import itertools
import re
import sys
from collections import Counter

# Shape from the picture: 6 = the "6", 7 = the "7", 0 = background
SHAPE = [
    "66600",
    "60777",
    "66607",
    "60607",
    "66607",
    "00007",
]

COLOR_ALIASES = {
    "g": "G", "green": "G",
    "y": "Y", "yellow": "Y",
    "b": "B", "grey": "B", "gray": "B", "black": "B",
}
COLOR_NAMES = {"G": "green", "Y": "yellow", "B": "grey"}
EMOJI = {"G": "G", "Y": "Y", "B": "."}


def color(value):
    key = value.strip().lower()
    if key not in COLOR_ALIASES:
        raise argparse.ArgumentTypeError(
            f"invalid colour '{value}' (use green/g, yellow/y, grey/gray/b)")
    return COLOR_ALIASES[key]


def score(guess, target):
    res = ["B"] * 5
    left = Counter()
    for i in range(5):
        if guess[i] == target[i]:
            res[i] = "G"
        else:
            left[target[i]] += 1
    for i in range(5):
        if res[i] != "G" and left[guess[i]] > 0:
            res[i] = "Y"
            left[guess[i]] -= 1
    return "".join(res)


def build_rows(c6, c7, bg):
    m = {"6": c6, "7": c7, "0": bg}
    return ["".join(m[ch] for ch in row) for row in SHAPE]


def load(path):
    try:
        with open(path) as f:
            return [w.strip().lower() for w in f if re.fullmatch(r"[a-zA-Z]{5}", w.strip())]
    except OSError as e:
        sys.exit(f"error: cannot read word list '{path}': {e.strerror}")


def main():
    ap = argparse.ArgumentParser(description="Draw '67' on a Wordle grid.")
    ap.add_argument("-w", "--word", required=True, help="the answer (target word)")
    ap.add_argument("-c6", "--c6", type=color, help="colour of the 6")
    ap.add_argument("-c7", "--c7", type=color, help="colour of the 7")
    ap.add_argument("-bg", "--bg", type=color, help="colour of the background")
    ap.add_argument("-l", "--list", default="words.txt", help="valid guesses file")
    args = ap.parse_args()

    target = args.word.strip().lower()
    if not re.fullmatch(r"[a-z]{5}", target):
        ap.error(f"'{args.word}' is not a 5-letter word")

    fixed = {"6": args.c6, "7": args.c7, "background": args.bg}
    given = {k: v for k, v in fixed.items() if v}
    if len(set(given.values())) < len(given):
        dup = [k for k, v in given.items() if list(given.values()).count(v) > 1]
        ap.error(f"{' and '.join(dup)} can't share the same colour")

    combos = [p for p in itertools.permutations("GYB")
              if all(v is None or v == p[i]
                     for i, v in enumerate((args.c6, args.c7, args.bg)))]

    words = load(args.list)
    if not words:
        sys.exit(f"error: no 5-letter words found in '{args.list}'")
    if target not in words:
        print(f"warning: '{target}' is not in the word list", file=sys.stderr)

    # One pass: first guess producing each pattern against the target
    first = {}
    for w in words:
        first.setdefault(score(w, target), w)

    for c6, c7, bg in combos:
        rows = build_rows(c6, c7, bg)
        print(f"\n6 = {COLOR_NAMES[c6]}, 7 = {COLOR_NAMES[c7]}, "
              f"background = {COLOR_NAMES[bg]}")
        missing = [i for i, p in enumerate(rows, 1) if p not in first]
        if missing:
            rows_txt = ", ".join(f"row {i} ({''.join(EMOJI[c] for c in rows[i-1])})"
                                 for i in missing)
            print(f"  impossible: no guess for {rows_txt}")
            continue
        for i, p in enumerate(rows, 1):
            print(f"  {i} : {first[p]}   {''.join(EMOJI[c] for c in p)}")


if __name__ == "__main__":
    main()