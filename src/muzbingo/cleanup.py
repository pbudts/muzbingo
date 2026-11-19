"""Shorten song titles from streaming services for printing on cards.

Spotify titles often carry release details that players don't need and that take up
cell space:

    Bohemian Rhapsody - Remastered 2011     →  Bohemian Rhapsody
    Don't Stop Me Now (2011 Remaster)       →  Don't Stop Me Now
    Last Christmas - Single Version         →  Last Christmas
    Wake Me Up (feat. Aloe Blacc)           →  Wake Me Up
    Danger Zone - From "Top Gun" Original Motion Picture Soundtrack  →  Danger Zone

Only *trailing* parts are removed: a " - …" suffix or a final "(…)" / "[…]" group
that contains one of the keywords below. "(I Can't Get No) Satisfaction" and
"Song - X Remix" stay as they are. The UI shows a preview before anything changes.
"""

from __future__ import annotations

import re

# Words that mark release details rather than part of the song's name.
_KEYWORDS = (
    r"remaster(?:ed)?",
    r"radio\s+edit",
    r"single\s+(?:version|edit)",
    r"album\s+version",
    r"(?:\d+\"?\s+|\w+\s+)?version",
    r"edit",
    r"mono",
    r"stereo",
    r"live",
    r"bonus\s+track",
    r"original\s+mix",
    r"extended\s+mix",
    r"deluxe",
    r"anniversary",
    r"soundtrack",
    r"motion\s+picture",
    r"from\s+(?:the\s+)?[\"“'‘].*",  # From "Top Gun"
    r"recorded\s+(?:at|live)",
)
_KEYWORD_RE = re.compile(r"\b(?:" + "|".join(_KEYWORDS) + r")\b", re.IGNORECASE)
_FEAT_RE = re.compile(r"^\s*(?:feat\.?|ft\.?|featuring|with)\s+\S", re.IGNORECASE)

_DASH_SUFFIX_RE = re.compile(r"\s+[-–—]\s+([^-–—]+)$")
_BRACKET_SUFFIX_RE = re.compile(r"\s*[(\[]([^()\[\]]+)[)\]]\s*$")


def _is_detail(text: str) -> bool:
    return bool(_FEAT_RE.match(text) or _KEYWORD_RE.search(text))


def clean_title(title: str) -> str:
    """Return ``title`` without trailing release details; never returns an empty string."""
    text = " ".join(title.split())
    changed = True
    while changed:
        changed = False
        for pattern in (_BRACKET_SUFFIX_RE, _DASH_SUFFIX_RE):
            match = pattern.search(text)
            if match and _is_detail(match.group(1)):
                shorter = text[: match.start()].rstrip(" -–—")
                if shorter:
                    text, changed = shorter, True
                    break
    return text
