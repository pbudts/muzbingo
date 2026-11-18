from muzbingo.patterns import Pattern, check_card


def test_nothing_played(simple_card):
    result = check_card(simple_card, [], Pattern.ONE_LINE)
    assert not result.won
    assert result.complete_rows == []
    assert len(result.missing) == 3


def test_one_line_is_a_row(simple_card):
    assert check_card(simple_card, ["d", "e", "f"], Pattern.ONE_LINE).won
    # a column is not a line
    assert not check_card(simple_card, ["a", "d", "g"], Pattern.ONE_LINE).won
    # a diagonal is not a line
    assert not check_card(simple_card, ["a", "e", "i"], Pattern.ONE_LINE).won


def test_two_lines(simple_card):
    played = ["a", "b", "c", "g", "h"]
    result = check_card(simple_card, played, Pattern.TWO_LINES)
    assert not result.won
    assert result.complete_rows == [0]
    assert result.missing == ["i"]  # nearest win: finish the last row

    result = check_card(simple_card, played + ["i"], Pattern.TWO_LINES)
    assert result.won
    assert result.complete_rows == [0, 2]


def test_full_card(simple_card):
    all_songs = list("abcdefghi")
    assert not check_card(simple_card, all_songs[:-1], Pattern.FULL_CARD).won
    assert check_card(simple_card, all_songs, Pattern.FULL_CARD).missing == []
    assert check_card(simple_card, all_songs + ["x"], Pattern.FULL_CARD).won


def test_full_card_missing_lists_all_unplayed(simple_card):
    result = check_card(simple_card, ["a", "b", "c"], Pattern.FULL_CARD)
    assert sorted(result.missing) == list("defghi")
