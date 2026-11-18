# MuzBingo — Outline & Architecture

A desktop application for creating **music bingo** games. The host plays songs from a
playlist; players mark the matching **artist – title** squares on their card. MuzBingo
imports the playlist, generates randomized cards, saves the game, and renders the
cards to a printable PDF from an editable HTML template.

---

## 1. Goals

| # | Requirement | How it's met |
|---|-------------|--------------|
| 1 | Python desktop app with a Qt6 GUI | PySide6 (official Qt for Python binding, LGPL) |
| 2 | Import a Spotify CSV export | CSV importer with column auto-detection (Exportify / similar formats) |
| 3 | Import an Excel sheet with titles and artists | `.xlsx` importer via `openpyxl`, with column mapping |
| 4 | Edit the playlist (shorten names that are too long) | Editable playlist table with display overrides and a length warning |
| 5 | Generate randomized cards, including rectangular grids (4×5, 5×5, …) | Card generator with separate `rows` × `cols` and a reproducible seed |
| 6 | Store a game (title, grid size, playlist, cards) | Game saved as a single JSON file (`*.muzbingo`) |
| 7 | Layout defined by an HTML template | Jinja2 templates + CSS, editable without touching code |
| 8 | Output cards as PDF, one card per A4 page | HTML → PDF with Qt WebEngine (Chromium), default template is 1 card per page |
| 9 | Winning patterns: one line, two lines, full card | Pattern checker in host mode |
| 10 | English UI with a Dutch translation | Qt translation system (`tr()`, `.ts`/`.qm` files); English is the source language |
| 11 | Runs on Linux and Windows; portable Windows app | PyInstaller "onedir" build, shipped as a zip with a portable settings mode |

### Out of scope (for now)
- Playing the audio itself (the host uses Spotify or another player).
- Online or multiplayer play.
- A Windows installer. The portable zip comes first; an installer (e.g. Inno Setup)
  can be wrapped around the same build folder later.

---

## 2. Domain model

```
Game
├── id: UUID
├── title: str                 e.g. "Christmas Party 2026"
├── event_date: date | None    date of the event, printed on the cards
├── rows: int                  e.g. 4
├── cols: int                  e.g. 5      → "4×5" = 4 rows × 5 columns
├── seed: int                  RNG seed, so a card set can be regenerated exactly
├── background: Image | None   optional per-game background picture (overrides the template's default)
├── logo: Image | None         optional per-game logo, top-left (overrides the template's default)
├── language: str              "en" | "nl" — language of the labels printed on the cards
├── template: str              name of the card template
├── created_at / updated_at
├── playlist: list[Song]
├── cards: list[Card]
└── played: list[song_id]      songs played so far, in order (host mode)

Song
├── id: str                    stable id (Spotify URI if available, otherwise a hash of the original artist+title)
├── title: str                 as imported (kept for reference)
├── artist: str                as imported, all artist names
├── display_title: str | None  edited text to print on cards (None = use title)
├── display_artist: str | None edited text to print on cards (None = use artist)
└── extra: dict                optional: album, duration, etc. (ignored by the core)

Card
├── number: int                1..n, printed on the card so the host can verify a win
└── cells: list[list[str]]     song ids in a rows × cols grid

Image
├── filename: str              original file name, e.g. "christmas.jpg"
├── mime: str                  "image/jpeg" | "image/png"
└── data: bytes                stored base64-encoded in the game file
```

**Constraints**
- Songs needed per card = `rows × cols`: 20 for a 4×5 card, 25 for 5×5. There are no
  free squares. They could be added later, but nothing in the design depends on them.
- The playlist must have at least that many songs. In practice it should have **at
  least 2–3× as many**, so cards differ enough and a game doesn't end too fast. The UI
  warns when it is smaller.
- No two cards in a game are identical (compared as sets of songs, not just positions).
- No song appears more than once on a card.
- **Editing display text never changes a song's id.** Generated cards stay valid when
  you shorten a name after generating; only re-rendering the PDF is needed.

---

## 3. Architecture

