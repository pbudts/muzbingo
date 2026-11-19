import pytest

from muzbingo.cleanup import clean_title


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Bohemian Rhapsody - Remastered 2011", "Bohemian Rhapsody"),
        ("Don't Stop Me Now (2011 Remaster)", "Don't Stop Me Now"),
        ("Hotel California - 2013 Remaster", "Hotel California"),
        ("Last Christmas - Single Version", "Last Christmas"),
        ("Bad Romance - Radio Edit", "Bad Romance"),
        ("Wake Me Up (feat. Aloe Blacc)", "Wake Me Up"),
        ("Under Pressure - Remastered 2011 (feat. David Bowie)", "Under Pressure"),
        ('Danger Zone - From "Top Gun" Original Motion Picture Soundtrack', "Danger Zone"),
        ("Purple Rain - Live at the Forum", "Purple Rain"),
        ("Rolling in the Deep [Live]", "Rolling in the Deep"),
        ('Thriller - 7" Version', "Thriller"),
        # left alone
        ("(I Can't Get No) Satisfaction", "(I Can't Get No) Satisfaction"),
        ("Song 2 - Blur Remix", "Song 2 - Blur Remix"),
        ("Live Forever", "Live Forever"),
        ("Edit", "Edit"),
        ("Ob-La-Di, Ob-La-Da", "Ob-La-Di, Ob-La-Da"),
    ],
)
def test_clean_title(title, expected):
    assert clean_title(title) == expected


def test_never_empty():
    assert clean_title("(Remastered)") == "(Remastered)"
