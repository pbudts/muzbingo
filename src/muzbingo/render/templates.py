"""Card templates: folders with ``template.toml``, a Jinja2 HTML file and assets."""

from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from muzbingo.paths import template_search_path, user_templates_dir

MANIFEST = "template.toml"
DEFAULT_LABELS = {"card": "Card"}


class TemplateError(Exception):
    """A template is missing or invalid."""


@dataclass
class CardTemplate:
    name: str  # folder name, used as the template's id
    path: Path
    display_name: str
    description: str = ""
    entry: str = "cards.html.j2"
    page_size: str = "A4"
    orientation: str = "landscape"
    # Combined title + artist characters that fit comfortably in a cell of a
    # 5-column grid; scaled for other column counts by char_budget().
    max_chars: int = 44
    background: str | None = None
    logo: str | None = None
    labels: dict[str, dict[str, str]] = field(default_factory=dict)
    date_formats: dict[str, str] = field(default_factory=dict)

    def label_set(self, language: str) -> dict[str, str]:
        return {**DEFAULT_LABELS, **self.labels.get("en", {}), **self.labels.get(language, {})}

    def asset(self, filename: str | None) -> Path | None:
        if not filename:
            return None
        path = self.path / filename
        return path if path.is_file() else None

    def char_budget(self, cols: int) -> int:
        return max(10, round(self.max_chars * 5 / max(cols, 1)))


def _read(folder: Path) -> CardTemplate:
    try:
        data = tomllib.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise TemplateError(f"Invalid {MANIFEST} in {folder}: {exc}") from exc
    template = CardTemplate(
        name=folder.name,
        path=folder,
        display_name=data.get("name", folder.name),
        description=data.get("description", ""),
        entry=data.get("entry", "cards.html.j2"),
        page_size=data.get("page_size", "A4"),
        orientation=data.get("orientation", "landscape"),
        max_chars=int(data.get("max_chars", 44)),
        background=data.get("background"),
        logo=data.get("logo"),
        labels={k: dict(v) for k, v in data.get("labels", {}).items()},
        date_formats=dict(data.get("date_formats", {})),
    )
    if template.orientation not in ("landscape", "portrait"):
        raise TemplateError(f"{folder.name}: orientation must be 'landscape' or 'portrait'")
    if not (folder / template.entry).is_file():
        raise TemplateError(f"{folder.name}: {template.entry} not found")
    return template


def load_template(name: str, search_path: list[Path] | None = None) -> CardTemplate:
    if not name or Path(name).name != name or name.startswith("."):
        raise TemplateError(f"Invalid template name: {name!r}")
    for root in search_path or template_search_path():
        folder = root / name
        if (folder / MANIFEST).is_file():
            return _read(folder)
    raise TemplateError(f"Template not found: {name!r}")


def list_templates(search_path: list[Path] | None = None) -> list[CardTemplate]:
    """All valid templates; a user template hides a bundled one with the same name."""
    found: dict[str, CardTemplate] = {}
    for root in search_path or template_search_path():
        if not root.is_dir():
            continue
        for folder in sorted(root.iterdir()):
            if folder.name not in found and (folder / MANIFEST).is_file():
                try:
                    found[folder.name] = _read(folder)
                except TemplateError:
                    continue  # skip broken templates in listings; load_template reports them
    return list(found.values())


def _toml_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def copy_template(name: str, display_name: str, target_root: Path | None = None) -> CardTemplate:
    """Copy template ``name`` to the user templates folder under a new name, to edit it.

    The folder name is made from ``display_name``; a number is added when it exists.
    """
    source = load_template(name)
    root = target_root or user_templates_dir()
    root.mkdir(parents=True, exist_ok=True)
    display_name = " ".join(display_name.split())
    taken = {t.name for t in list_templates()}  # a copy must not hide another template
    base = re.sub(r"[^a-z0-9]+", "-", display_name.casefold()).strip("-") or "my-template"
    folder, n = root / base, 2
    while folder.exists() or folder.name in taken:
        folder, n = root / f"{base}-{n}", n + 1
    shutil.copytree(source.path, folder)
    manifest = folder / MANIFEST
    text = manifest.read_text(encoding="utf-8")
    line = f"name = {_toml_string(display_name or folder.name)}"
    text, count = re.subn(r"(?m)^name\s*=.*$", lambda _m: line, text, count=1)
    if not count:
        text = line + "\n" + text
    manifest.write_text(text, encoding="utf-8")
    return _read(folder)