Layered, so the core works and can be tested without the GUI:

```
┌──────────────────────────────────────────────────────────┐
│  GUI (PySide6)                 muzbingo/gui/              │
│  MainWindow, PlaylistView, GameSettings, Preview, Host    │
└───────────────┬──────────────────────────────────────────┘
                │ calls
┌───────────────▼──────────────────────────────────────────┐
│  Services                      muzbingo/services/         │
│  GameService (new/open/save, generate, export)            │
└──┬────────────┬─────────────┬─────────────┬──────────┬───┘
   │            │             │             │          │
┌──▼───────┐ ┌──▼────────┐ ┌──▼──────┐ ┌────▼──────┐ ┌─▼────────┐
│importers/│ │ generator │ │ storage │ │ render/   │ │ patterns │
│csv, xlsx │ │ cards     │ │ JSON    │ │ jinja2 →  │ │ win check│
│          │ │           │ │         │ │ html → pdf│ │          │
└──┬───────┘ └──┬────────┘ └──┬──────┘ └────┬──────┘ └─┬────────┘
   └────────────┴──── models (dataclasses) ─┴──────────┘
```

### 3.1 Project layout

```
muzbingo/
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
├── muzbingo.spec                # PyInstaller build definition
├── src/muzbingo/
│   ├── __init__.py
│   ├── __main__.py              # `python -m muzbingo` → launches GUI
│   ├── models.py                # Game, Song, Card dataclasses + (de)serialization
│   ├── paths.py                 # app/data/template/settings locations, portable-mode detection
│   ├── importers/
│   │   ├── __init__.py          # import_playlist(path, mapping=None) dispatcher
│   │   ├── base.py              # column detection, normalisation, dedupe
│   │   ├── csv_importer.py
│   │   └── excel_importer.py
│   ├── generator.py             # generate_cards(playlist, n_cards, rows, cols, seed)
│   ├── patterns.py              # check_card(card, played, pattern) → bool + winning lines
│   ├── storage.py               # save_game(game, path) / load_game(path)
│   ├── render/
│   │   ├── __init__.py
│   │   ├── context.py           # Game → template context (resolves display texts)
│   │   ├── html.py              # Jinja2 environment, render_html(...)
│   │   ├── pdf.py               # html → PDF via QWebEnginePage.printToPdf
│   │   └── filters.py           # Jinja filters (font-size class from text length)
│   ├── templates/               # bundled default templates
│   │   ├── classic/
│   │   │   ├── template.toml    # name, page size/orientation, labels (en/nl), grid placement
│   │   │   ├── cards.html.j2
│   │   │   ├── style.css
│   │   │   ├── background.jpg   # default background picture
│   │   │   └── logo.png         # default logo (replace with your own)
│   │   └── host_sheet/
│   │       └── sheet.html.j2    # checklist of all songs for the host
│   ├── i18n/
│   │   ├── muzbingo_nl.ts       # Dutch translations (source, edited with Qt Linguist)
│   │   └── muzbingo_nl.qm       # compiled, loaded at runtime
│   └── gui/
│       ├── main_window.py
│       ├── playlist_view.py     # QTableView + model, edit mode, length warnings
│       ├── import_dialog.py     # file chooser + column mapping preview
│       ├── game_panel.py        # title, date, rows, cols, # cards, seed, template, background, logo
│       ├── preview.py           # QWebEngineView showing one rendered card
│       └── host_view.py         # mark played songs, check a card number
└── tests/
    ├── test_importers.py
    ├── test_generator.py
    ├── test_patterns.py
    ├── test_storage.py
    └── test_render.py
```

### 3.2 Dependencies

| Package | Purpose |
|---------|---------|
| `PySide6` | Qt6 GUI, Qt WebEngine (preview and PDF), translations |
| `openpyxl` | Read `.xlsx` |
| `Jinja2` | HTML templating |
| `pytest`, `pytest-qt` | Tests (dev) |
| `pyinstaller` | Build the portable app (dev) |

The standard library `csv` and `tomllib` modules cover CSV files and template
metadata, so no pandas is needed.

