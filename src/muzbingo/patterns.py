"""Check a card against the songs played so far.

A line is a horizontal row; columns and diagonals don't count.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from muzbingo.models import Card


class Pattern(Enum):
    ONE_LINE = "one_line"
    TWO_LINES = "two_lines"
    FULL_CARD = "full_card"


@dataclass
class CheckResult:
    won: bool
    complete_rows: list[int]  # 0-based row indexes with all songs played
    missing: list[str]  # songs still needed for the nearest win; empty if won


def rows_needed(pattern: Pattern, n_rows: int) -> int:
    return {Pattern.ONE_LINE: 1, Pattern.TWO_LINES: 2, Pattern.FULL_CARD: n_rows}[pattern]


def check_card(card: Card, played: Iterable[str], pattern: Pattern) -> CheckResult:
    played_set = set(played)
    missing_per_row = [[sid for sid in row if sid not in played_set] for row in card.cells]
    complete = [i for i, missing in enumerate(missing_per_row) if not missing]
    needed = min(rows_needed(pattern, len(card.cells)), len(card.cells))

    if len(complete) >= needed:
        return CheckResult(won=True, complete_rows=complete, missing=[])

    # Nearest win: the `needed` rows with the fewest songs still missing.
    closest = sorted(missing_per_row, key=len)[:needed]
    return CheckResult(
        won=False,
        complete_rows=complete,
        missing=[sid for row in closest for sid in row],
    )
