![wordle67](header.png)

# wordle67

Give it a Wordle answer and it finds 6 guesses that draw **67** on the grid.

## Usage

```bash
python3 wordle67.py -w <word> [options]
```

| Flag | Description |
|------|-------------|
| `-w`, `--word` | The answer / target word (required) |
| `-c6`, `--c6` | Colour of the 6 |
| `-c7`, `--c7` | Colour of the 7 |
| `-bg`, `--bg` | Colour of the background |
| `-l`, `--list` | Word list file (default: `words.txt`) |

Colours: `green`/`g`, `yellow`/`y`, `grey`/`gray`/`b`. The 6, the 7 and the background each need a different colour.

If you don't set a colour, the script tries every possible combination and shows each one that works.

### Examples

```bash
python3 wordle67.py -w crane
python3 wordle67.py -w crane -c6 yellow -c7 green -bg grey
```

## Word list

The list of valid guesses comes from [tabatkins/wordle-list](https://github.com/tabatkins/wordle-list). To download it:

```bash
curl -o words.txt https://raw.githubusercontent.com/tabatkins/wordle-list/main/words
```

## Credits

The idea came from a Twitter post, which led me to [this Reddit post](https://www.reddit.com/r/wordle/comments/1uxk3hi/67/).