### 3.3 PDF engine: Qt WebEngine (changed from WeasyPrint)

The first draft used WeasyPrint. Because you need a **portable Windows build**, the
plan now uses **Qt WebEngine** (`QWebEnginePage.printToPdf`) instead:

- **No extra native libraries.** WeasyPrint needs Pango/GTK DLLs on Windows. Bundling
  those into a portable folder works but is fiddly. Qt WebEngine is already part of
  PySide6, and PyInstaller has hooks for it.
- **Same engine for preview and PDF.** The preview pane already uses `QWebEngineView`,
  so the preview and the printed PDF look identical.
- **CSS support is sufficient.** Chromium handles `@page { size: A4 landscape }`,
  `break-after: page`, web fonts, flexbox and grid.

Trade-offs:
- **Asynchronous API.** `printToPdf` needs a running Qt event loop. `render/pdf.py`
  hides this behind a blocking `render_pdf(html, base_url, out_path)` that runs its
  own `QEventLoop`.
- **Command line and tests** need a `QApplication`. They run headless with
  `QT_QPA_PLATFORM=offscreen`.
- **Bigger download.** The bundled Chromium makes the portable app roughly
  150–200 MB zipped.

`render/pdf.py` is the only module that knows about the engine, so WeasyPrint could
still be added later as an alternative.

---

## 4. Components

### 4.1 Importers
- **Entry point:** `import_playlist(path, mapping: ColumnMapping | None) -> ImportResult`
  - Picks the importer by extension: `.csv`, `.xlsx` (and `.xlsm`).
  - `ImportResult` contains `songs`, `warnings` (skipped rows, duplicates) and the
    `mapping` that was used.
- **Column auto-detection** (case-insensitive, first match wins):
  - title: `Track Name`, `Title`, `Song`, `Titel`, `Name`
  - artist: `Artist Name(s)`, `Artist`, `Artists`, `Artiest`, `Performer`
  - id (optional): `Track URI`, `Spotify URI`, `URI`
- If detection fails, the GUI shows the import dialog. It lists the headers and the
  first few rows so the user picks the title and artist columns by hand.
- **Normalisation:**
  - Trim whitespace.
  - **Keep all artist names.** Spotify separates them with `,` or `;`; replace that
    with a consistent `, `.
- **Title cleanup suggestions:** suffixes such as `- Remastered 2011` and `(feat. X)` are
  not removed during import. The edit mode offers them as cleanups (see 4.2) and
  stores the result as `display_title`, so the original stays available.
- **CSV specifics:** detect the encoding (try `utf-8-sig`, then `cp1252`) and the
  delimiter (`csv.Sniffer`; Excel-made CSVs in BE/NL often use `;`).
- **Dedupe:** treat the same artist + title (case-insensitive) as one song and warn
  about it.
- **Merging:** a second import can be appended to the existing playlist instead of
  replacing it.

### 4.2 Playlist edit mode
- **Columns:**
  - `#`
  - **Title** (display text)
  - **Artist** (display text)
  - Original title and original artist (read-only, can be hidden)
  - A ⚠ indicator
- **Editing:** double-click a cell to edit it. Edits are stored in
  `display_title` / `display_artist`. A "Reset to original" action clears an override.
- **Length warning:** a cell is highlighted when the text is longer than a limit for
  the current grid. The limit is a characters-per-cell budget derived from `cols`, and
  templates can override it in `template.toml`.
- A filter toggle shows only songs with warnings, so you can fix them quickly before
  printing.
- **Bulk cleanup action:** strips `- Remastered…`, `(feat. …)`, `- Radio Edit`, etc. It
  shows a preview first, and the results go into the display fields.
- **Other actions:** add, delete and reorder songs; undo/redo via `QUndoStack`.
- **Effect on generated cards:**
  - Display text edits don't invalidate them.
  - Adding or removing songs does, with a "regenerate?" banner. Removing a song that
    is already on cards requires confirmation.

