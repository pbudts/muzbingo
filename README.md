# MuzBingo

Create **music bingo** cards from a playlist. The host plays songs; players mark the
matching artist + title on their card. MuzBingo imports a Spotify CSV export or an
Excel sheet, generates randomized cards (e.g. 4×5 or 5×5), saves the game, and prints
the cards to PDF from an editable HTML template.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and roadmap.

## Status

- Phase 1 (core + command-line tool): done.
- Phase 2 (web UI): first version done. It covers the "My games" library, game settings,
  the playlist editor, card generation, card preview and PDF download. It runs in a
  browser with `muzbingo serve`. The app window for end-users follows in phase 5.
- Phase 3 (polish): done. Undo/redo, "Shorten titles" (removes "Remastered",
  "feat. …" and the like), automatic downscaling of large pictures, copying a card
  template to make your own, and the host sheet (the playlist as a checklist).
- Phase 4 (host mode): done. The Host tab: tick off songs while playing, see which
  cards have one line / two lines / a full card, and check a card number.
- Phase 5 (desktop & translation): done. `muzbingo` opens the app window; the UI is in
  English and Dutch (switch in the top bar); new games start with the last used
  template, grid and number of cards.

## Setup (development)

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e . --no-deps
pytest
```

- `requirements.txt` holds the exact runtime versions and `requirements-dev.txt` adds
  the test tools. The loose version ranges are in `pyproject.toml`; `pip install -e ".[dev]"`
  installs the latest matching versions instead of the pinned ones.
- **Linux system packages.** On Debian/Ubuntu, `python3 -m venv` needs `python3-venv`.
  Qt also needs system libraries for graphics and for the PDF engine, plus some fonts.
  Desktop installs usually have these already; minimal installs, servers and WSL
  often don't:

  ```bash
  sudo apt install python3.12-venv \
      libgl1 libegl1 libgbm1 libasound2t64 libxkbcommon-x11-0 libxkbfile1 \
      libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxtst6 \
      libxcb-cursor0 libxcb-dri3-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
      libxcb-randr0 libxcb-render0 libxcb-render-util0 libxcb-shape0 libxcb-shm0 \
      libxcb-sync1 libxcb-util1 libxcb-xfixes0 libxcb-xkb1 \
      fonts-dejavu-core fonts-liberation
  ```

## Using the app window

```bash
muzbingo                       # or: muzbingo app --data-dir ./testdata
```

Opens MuzBingo in its own window (no browser needed). Downloads (PDF, game files)
ask where to save; links to other websites open in your normal browser. Closing the
window stops the app. On a machine without a desktop it says so: use `muzbingo serve`
there.

## Using the web UI

```bash
muzbingo serve
```

This prints a link like `http://localhost:8080/?token=…`. Open it in a browser; the
token logs you in and is then remembered in a cookie. Each start makes a new token.

The server only accepts connections from the computer it runs on. To use it from
another computer, for example when developing over SSH:

- **VS Code Remote-SSH** forwards the port automatically. Open the **Ports** panel (next
  to Terminal) and click the globe icon for port 8080, or ctrl+click the link in the
  terminal.
- **Plain SSH**: `ssh -L 8080:localhost:8080 <dev machine>`, then open the printed link
  on your own computer.
- **On your network** (e.g. to try it on a tablet): `muzbingo serve --host 0.0.0.0`.
  The token is still required, but anyone on the network can reach the server.

Options: `--port 9000` uses another port; `--data-dir ./testdata` keeps games in another
folder, which is handy for testing. By default games are stored in
`~/.local/share/MuzBingo/games/` (Linux) or `%APPDATA%\MuzBingo\games\` (Windows).

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

# The host sheet: all songs as a checklist (shuffled play order, or playlist/artist/title)
muzbingo hostsheet kerstfeest.muzbingo -o host.pdf --order artist
```

If the title/artist columns aren't detected automatically, pick them with
`--title-col` and `--artist-col`.

## Tests

```bash
pytest
```

The UI tests use NiceGUI's simulated user (`tests/test_ui.py`), so they need no browser.
The PDF tests use Qt WebEngine offscreen.

## Translations

All UI text is written in English and wrapped in `_("…")`. The Dutch translation is
`src/muzbingo/i18n/locale/nl/LC_MESSAGES/muzbingo.po`. After changing UI texts:

```bash
pybabel extract --no-location --sort-output -k _ -k ngettext:1,2 \
    -o src/muzbingo/i18n/locale/muzbingo.pot src/muzbingo
pybabel update -i src/muzbingo/i18n/locale/muzbingo.pot -d src/muzbingo/i18n/locale \
    -D muzbingo --no-fuzzy-matching
# translate the new entries in the .po file (Poedit or a text editor), then:
pybabel compile -d src/muzbingo/i18n/locale -D muzbingo
```

`tests/test_i18n.py` fails when a text is missing from the Dutch catalog, when the
`{placeholders}` differ, or when the compiled `.mo` file is out of date.

## Card templates

Templates live in `src/muzbingo/templates/<name>/`:

- `template.toml`: page size, labels per language, date format, default pictures
- `cards.html.j2`: the Jinja2 HTML
- `style.css`: layout and colours; the variables at the top move or restyle elements

To make your own, copy a template into your templates folder: in the app, use the copy
button next to "Card template" (Settings tab), or run
`muzbingo templates --copy classic "Our party"`. The copy goes to:
- Linux: `~/.local/share/MuzBingo/templates/`
- Windows: `%APPDATA%\MuzBingo\templates\`
- Portable app: `data/templates/` next to the program
- With `muzbingo serve --data-dir DIR`: `DIR/templates/`

Edit the files of the copy; the card preview in the app shows the result when you
switch tabs or pages. `muzbingo templates` lists what's available and where.
