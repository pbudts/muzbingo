# MuzBingo — Outline & Architecture

An application for creating **music bingo** games. The host plays songs from a
playlist; players mark the matching **artist – title** squares on their card. MuzBingo
imports the playlist, generates randomized cards, saves the game, and renders the
cards to a printable PDF from an editable HTML template.

The user interface is a **web UI served by a local app**. End-users get a normal
desktop window; developers can use the same UI in any browser, also on a machine
without a desktop (see 3.4).

---

## 1. Goals

| # | Requirement | How it's met |
|---|-------------|--------------|
| 1 | Python app, easy to install and use for non-technical users, testable on a machine without a desktop | Web UI (NiceGUI) served on the local PC; shown in an app window (Qt WebEngine) for end-users, or in a browser during development |
| 2 | Import a Spotify CSV export | CSV importer with column auto-detection (Exportify / similar formats) |
| 3 | Import an Excel sheet with titles and artists | `.xlsx` importer via `openpyxl`, with column mapping |
| 4 | Edit the playlist (shorten names that are too long) | Editable playlist table with display overrides and a length warning |
| 5 | Generate randomized cards, including rectangular grids (4×5, 5×5, …) | Card generator with separate `rows` × `cols` and a reproducible seed |
| 6 | Store a game (title, grid size, playlist, cards) | Game saved as a single JSON file (`*.muzbingo`), kept in a "My games" library |
| 7 | Layout defined by an HTML template | Jinja2 templates + CSS, editable without touching code |
| 8 | Output cards as PDF, one card per A4 page | HTML → PDF with Qt WebEngine (Chromium), default template is 1 card per page |
| 9 | Winning patterns: one line, two lines, full card | Pattern checker in host mode |
| 10 | English UI with a Dutch translation | `gettext` catalogs (`.po`/`.mo`); English is the source language |
| 11 | Runs on Linux and Windows; portable Windows app | PyInstaller "onedir" build, shipped as a zip with a portable data folder |