### 4.3 Card generator
```python
def generate_cards(songs, n_cards, rows, cols, seed) -> list[Card]
```
- Use `random.Random(seed)`, never the global RNG, so a card set is reproducible.
- **Balanced draw:** shuffle all song ids into a deck and deal `k` per card. When the
  deck runs out, reshuffle it. Songs then appear about equally often across cards, so
  no song is "dead".
- **No duplicate song on a card:** when dealing near a reshuffle, skip ids already on
  the current card.
- **Unique cards:** track `frozenset(song_ids)` per card. If a new card matches an
  existing one, draw it again (give up after a bounded number of retries and raise a
  clear error).
- **Placement:** songs are placed row by row.

### 4.4 Winning patterns
- **A line is a horizontal row.** Columns and diagonals don't count, so a 4×5 card has
  4 possible lines and a 5×5 card has 5.
- **Patterns:**
  - **One line:** at least one row with all of its songs played.
  - **Two lines:** at least two such rows.
  - **Full card:** every song on the card has been played.
- **API:** `check_card(card, played, pattern) -> CheckResult(won: bool, complete_rows: list[int], missing: list[song_id])`.
  For a pattern that isn't reached yet, `missing` lists the songs still needed for the
  nearest win.
- **Host view:** the host enters a card number. The view shows the card with played
  songs marked, highlights winning lines, and lists which songs are still missing.

### 4.5 Storage
- **Format:** one human-readable JSON file per game, extension `.muzbingo`.
- Includes `"format_version": 1` so later versions can migrate older files.
- Save atomically: write `*.tmp`, then `os.replace`.
- Recent files are kept in the app settings (see 4.8 for portable mode).

Example:
```json
{
  "format_version": 1,
  "id": "6f1c…",
  "title": "Christmas Party 2026",
  "event_date": "2026-12-19",
  "rows": 4,
  "cols": 5,
  "seed": 184467,
  "language": "nl",
  "template": "classic",
  "background": {"filename": "christmas.jpg", "mime": "image/jpeg", "data": "<base64>"},
  "logo": null,
  "playlist": [
    {"id": "spotify:track:…", "title": "Last Christmas - Remastered", "artist": "Wham!",
     "display_title": "Last Christmas", "display_artist": null}
  ],
  "cards": [
    {"number": 1, "cells": [["spotify:track:…", "…", "…", "…", "…"], "…"]}
  ],
  "played": []
}
```

> **Background and logo images:** both pictures are stored inside the game file, so a `.muzbingo`
> file is self-contained. You can copy it to another PC and print the same cards
> without a missing image. A logo in PNG or SVG format keeps its transparency.
> When importing a large photo, it is scaled down to print
> resolution (about 300 dpi for A4, so at most 3508 px on the long side) to keep files
> small.

> A single-file JSON format is simple, portable and easy to diff or inspect. If the
> app later needs a library of many games with search, move to SQLite. The `storage`
> module keeps that change local.

### 4.6 Rendering (Jinja2 → HTML → PDF)
- **Template discovery:** the bundled `templates/` folder plus a user templates folder
  (see 4.8). Each template is a folder with:
  - `template.toml`: display name, page size and orientation, max characters per
    cell, and printed labels per language.
  - `cards.html.j2`
  - Assets (CSS, images, fonts).
- **Default template: `classic`.** A layout of our own design (no existing card to
  copy), **1 card per A4 page**:

  ```
  ┌───────────────────────────────────────────────┐
  │ ┌──────┐                                      │
  │ │ LOGO │      CHRISTMAS PARTY 2026            │  ← logo top-left, game title top centre
  │ └──────┘                                      │
  │   (background picture covers the whole page)  │
  │                                               │
  │                 ┌────┬────┬────┬────┬────┐    │
  │                 │    │    │    │    │    │    │
  │                 ├────┼────┼────┼────┼────┤    │
  │                 │    │    │    │    │    │    │  ← grid, bottom-right
  │                 ├────┼────┼────┼────┼────┤    │
  │                 │    │    │    │    │    │    │
  │                 ├────┼────┼────┼────┼────┤    │
  │                 │    │    │    │    │    │    │
  │                 └────┴────┴────┴────┴────┘    │
  │  Kaart 17 · 19/12/2026                        │  ← card number + date
  └───────────────────────────────────────────────┘
  ```

