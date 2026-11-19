"""Command-line interface, to use and test the core without the GUI.

Examples::

    muzbingo inspect playlist.csv
    muzbingo new playlist.csv --title "Christmas Party" --grid 4x5 --cards 40 \\
        --date 2026-12-19 --language nl -o party.muzbingo
    muzbingo pdf party.muzbingo -o party.pdf
    muzbingo hostsheet party.muzbingo -o host.pdf --order artist
    muzbingo templates --copy classic "Our party"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from muzbingo.generator import GenerationError, generate_for_game
from muzbingo.importers import ColumnMapping, MappingRequired, PlaylistImportError, import_playlist
from muzbingo.models import Game, Image, new_seed
from muzbingo.storage import FILE_EXTENSION, StorageError, load_game, save_game


def _grid(value: str) -> tuple[int, int]:
    try:
        rows, cols = (int(x) for x in value.lower().replace("×", "x").split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError("use ROWSxCOLS, e.g. 4x5") from None
    if not (1 <= rows <= 10 and 1 <= cols <= 10):
        raise argparse.ArgumentTypeError("rows and columns must be between 1 and 10")
    return rows, cols


def _mapping(args: argparse.Namespace) -> ColumnMapping | None:
    if args.title_col or args.artist_col:
        if not (args.title_col and args.artist_col):
            raise SystemExit("error: give both --title-col and --artist-col")
        return ColumnMapping(title=args.title_col, artist=args.artist_col)
    return None


def _import(args: argparse.Namespace):
    try:
        result = import_playlist(args.playlist, _mapping(args), args.sheet)
    except MappingRequired as exc:
        print("Could not detect the title and artist columns. Columns found:", file=sys.stderr)
        for header in exc.headers:
            print(f"  - {header}", file=sys.stderr)
        print("Choose them with --title-col and --artist-col.", file=sys.stderr)
        raise SystemExit(1) from None
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return result


def cmd_inspect(args: argparse.Namespace) -> int:
    result = _import(args)
    m = result.mapping
    print(f"Columns: title={m.title!r}, artist={m.artist!r}, id={m.id!r}")
    print(f"{len(result.songs)} songs:")
    for i, song in enumerate(result.songs, start=1):
        print(f"{i:4}. {song.artist} – {song.title}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    result = _import(args)
    rows, cols = args.grid
    game = Game(
        title=args.title,
        rows=rows,
        cols=cols,
        n_cards=args.cards,
        event_date=args.date,
        seed=args.seed if args.seed is not None else new_seed(),
        language=args.language,
        template=args.template,
        background=Image.from_file(args.background) if args.background else None,
        logo=Image.from_file(args.logo) if args.logo else None,
        playlist=result.songs,
    )
    generate_for_game(game)
    out = Path(args.output)
    if out.suffix != FILE_EXTENSION:
        out = out.with_name(out.name + FILE_EXTENSION)
    save_game(game, out)
    print(f"Saved {out}: {len(game.cards)} cards ({rows}×{cols}), "
          f"{len(game.playlist)} songs, seed {game.seed}")
    if len(game.playlist) < 2 * game.songs_per_card:
        print("note: for varied cards, use at least twice as many songs as cells per card",
              file=sys.stderr)
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:
    from muzbingo.render import export_html, export_pdf, load_template

    game = load_game(args.game)
    template = load_template(args.template or game.template)
    if args.html:
        out = export_html(game, args.output, template)
    else:
        out = export_pdf(game, args.output, template)
    print(f"Wrote {out} ({len(game.cards)} cards)")
    return 0


def cmd_hostsheet(args: argparse.Namespace) -> int:
    from muzbingo.render import export_host_sheet

    game = load_game(args.game)
    out = export_host_sheet(game, args.output, args.order)
    print(f"Wrote {out} ({len(game.playlist)} songs)")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from muzbingo.ui.server import serve

    return serve(args.host, args.port, Path(args.data_dir) if args.data_dir else None)


def cmd_templates(args: argparse.Namespace) -> int:
    from muzbingo.paths import user_templates_dir
    from muzbingo.render import TemplateError, list_templates
    from muzbingo.render.templates import copy_template

    if args.copy:
        source, name = args.copy
        try:
            template = copy_template(source, name)
        except TemplateError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Copied '{source}' to {template.path}")
        return 0
    print(f"Your own templates go in: {user_templates_dir()}\n")
    for template in list_templates():
        print(f"{template.name:12} {template.display_name} — {template.path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="muzbingo", description="Create music bingo cards.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_import_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("playlist", help="CSV or Excel file with titles and artists")
        p.add_argument("--sheet", help="Excel sheet name (default: the first sheet)")
        p.add_argument("--title-col", help="column with the song titles (if not detected)")
        p.add_argument("--artist-col", help="column with the artists (if not detected)")

    p = sub.add_parser("inspect", help="show the songs a playlist file would import")
    add_import_args(p)
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("new", help="create a game with generated cards from a playlist")
    add_import_args(p)
    p.add_argument("-o", "--output", required=True, help=f"game file to write ({FILE_EXTENSION})")
    p.add_argument("--title", default="Music Bingo", help="game title printed on the cards")
    p.add_argument("--grid", type=_grid, default=(4, 5), help="ROWSxCOLS (default: 4x5)")
    p.add_argument("--cards", type=int, default=30, help="number of cards (default: 30)")
    p.add_argument("--seed", type=int, help="random seed (default: a new random one)")
    p.add_argument("--date", type=date.fromisoformat, help="event date, YYYY-MM-DD")
    p.add_argument("--language", choices=["en", "nl"], default="en", help="language printed on the cards")
    p.add_argument("--template", default="classic", help="card template (default: classic)")
    p.add_argument("--background", help="background picture for this game")
    p.add_argument("--logo", help="logo for this game")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("pdf", help="print the cards of a game to PDF")
    p.add_argument("game", help=f"game file ({FILE_EXTENSION})")
    p.add_argument("-o", "--output", required=True, help="PDF (or HTML with --html) to write")
    p.add_argument("--template", help="use another template than the one saved in the game")
    p.add_argument("--html", action="store_true", help="write HTML instead of PDF (for template work)")
    p.set_defaults(func=cmd_pdf)

    p = sub.add_parser("hostsheet", help="print the playlist as a checklist for the host")
    p.add_argument("game", help=f"game file ({FILE_EXTENSION})")
    p.add_argument("-o", "--output", required=True, help="PDF to write")
    p.add_argument("--order", choices=["shuffled", "playlist", "artist", "title"], default="shuffled",
                   help="order of the songs (default: shuffled, a play order)")
    p.set_defaults(func=cmd_hostsheet)

    p = sub.add_parser("serve", help="run the app for use in a web browser")
    p.add_argument("--host", default="127.0.0.1",
                   help="address to listen on (default: 127.0.0.1, only this computer)")
    p.add_argument("--port", type=int, default=8080, help="port (default: 8080)")
    p.add_argument("--data-dir", help="folder for games and settings (default: the user data folder)")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("templates", help="list the available card templates")
    p.add_argument("--copy", nargs=2, metavar=("TEMPLATE", "NAME"),
                   help="copy a template to your templates folder, to change its layout")
    p.set_defaults(func=cmd_templates)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (PlaylistImportError, GenerationError, StorageError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # render errors and template errors
        from muzbingo.render import RenderError, TemplateError

        if isinstance(exc, (RenderError, TemplateError)):
            print(f"error: {exc}", file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