### Out of scope (for now)
- Playing the audio itself (the host uses Spotify or another player).
- Online or multiplayer play, or hosting MuzBingo as a public website.
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
├── n_cards: int               how many cards to generate
├── seed: int                  RNG seed, so a card set can be regenerated exactly
├── background: Image | None   optional per-game background picture (overrides the template's default)
├── logo: Image | None         optional per-game logo, top-left (overrides the template's default)
├── language: str              "en" | "nl" — language of the labels printed on the cards
├── template: str              name of the card template
├── created_at / updated_at
├── playlist: list[Song]
├── cards: list[Card]
├── played: list[song_id]      songs played so far, in order (host mode)
└── cards_basis: str | None    fingerprint of grid, card count, seed and song ids when the cards
                               were generated; differs from the current one → cards are out of date

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
├── mime: str                  "image/jpeg" | "image/png" | "image/svg+xml" | "image/webp"
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

Layered, so the core works and can be tested without any UI:

```
┌──────────────────────────────┐   ┌─────────────────────────────────┐
│ Browser (development)        │   │ App window (end-users)          │
│ any machine, via SSH tunnel  │   │ QMainWindow + QWebEngineView    │
└──────────────┬───────────────┘   └────────────────┬────────────────┘
               │ HTTP + websocket, 127.0.0.1 only    │
┌──────────────▼─────────────────────────────────────▼────────────────┐
│  Web UI (NiceGUI on FastAPI/uvicorn)              muzbingo/ui/       │
│  Library page, game page (settings, playlist, cards, host)          │
│  + plain routes: card preview, template assets, PDF/game downloads  │
└──────────────┬──────────────────────────────────────────────────────┘
               │ calls
┌──────────────▼──────────────────────────────────────────────────────┐
│  Services                                         muzbingo/services/ │
│  Library (list/create/open/save/delete games), GameService          │
│  (import, edit, generate, check), PdfService (runs on the Qt thread)│
└──┬────────────┬─────────────┬─────────────┬──────────┬──────────────┘
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
├── requirements.txt / requirements-dev.txt   # pinned versions
├── README.md
├── ARCHITECTURE.md
├── muzbingo.spec                # PyInstaller build definition
├── src/muzbingo/
│   ├── __init__.py
│   ├── __main__.py              # `python -m muzbingo` → same as the `muzbingo` command
│   ├── cli.py                   # commands: (none) = app window, serve, inspect, new, pdf, templates
│   ├── models.py                # Game, Song, Card, Image dataclasses + (de)serialization
│   ├── paths.py                 # app/data/template/library locations, portable-mode detection
│   ├── settings.py              # user settings (UI language, last template, …) as JSON (phase 5)
│   ├── importers/
│   │   ├── __init__.py          # import_playlist(path, mapping=None) dispatcher
│   │   ├── base.py              # column detection, normalisation, dedupe
│   │   ├── csv_importer.py
│   │   └── excel_importer.py
│   ├── generator.py             # generate_cards(playlist, n_cards, rows, cols, seed)
│   ├── cleanup.py               # clean_title(): strip "- Remastered", "(feat. …)", …
│   ├── images.py                # prepare_image(): scale down large uploaded pictures
│   ├── patterns.py              # check_card(card, played, pattern) → CheckResult
│   ├── storage.py               # save_game(game, path) / load_game(path)
│   ├── render/
│   │   ├── __init__.py          # export_html(...) / export_pdf(...)
│   │   ├── templates.py         # find, list and load card templates (template.toml)
│   │   ├── context.py           # Game → template context (display texts, dates, font-size classes)
│   │   ├── html.py              # Jinja2 environment, render_html(...)
│   │   ├── host_sheet.py        # render_host_sheet(game, order) + host_sheet.html.j2
│   │   └── pdf.py               # html file → PDF via QWebEnginePage.printToPdf
│   ├── services/
│   │   ├── library.py           # "My games": games/<id>.muzbingo in the data folder, autosave
│   │   ├── game_service.py      # use cases on one game, used by the UI (and tests)
│   │   └── pdf_service.py       # queues PDF jobs onto the Qt thread, returns awaitable results
│   ├── ui/
│   │   ├── server.py            # build the app, start/stop uvicorn in a thread, `serve`
│   │   ├── app.py               # setup(): register pages and routes (also used by UI tests)
│   │   ├── auth.py              # token → cookie login, Host header check
│   │   ├── context.py           # the running app's library and PDF service
│   │   ├── routes.py            # plain HTTP routes: card preview, template assets, game pictures
│   │   ├── layout.py            # header bar and small helpers
│   │   ├── pages/
│   │   │   ├── library.py       # start page: list, new, open, duplicate, delete, import/export games
│   │   │   └── game.py          # game page with tabs (settings, playlist, cards, host)
│   │   └── components/
│   │       ├── settings_panel.py   # title, date, grid, cards, seed, template, pictures
│   │       ├── playlist_panel.py   # editable table with length warnings + import dialog
│   │       ├── cards_panel.py      # generate, preview (iframe), download PDF
│   │       └── host_panel.py       # mark played songs, check a card number (phase 4)
│   ├── desktop/
│   │   └── window.py            # QMainWindow + QWebEngineView pointing at the local server
│   ├── i18n/
│   │   ├── __init__.py          # _() / ngettext(), current language
│   │   └── locale/nl/LC_MESSAGES/muzbingo.po (+ compiled .mo)
│   └── templates/               # bundled card templates
│       ├── classic/
│       │   ├── template.toml    # name, page size/orientation, labels (en/nl), date formats
│       │   ├── cards.html.j2
│       │   ├── style.css
│       │   ├── background.svg   # default background picture
│       │   └── logo.svg         # placeholder logo (replace with your own)
│       └── host_sheet/
│           └── sheet.html.j2    # checklist of all songs for the host
└── tests/
    ├── test_importers.py, test_generator.py, test_patterns.py,
    ├── test_storage.py, test_render.py
    ├── test_library.py, test_game_service.py, test_auth.py
    ├── test_ui.py               # NiceGUI's simulated-user tests, no browser needed
    └── ui/main.py               # entry point the UI tests load
```

### 3.2 Dependencies

| Package | Purpose |
|---------|---------|
| `nicegui` | Web UI in Python (brings FastAPI and uvicorn) |
| `PySide6` | Qt WebEngine: PDF printing, and the app window for end-users |
| `openpyxl` | Read `.xlsx` |
| `Jinja2` | HTML templating (cards; already a NiceGUI dependency as well) |
| `pytest`, `pytest-asyncio` | Tests (dev) |
| `Babel` | Extract and compile translations (dev) |
| `pyinstaller` | Build the portable app (dev) |

The standard library `csv`, `tomllib`, `gettext` and `json` modules cover CSV files,
template metadata, translations and settings.

`pytest-qt` is no longer needed: no widgets are tested, and PDF tests only need a
`QApplication`, which `render/pdf.py` creates itself.

### 3.3 PDF engine: Qt WebEngine

The first draft used WeasyPrint. Because you need a **portable Windows build**, the
plan uses **Qt WebEngine** (`QWebEnginePage.printToPdf`) instead:

- **No extra native libraries.** WeasyPrint needs Pango/GTK DLLs on Windows. Bundling
  those into a portable folder works but is fiddly. Qt WebEngine is part of PySide6,
  and PyInstaller has hooks for it.
- **One engine, two jobs.** The same Chromium engine prints the PDFs and shows the UI
  in the app window, so the card preview matches the printed PDF.
- **CSS support is sufficient.** Chromium handles `@page { size: A4 landscape }`,
  `break-after: page`, web fonts, flexbox and grid.
- **Works headless.** Verified on the development machine with
  `QT_QPA_PLATFORM=offscreen`: 12 cards print in under a second.

Trade-offs:
- **Asynchronous API.** `printToPdf` needs a running Qt event loop. `render/pdf.py`
  hides this behind a blocking `print_pdf(html_file, pdf_file, ...)` for the CLI. The
  UI uses `PdfService` instead (3.4).
- **System libraries on Linux.** Minimal Linux installs need some graphics libraries
  and fonts (see README). Windows builds bundle everything.
- **Bigger download.** The bundled Chromium makes the portable app roughly
  150–200 MB zipped.

`render/pdf.py` is the only module that knows about the engine, so WeasyPrint could
still be added later as an alternative.

### 3.4 Web UI as a local app

**Why:**
- The development machine has no desktop, so a Qt widget GUI would be hard to test.
- A web UI can be used from any browser, and NiceGUI can test it in pytest without one.
- End-users should not notice it's a web app: they get a normal window, with no
  browser, URLs or ports in sight.

**Two ways to run, one code base:**

| | `muzbingo` (end-users) | `muzbingo serve` (development) |
|---|---|---|
| Server | 127.0.0.1, random free port | 127.0.0.1:8080 by default (`--port`, `--host`) |
| Shown in | App window: `QMainWindow` + `QWebEngineView` | Any browser, e.g. via `ssh -L 8080:localhost:8080 devbox` |
| Downloads (PDF, game file) | Native "Save as" dialog (`QWebEngineProfile.downloadRequested`) | Browser downloads |
| Uploads (playlist, pictures) | `<input type=file>` → native file dialog, handled by WebEngine | Browser file dialog |
| Stopping | Closing the window stops the server and exits | Ctrl+C |

**Threads:**
- The **main thread runs the Qt event loop** in both modes: with the window in app
  mode, and with an invisible offscreen `QApplication` in serve mode.
- **uvicorn runs in a background thread** with its own asyncio loop. NiceGUI is
  mounted on a FastAPI app with `ui.run_with(...)` and served by uvicorn directly.
- **PDF jobs.** `PdfService` sends each job to the Qt thread through a queued signal
  and returns an `asyncio.Future`, so UI handlers can simply `await` it. Printing never
  blocks the web server, and Qt objects are only touched on the Qt thread.

**Security:** the server is reachable only from the user's own PC, but other programs
and websites on that PC must not be able to use it either.
- The server binds to `127.0.0.1` only.
- At startup the app creates a random token. The window opens
  `http://127.0.0.1:<port>/?token=…`, which sets a session cookie. Requests without
  that cookie are refused.
- `serve` mode prints the URL with its token.
- The `Host` header must be `127.0.0.1` or `localhost`, which blocks DNS-rebinding
  attacks.

**Preview over HTTP:**
- The card renderer (4.6) takes a **URL resolver**, so the same template works in both
  places:
  - **PDF:** `file://` URLs.
  - **Browser preview:** HTTP routes, e.g. `/assets/templates/classic/style.css` and
    `/assets/games/<id>/background`.
- The browser can't load `file://` URLs from an `http://` page, which is why the
  preview needs HTTP routes.

**Scope of the window code:** `desktop/window.py` only starts the server, shows the
page, handles downloads and closes cleanly (about 50 lines). All UI logic lives in
`ui/` and can be tested in a browser.

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
- If detection fails (`MappingRequired`), the import dialog lists the headers and the
  first few rows so the user picks the title and artist columns by hand.
- **Normalisation:**
  - Trim whitespace.
  - **Keep all artist names.** Spotify separates several artists with `;`; they are
    joined with `, `. Commas are left alone, because they also occur inside single
    names ("Earth, Wind & Fire").
- **Title cleanup suggestions:** suffixes such as `- Remastered 2011` and `(feat. X)` are
  not removed during import. The edit mode offers them as cleanups (see 4.2) and
  stores the result as `display_title`, so the original stays available.
- **CSV specifics:** detect the encoding (try `utf-8-sig`, then `cp1252`) and the
  delimiter (`csv.Sniffer`; Excel-made CSVs in BE/NL often use `;`).
- **Dedupe:** treat the same artist + title (case-insensitive) as one song and warn
  about it.
- **Merging:** a second import can be appended to the existing playlist instead of
  replacing it.
- **Uploads.** The UI saves an uploaded file to a temporary file and passes its path to
  `import_playlist`, so the importers keep working on paths.

### 4.2 Playlist edit mode
- **Table:** an editable table (NiceGUI's AG Grid) with these columns:
  - `#`
  - **Title** (display text)
  - **Artist** (display text)
  - Original title and original artist (read-only, can be hidden)
  - A ⚠ indicator
- **Editing:** click a cell to edit it. Edits are stored in
  `display_title` / `display_artist`. A "Reset to original" action clears an override.
- **Length warning:** a cell is highlighted when the text is longer than a limit for
  the current grid. The limit is a characters-per-cell budget derived from `cols`, and
  templates can override it in `template.toml`.
- A filter toggle shows only songs with warnings, so you can fix them quickly before
  printing.
- **Bulk cleanup action ("Shorten titles"):** strips `- Remastered…`, `(feat. …)`,
  `- Radio Edit`, etc. (`cleanup.py`; only trailing parts, so "(I Can't Get No)
  Satisfaction" stays). It shows a preview with checkboxes first, and the results go
  into the display fields.
- **Other actions:** add, delete and reorder songs.
- **Undo:** `GameService` keeps a history of game snapshots (50 steps, undo and redo),
  with buttons in the top bar and Ctrl+Z / Ctrl+Y. Every change goes through one
  `_change()` wrapper that snapshots, saves, and rolls back on errors; quick repeated
  edits of the same field (typing a title) are one step, and bulk actions (delete,
  shorten titles) are one step. The UI keeps one `GameService` per game for the
  whole session (`AppContext.game_service`), so the history survives page reloads;
  if the file was changed by something else, the game is loaded fresh.
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

### 4.5 Storage and the games library
- **Format:** one human-readable JSON file per game, extension `.muzbingo`.
- Includes `"format_version": 1` so later versions can migrate older files.
- Save atomically: write `*.tmp`, then `os.replace`.
- **Library:**
  - Games live in `<data folder>/games/<game id>.muzbingo` (see 4.8 for the data
    folder).
  - The start page lists them with title, event date, number of songs and cards, and
    last change, newest first.
  - Actions: new, open, duplicate (handy for a yearly party), delete (moved to
    `games/trash/`, not removed), import a `.muzbingo` file, and download one to
    share or back up.
- **Autosave:** every change is saved shortly after it's made (about 1 s debounce), so
  there's no Save button and no "unsaved changes" question. This is friendlier for
  non-technical users, and undo (4.2) covers mistakes.
- **One user:** if the same game is open in two browser tabs, the last change wins.
  This is acceptable for a single-user local app.

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
     "display_title": "Last Christmas"}
  ],
  "cards": [
    {"number": 1, "cells": [["spotify:track:…", "…", "…", "…", "…"], "…"]}
  ],
  "played": []
}
```

> **Background and logo images:** both pictures are stored inside the game file, so a
> `.muzbingo` file is self-contained. You can copy it to another PC and print the same
> cards without a missing image. A logo in PNG or SVG format keeps its transparency.
> When uploading a large photo, it is scaled down to print resolution (about 300 dpi
> for A4, so at most 3508 px on the long side) to keep files small.

> A single-file JSON format is simple, portable and easy to diff or inspect. If the
> library later needs search across many games, move to SQLite. The `storage` and
> `library` modules keep that change local.

### 4.6 Rendering (Jinja2 → HTML → PDF)
- **Template discovery:** the bundled `templates/` folder plus a user templates folder
  (see 4.8). Each template is a folder with:
  - `template.toml`: display name, page size and orientation, max characters per
    cell, default pictures, printed labels and date formats per language.
  - `cards.html.j2`
  - Assets (CSS, images, fonts).
- **Default template: `classic`.** A layout of our own design, **1 card per A4 page**:

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
  - Uses the game's own picture if set, otherwise the template's `background.svg`, or
    no picture at all.
  - It reaches the paper edges, but most office printers can't print the outer ~4 mm.
    For true edge-to-edge printing, use a print shop.
- **Logo:**
  - Placed top-left at a fixed maximum height (about 30 mm), keeping its aspect ratio.
  - Uses the game's own logo if set, otherwise the template's `logo.svg`; it is left
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
  - Positions, sizes and colours are CSS variables at the top of `style.css`: margins,
    maximum grid area and cell size, logo size, and colours.
  - Moving the grid or footer means editing a few values, not the HTML.
- **Page orientation:** the template sets it, landscape by default.
- **Grid sizing:** the grid uses CSS grid with the row and column count as CSS
  variables, so 4×5 and 5×5 render with the same template.
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
           "rows": [[{"title": "…", "artist": "…", "size": "normal"}, …], …]}
      ],
      "date_text": "19/12/2026",          # formatted event date, or ""
      "background_url": "…",              # or None
      "logo_url": "…",                    # or None
      "template_url": "…/classic/",       # for style.css, fonts, images; ends with "/"
      "labels": {"card": "Kaart"},        # from template.toml, in game.language
      "options": {"page_size": "A4", "orientation": "landscape"},
  }
  ```
  - The renderer resolves song ids to display texts (`display_* or original`), so
    templates never look songs up themselves.
  - Labels come from the template in the game's language. Dutch cards print
    "Kaart", English cards print "Card".
  - **The URLs come from a resolver** chosen by the caller:
    - **PDF and HTML export:** `file://` URLs.
    - **Preview in the UI:** HTTP routes on the local server (3.4).
- **Rendering:**
  - The HTML is built with `Environment(loader=FileSystemLoader(template_dir), autoescape=True)`.
  - **For the PDF:**
    - The HTML is written to a temporary file and printed with Qt WebEngine (3.3).
      Loading from a file avoids the 2 MB limit of `QWebEnginePage.setHtml`.
    - Pictures are referenced by URL, never embedded as data URLs, so the HTML stays
      small however many cards there are.
    - All cards go into one HTML document with `break-after: page`, giving one PDF with
      one page per card.
    - The page uses `@page { size: A4 landscape; margin: 0 }`, so the background
      reaches the page edges.
  - **For the preview:** the same template renders a single card, which the UI shows in
    an `<iframe>` scaled to fit.
- **Long text:**
  - CSS uses `overflow-wrap` and hyphenation.
  - Each cell gets a font-size class (`size-normal`, `size-small`, `size-tiny`) based on
    the title + artist length compared with the template's `max_chars`.
  - The edit mode (4.2) lets you shorten what still doesn't fit.
- **Extra outputs:**
  - **Host sheet:** a PDF (A4 portrait, `render/host_sheet.html.j2`, independent of
    the card template) with the full playlist as a checklist: in a shuffled play order
    (the same every time for a game), playlist order, or sorted by artist or title. It
    shows on how many cards each song appears.
  - **HTML export:** for working on templates in a browser.

The full template is in `src/muzbingo/templates/classic/cards.html.j2`.

### 4.7 User interface (NiceGUI)

**Start page — "My games":**
- Shows the library (4.5) as cards or a list.
- Buttons: **New game**, **Import game file**.
- Each game has **Open**, **Duplicate**, **Download** and **Delete**.
- A new game asks only for a title and a playlist file (upload). Everything else has
  sensible defaults (4×5, 30 cards, classic template, the UI language as card language).

**Game page**, with tabs:
1. **Settings:**
   - Title.
   - Event date (a date picker, can be left empty).
   - Grid: rows and columns, plus presets **4×5** and **5×5**.
   - Number of cards.
   - Seed, with a "🎲 new seed" button.
   - Template and card language, plus a button to copy the template into the user
     templates folder to make your own.
   - Background picture and logo: upload an image or use the template default; each
     is shown with a thumbnail. Large raster pictures are scaled down on upload
     (`images.py`, Qt's QImage: background max. 3508 px = A4 at 300 dpi, logo max.
     1200 px; heavy pictures without transparency become JPEG). SVG stays as is.
2. **Playlist:** the editable table from 4.2. It also shows the song count, with a
   warning when the playlist is too small for the grid, plus **Import playlist**
   (replace or append).
3. **Cards:**
   - **Generate cards** button.
   - Live preview of card #N (an `<iframe>`, previous/next buttons).
   - **Download PDF** and **Download host sheet** (phase 3).
4. **Host** (phase 4): the playlist with checkboxes in play order, a "check card #"
   field, and the pattern result.

**Top bar:** the game title, a "back to My games" link, an autosave indicator
("Saved ✓"), and the UI language switch (English / Nederlands).

**Long-running work:** PDF export runs through `PdfService` (3.4). The button shows a
spinner and the download starts when the PDF is ready; the UI stays usable meanwhile.

**State rules:**
- Changing the songs, grid size or seed invalidates the generated cards.
- Changing the title, date, background, logo, template or display texts does not
  invalidate them; the next export simply uses the new values.
- When cards are invalidated, the UI shows a "cards out of date — regenerate?"
  banner instead of silently regenerating.

**Testing:**
- **Automated:** UI logic is tested with NiceGUI's simulated `User` fixture in pytest.
  It is fast and needs no browser.
- **Manual:** use `muzbingo serve` from any browser.
- **App window:** checked manually on a desktop machine (Windows/Linux) before each
  release.

### 4.8 Internationalisation, settings & portability
- **UI translation:**
  - All UI strings are written in English and wrapped in `_("…")` (`gettext`).
  - `pybabel extract` collects them into a template catalog, and the Dutch translations
    live in `i18n/locale/nl/LC_MESSAGES/muzbingo.po`. They can be edited with Poedit
    or any text editor, and are compiled to `.mo` with `pybabel compile`. The compiled
    `.mo` files are included in builds.
  - The language is chosen in the top bar. The default is the system locale, falling
    back to English. The choice is stored in the settings and takes effect on the next
    page load.
- **Card language** is separate from the UI language. It is stored per game, because
  you might run a Dutch UI and print English cards.
- **Data folder** (decided once, in `paths.py`):
  - **Normal mode:**
    - Linux: `~/.local/share/MuzBingo/`
    - Windows: `%APPDATA%\MuzBingo\`
  - **Portable mode:**
    - Turned on when a file `portable.txt` sits next to the executable.
    - The data folder is then `data/` next to the program.
    - Nothing is written to the user profile, so the whole folder can live on a USB
      stick.
  - Contents:
    - `games/`: the library
    - `templates/`: user templates
    - `settings.json`: UI language, last used template and grid, etc.

---

## 5. Main flows

```
Start:     double-click MuzBingo → window opens on "My games"
New game:  New game → title + upload playlist → [auto-detect cols] → (mapping dialog if needed) → game page
Edit:      Playlist tab: fix ⚠ cells (shorten names, bulk cleanup) → display texts stored (autosaved)
Generate:  Settings tab: grid (4×5 / 5×5), #cards, seed → Cards tab: Generate → preview
Print:     Cards tab: Download PDF → "Save as" dialog → cards.pdf (1 card per A4 page)
Play:      Host tab: tick songs as played; enter card # → one line / two lines / full card?
Share:     My games: Download → game.muzbingo (all data incl. pictures) → Import on another PC
```

---

## 6. Packaging & distribution

| Target | Approach |
|--------|----------|
| **Development** | venv + `pip install -r requirements-dev.txt` + `pip install -e . --no-deps`; `muzbingo serve` |
| **Windows portable** | PyInstaller **onedir** build of `MuzBingo.exe` plus an `_internal/` folder, with `portable.txt` included; shipped as `MuzBingo-x.y.z-win64-portable.zip`. Unzip and run, no install or admin rights needed |
| **Windows installer** (later) | Inno Setup script around the same onedir folder, without `portable.txt` |
| **Linux** | Run from a venv (pip/pipx), or a PyInstaller onedir tarball; an AppImage is possible later |

**Notes**
- **Use onedir, not onefile.** A onefile build unpacks the whole Chromium/WebEngine
  runtime to a temp folder on every start, which is slow and sometimes blocked by
  antivirus. Onedir starts quickly and is still "portable" as a folder.
- **Build on each platform.** PyInstaller doesn't cross-compile, so the Windows build
  is made on Windows. A GitHub Actions workflow with a `windows-latest` runner can build
  the zip automatically on each tagged release.
- **Bundled files.** The `.spec` file bundles:
  - `templates/`
  - `i18n/**/*.mo`
  - NiceGUI's own static files (via `collect_data_files("nicegui")`)

  `paths.py` finds them via `sys._MEIPASS` / `__file__`, so the same code runs from
  source and from the build.
- **No console window.** The Windows build is a windowed app (`console=False`). Logs go
  to `<data folder>/logs/`.
- **Single instance.** A lock file in the data folder makes a second start bring the
  existing window to the front instead of starting another server (phase 6).
- **Code signing.** Unsigned executables may trigger a Windows SmartScreen warning on
  first run ("More info → Run anyway"). Code signing can be added later if needed.
- **Firewall.** The server only listens on `127.0.0.1`, so Windows Firewall shows no
  prompt.

---

## 7. Roadmap

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **0 — Skeleton** | `pyproject.toml`, package layout, models, `paths.py`, pytest set up | ✅ done |
| **1 — Core** | CSV and Excel importers, generator (rows × cols), pattern checker, JSON storage, Jinja → HTML → PDF renderer, `classic` template (1 card/A4, 4×5 and 5×5), tests. Small CLI (`muzbingo new playlist.csv --grid 4x5 --cards 40 -o game.muzbingo`, `muzbingo pdf game.muzbingo -o cards.pdf`) | ✅ done |
| **2 — Web UI MVP** | Services (library with autosave, game service, PDF service on the Qt thread), `muzbingo serve`, URL resolver for previews, start page, game page (settings, playlist table with editing, generate, preview, download PDF), token auth, UI tests | ✅ done |
| **3 — Polish** | Column-mapping dialog, length warnings and bulk cleanup, undo, image upload with downscaling, user templates folder, host sheet | ✅ done |
| **4 — Host mode** | Mark played songs; verify a card number for one line / two lines / full card | |
| **5 — Desktop & i18n** | App window (`desktop/window.py`) with native downloads; all strings in `_()` from the start; Dutch `.po` translation and language switch | |
| **6 — Packaging** | PyInstaller spec, portable Windows zip, Linux tarball, single-instance lock, CI build on GitHub Actions; installer later | |

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
- **User interface:** a NiceGUI web UI served locally instead of a Qt widget GUI
  (see 3.4).
  - End-users get an app window (Qt WebEngine).
  - Development and testing use `muzbingo serve` in a browser.
- **Saving:** a "My games" library with autosave, instead of file dialogs.

**Open**
- None at the moment. New questions will be added here as they come up during
  implementation.