- **Background picture:**
  - Covers the full page (`background-size: cover`).
  - Uses the game's own picture if set, otherwise the template's `background.jpg`, or
    no picture at all.
  - It reaches the paper edges, but most office printers can't print the outer ~4 mm.
    For true edge-to-edge printing, use a print shop.
- **Logo:**
  - Placed top-left at a fixed maximum height (about 30 mm), keeping its aspect ratio.
  - Uses the game's own logo if set, otherwise the template's `logo.png`; it is left
    out if neither exists.
  - A transparent PNG or an SVG works best on top of the background picture.
- **Cells:** each cell shows the song title and the artist on separate lines.
  - The **title** comes first, in bold.
  - The **artist** comes below it, in a smaller regular font. All names are shown,
    separated by commas.
  - Swapping the order is a two-line change in `cards.html.j2`.
- **Readability:** grid cells get a semi-transparent white fill and a thin border, so
  text stays readable on any picture. The fill opacity is a CSS variable you can tweak.
- **Placement:**
  - Positions are CSS variables set in `style.css` / `template.toml`: grid anchor
    (bottom-right), grid width as a share of the page, margins, and the position of
    the card number and date.
  - Moving the grid or footer means editing a few values, not the HTML.
- **Page orientation:** the template sets it, landscape by default.
- **Grid sizing:** the grid uses CSS grid with `repeat(cols, 1fr)` / `repeat(rows, 1fr)`,
  so 4×5 and 5×5 render with the same template.
- **Card number and date:**
  - Each card prints its number (e.g. "Kaart 17" / "Card 17").
  - It also prints `game.event_date`, formatted for the card language: `19/12/2026` for
    nl, `19 Dec 2026` for en, overridable in `template.toml`.
  - If no event date is set, the date is left out.
- **Template context:**
  ```python
  {
      "game": {"title", "rows", "cols", "event_date", "language"},
      "cards": [
          {"number": 1,
           "rows": [[{"title": "…", "artist": "…"}, …], …]}
      ],
      "date_text": "19/12/2026",                       # formatted event date, or ""
      "background_url": "data:image/jpeg;base64,…",   # or a template-relative path, or None
      "logo_url": "data:image/png;base64,…",          # or a template-relative path, or None
      "labels": {"card": "Kaart"},                     # from template.toml, in game.language
      "options": {"page_size": "A4", "orientation": "landscape"},
  }
  ```
  - The renderer resolves song ids to display texts (`display_* or original`), so
    templates never look songs up themselves.
  - Labels come from the template in the game's language. Dutch cards print
    "Kaart", English cards print "Card".
- **Rendering:**
  - The HTML is built with `Environment(loader=FileSystemLoader(template_dir), autoescape=True)`.
  - It is then printed to PDF with Qt WebEngine (3.3), with the base URL set to the
    template folder so relative CSS, image and font links work.
  - All cards go into one HTML document with `break-after: page`, giving one PDF with
    one page per card.
  - The page uses `@page { size: A4 landscape; margin: 0 }`, so the background
    reaches the page edges.
  - Background printing must be on. In Qt it is
    `QWebEngineSettings.PrintElementBackgrounds`, which is on by default.
  - The background is placed once per page in CSS, so the PDF stays small even with
    many cards.
- **Long text:**
  - CSS uses `overflow-wrap` and hyphenation.
  - A `fit` filter picks a font-size class from the text length.
  - The edit mode (4.2) lets you shorten what still doesn't fit.
- **Extra outputs:**
  - **Host sheet:** a PDF with the full playlist as a checklist, sorted or in play order.
  - **HTML export:** for debugging templates in a browser.

