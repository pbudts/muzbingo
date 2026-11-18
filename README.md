# MuzBingo

Create **music bingo** cards from a playlist. The host plays songs; players mark the
matching artist + title on their card. MuzBingo imports a Spotify CSV export or an
Excel sheet, generates randomized cards (e.g. 4×5 or 5×5), saves the game, and prints
the cards to PDF from an editable HTML template.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and roadmap.

## Status

Phase 1 (core + command-line tool) is in progress. The desktop GUI comes in phase 2.

## Setup (development)

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

On Debian/Ubuntu, `python3 -m venv` needs the `python3-venv` package
(`sudo apt install python3.12-venv`).

## Command-line use

```bash
# Show which songs a playlist file contains (and which columns were detected)
muzbingo inspect playlist.csv

# Create a game: 40 cards of 4 rows × 5 columns, Dutch labels, event date
muzbingo new playlist.csv --title "Kerstfeest 2026" --grid 4x5 --cards 40 \
    --date 2026-12-19 --language nl --logo our-logo.png -o kerstfeest.muzbingo

# Print the cards (one A4 page per card)
muzbingo pdf kerstfeest.muzbingo -o kerstfeest.pdf

# Or write HTML, to work on a template in a browser
muzbingo pdf kerstfeest.muzbingo --html -o kerstfeest.html
```

If the title/artist columns aren't detected automatically, pick them with
`--title-col` and `--artist-col`.

## Card templates

Templates live in `src/muzbingo/templates/<name>/`:

- `template.toml`: page size, labels per language, date format, default pictures
- `cards.html.j2`: the Jinja2 HTML
- `style.css`: layout and colours; the variables at the top move or restyle elements

To make your own, copy the `classic` folder into the user templates folder:
- Linux: `~/.local/share/MuzBingo/templates/`
- Windows: `%APPDATA%\MuzBingo\templates\`
- Portable app: `data/templates/` next to the program

Give the folder a new name and edit it. `muzbingo templates` lists what's available.
