import pytest

from muzbingo.importers import (
    ColumnMapping,
    MappingRequired,
    PlaylistImportError,
    import_playlist,
)

EXPORTIFY_CSV = (
    "Track URI,Track Name,Artist URI(s),Artist Name(s),Album Name\n"
    "spotify:track:1,Last Christmas,spotify:artist:a,Wham!,Music from the Edge of Heaven\n"
    'spotify:track:2,September,spotify:artist:b,"Earth, Wind & Fire",The Best Of\n'
    "spotify:track:3,Under Pressure,spotify:artist:c;spotify:artist:d,Queen;David Bowie,Hot Space\n"
)


def write(tmp_path, name, content, encoding="utf-8"):
    path = tmp_path / name
    path.write_text(content, encoding=encoding)
    return path


def test_spotify_export(tmp_path):
    result = import_playlist(write(tmp_path, "p.csv", EXPORTIFY_CSV))

    assert result.mapping == ColumnMapping(title="Track Name", artist="Artist Name(s)", id="Track URI")
    assert [(s.artist, s.title) for s in result.songs] == [
        ("Wham!", "Last Christmas"),
        ("Earth, Wind & Fire", "September"),
        ("Queen, David Bowie", "Under Pressure"),
    ]
    assert result.songs[0].id == "spotify:track:1"
    assert result.warnings == []


def test_semicolon_csv_in_windows_encoding(tmp_path):
    content = "Artiest;Titel\nStromae;Alors on danse\nClouseau;Daar gaat ze\nAngèle;Balance ton quoi\n"
    result = import_playlist(write(tmp_path, "p.csv", content, encoding="cp1252"))

    assert [s.artist for s in result.songs] == ["Stromae", "Clouseau", "Angèle"]
    assert result.songs[0].id.startswith("h:")


def test_utf8_bom_and_whitespace(tmp_path):
    content = "﻿Title,Artist\n  Hello ,  Adele  \n"
    result = import_playlist(write(tmp_path, "p.csv", content))
    assert (result.songs[0].title, result.songs[0].artist) == ("Hello", "Adele")


def test_duplicates_and_empty_rows_are_skipped_with_warning(tmp_path):
    content = "Title,Artist\nHello,Adele\n,\nHELLO,adele\nNo artist,\nSkyfall,Adele\n"
    result = import_playlist(write(tmp_path, "p.csv", content))

    assert [s.title for s in result.songs] == ["Hello", "Skyfall"]
    assert len(result.warnings) == 2  # the duplicate and the row without artist
    assert any("duplicate" in w for w in result.warnings)


def test_unknown_columns_require_mapping(tmp_path):
    path = write(tmp_path, "p.csv", "Nummer,Zanger\nHello,Adele\n")
    with pytest.raises(MappingRequired) as exc:
        import_playlist(path)
    assert exc.value.headers == ["Nummer", "Zanger"]

    result = import_playlist(path, ColumnMapping(title="Nummer", artist="Zanger"))
    assert result.songs[0].artist == "Adele"


def test_mapping_with_missing_column_fails(tmp_path):
    path = write(tmp_path, "p.csv", "Title,Artist\nHello,Adele\n")
    with pytest.raises(PlaylistImportError):
        import_playlist(path, ColumnMapping(title="Title", artist="Singer"))


def test_unsupported_and_empty_files(tmp_path):
    with pytest.raises(PlaylistImportError):
        import_playlist(write(tmp_path, "p.json", "{}"))
    with pytest.raises(PlaylistImportError):
        import_playlist(write(tmp_path, "p.csv", ""))
    with pytest.raises(PlaylistImportError):
        import_playlist(write(tmp_path, "p.csv", "Title,Artist\n"))


def test_excel(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append([])  # blank rows above the header are skipped
    sheet.append([])
    sheet.append(["Artist", "Title", "Year"])
    sheet.append(["Adele", "Hello", 2015])
    sheet.append(["Prince", 1999, 1982])
    path = tmp_path / "p.xlsx"
    workbook.save(path)

    result = import_playlist(path)

    assert [(s.artist, s.title) for s in result.songs] == [("Adele", "Hello"), ("Prince", "1999")]