Minimal `cards.html.j2` sketch:
```html
<!doctype html>
<html lang="{{ game.language }}"><head><meta charset="utf-8"><link rel="stylesheet" href="style.css"></head>
<body>
{% for card in cards %}
  <section class="card"
           {% if background_url %}style="background-image: url('{{ background_url }}')"{% endif %}>
    {% if logo_url %}<img class="logo" src="{{ logo_url }}" alt="">{% endif %}
    <h1 class="title">{{ game.title }}</h1>
    <div class="grid" style="--rows: {{ game.rows }}; --cols: {{ game.cols }}">
      {% for row in card.rows %}{% for cell in row %}
        <div class="cell {{ (cell.title ~ cell.artist) | fit }}">
          <div class="song-title">{{ cell.title }}</div>
          <div class="song-artist">{{ cell.artist }}</div>
        </div>
      {% endfor %}{% endfor %}
    </div>
    <footer class="meta">
      <span class="no">{{ labels.card }} {{ card.number }}</span>
      {% if date_text %}<span class="date">{{ date_text }}</span>{% endif %}
    </footer>
  </section>
{% endfor %}
</body></html>
```

### 4.7 GUI (PySide6)
**Main window**, as tabs or a splitter:
1. **Game panel:**
   - Title.
   - Event date (`QDateEdit`, can be left empty).
   - Grid: rows and columns spin boxes, plus presets **4×5** and **5×5**.
   - Number of cards.
   - Seed, with a "🎲 new seed" button.
   - Template and card language.
   - Background picture: choose an image, or use the template default; shown with a
     thumbnail.
   - Logo: works the same way as the background picture.
2. **Playlist view:** a `QTableView` backed by a `QAbstractTableModel` over `Song`s,
   with the edit mode from 4.2. Shows a song count with a warning when the playlist is
   too small for the grid.
3. **Preview:** a `QWebEngineView` showing card #N rendered with the selected template.
   It is the same HTML and engine as the PDF.
4. **Host view** (phase 4): the playlist with checkboxes in play order, a "check card #"
   field, and the pattern result.

**Menu and toolbar:** New game, Open, Save, Save As, Import playlist…, Generate cards,
Export PDF…, Export host sheet…, Open templates folder, Language (English / Nederlands).

**Threading:** PDF printing is asynchronous inside the Qt event loop, so the UI stays
responsive. Show a progress or busy indicator while exporting.

**State rules:**
- Changing the songs, grid size or seed invalidates the generated cards.
- Changing the title, date, background, logo, template or display texts does not
  invalidate them; the next export simply uses the new values.
- When cards are invalidated, the GUI shows a "cards out of date — regenerate?"
  banner instead of silently regenerating.

### 4.8 Internationalisation, settings & portability
- **UI translation:**
  - All UI strings are written in English and wrapped in `self.tr("…")`.
  - `pyside6-lupdate` extracts them into `i18n/muzbingo_nl.ts`. They are translated
    with Qt Linguist (or by hand, since it's XML) and compiled to `.qm` with
    `pyside6-lrelease`.
  - The language is chosen in the menu (default: the system locale, falling back to
    English). It takes effect after a restart, or immediately via `changeEvent`/`retranslateUi`.
  - Qt's own `qtbase_nl.qm` is loaded too, so standard dialogs are in Dutch.
- **Card language** is separate from the UI language. It is stored per game, because
  you might run a Dutch UI and print English cards.
- **Settings and data locations** are decided once, in `paths.py`:
  - **Installed/normal mode:**
    - Settings are stored by `QSettings`: the registry on Windows,
      `~/.config/MuzBingo/` on Linux.
    - User templates live in `QStandardPaths.AppDataLocation/templates`.
  - **Portable mode:**
    - Turned on when a file `portable.txt` (or a `data/` folder) sits next to the
      executable.
    - Settings are then stored as an INI file in `data/settings.ini`.
    - User templates live in `data/templates/`.
    - Nothing is written to the registry or the user profile, so the whole folder can
      live on a USB stick.

---

## 5. Main flows

```
Import:    File → Import → [auto-detect cols] → (mapping dialog if needed) → playlist table
Edit:      fix ⚠ cells in the playlist (shorten names, bulk cleanup) → display texts stored
Generate:  set grid (4×5 / 5×5) / #cards / seed → Generate → cards stored in Game → preview
Save:      File → Save → game.muzbingo (JSON)
Print:     Export PDF → cards.pdf (1 card per A4 page) + optional host sheet
Play:      Host view: tick songs as played; enter card # → one line / two lines / full card?
```

---

## 6. Packaging & distribution

| Target | Approach |
|--------|----------|
| **Development (both)** | `pip install -e .[dev]` in a venv, `python -m muzbingo` |
| **Windows portable** | PyInstaller **onedir** build of `MuzBingo.exe` plus a `_internal/` folder, with `portable.txt` included; shipped as `MuzBingo-x.y.z-win64-portable.zip`. Unzip and run, no install or admin rights needed |
| **Windows installer** (later) | Inno Setup script around the same onedir folder, without `portable.txt` |
| **Linux** | Run from a venv (pip/pipx), or a PyInstaller onedir tarball; an AppImage is possible later |

**Notes**
- **Use onedir, not onefile.** A onefile build unpacks the whole Chromium/WebEngine
  runtime to a temp folder on every start, which is slow and sometimes blocked by
  antivirus. Onedir starts quickly and is still "portable" as a folder.
- **Build on each platform.** PyInstaller doesn't cross-compile, so the Windows build
  is made on Windows. A GitHub Actions workflow with a `windows-latest` runner can build
  the zip automatically on each tagged release.
- **Bundled files.** The `.spec` file bundles `templates/` and `i18n/*.qm` as data
  files. `paths.py` finds them via `sys._MEIPASS` / `__file__`, so the same code runs
  from source and from the build.
- **Code signing.** Unsigned executables may trigger a Windows SmartScreen warning on
  first run ("More info → Run anyway"). Code signing can be added later if needed.

---

## 7. Roadmap

| Phase | Deliverable |
|-------|-------------|
| **0 — Skeleton** | `pyproject.toml`, package layout, models, `paths.py`, pytest set up |
| **1 — Core** | CSV and Excel importers, generator (rows × cols), pattern checker, JSON storage, Jinja → HTML → PDF renderer, `classic` template (1 card/A4, 4×5 and 5×5), tests. Small CLI (`muzbingo generate playlist.csv --grid 4x5 --cards 40 -o cards.pdf`) |
| **2 — GUI MVP** | Main window: import, playlist table with edit mode, game settings, generate, save/open, export PDF, live preview |
| **3 — Polish** | Column-mapping dialog, length warnings and bulk cleanup, undo/redo, user templates folder, host sheet |
| **4 — Host mode** | Mark played songs; verify a card number for one line / two lines / full card |
| **5 — i18n** | All strings wrapped in `tr()` from the start; Dutch `.ts`/`.qm` translation and language switch added here |
| **6 — Packaging** | PyInstaller spec, portable Windows zip, Linux tarball, CI build on GitHub Actions; installer later |

---

## 8. Decisions & open questions

**Decided**
- **Page:** 1 card per A4 page, landscape.
- **Grid:** `rows × cols`, with presets 4×5 (4 rows × 5 columns) and 5×5. There are no
  free squares.
- **Winning patterns:** one line, two lines, full card. A line is a horizontal row only.
- **Card layout:**
  - Background picture covering the page.
  - Logo at the top-left.
  - Game title at the top.
  - Grid at the bottom-right.
  - Card number and event date printed bottom-left on each card.
- **Background picture and logo:** per template, overridable per game, and stored
  inside the game file.
- **Cells:** song title (bold) and artist on separate lines.
- **Template design:** made up from scratch, with no existing card to match.
- **Song text:** show all artist names; long texts are fixed in the playlist edit mode.
- **Languages:** English UI with a Dutch translation.
- **Platforms:** Linux and Windows; a portable Windows zip first, an installer later.
- **PDF engine:** Qt WebEngine instead of WeasyPrint (see 3.3).

**Open**
- None at the moment. New questions will be added here as they come up during
  implementation.
