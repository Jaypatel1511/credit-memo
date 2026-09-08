"""Unit gates on the shared Markdown-table helpers."""
import pytest

from creditmemo.tables import (
    block_to_rows,
    escape_cell,
    is_separator_row,
    is_table_line,
    iter_table_blocks,
    split_row,
    unescape_cell,
)


@pytest.mark.parametrize("value", [
    "plain",
    "A | B",
    "A || B",
    "trailing pipe |",
    "| leading pipe",
    "back\\slash",
    "back\\ | slash and pipe",
    "line one\nline two",
    "carriage\r\nreturn",
    None,
    1234,
])
def test_escape_round_trips_through_a_row(value):
    """escape_cell -> split_row must return the original text (newlines folded)."""
    expected = "" if value is None else str(value)
    expected = expected.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    row = f"| {escape_cell(value)} | next |"
    assert split_row(row) == [expected, "next"]


def test_unescape_is_inverse_of_escape():
    for v in ["a|b", "a\\b", "a\\|b", "|", "\\"]:
        assert unescape_cell(escape_cell(v)) == v


def test_separator_detection():
    assert is_separator_row("|------|-------------|----------|")
    assert is_separator_row("| :--- | ---: | :---: |")
    # A signature block row is content, not a separator.
    assert not is_separator_row("| IC Chair | | | |")
    assert not is_separator_row("| Revenue | — | — |")


def test_is_table_line():
    assert is_table_line("| a | b |")
    assert is_table_line("  | a | b |")
    assert is_table_line("|---|---|")
    assert not is_table_line("Line one")
    assert not is_table_line("")


def test_iter_table_blocks_splits_on_non_table_lines():
    lines = [
        "## Head", "", "| a | b |", "|---|---|", "| 1 | 2 |", "",
        "### Other", "", "| c |", "|---|", "| 3 |", "",
    ]
    blocks = list(iter_table_blocks(lines))
    assert len(blocks) == 2
    assert len(blocks[0]) == 3 and len(blocks[1]) == 3


def test_block_to_rows_drops_separators_and_pads_ragged_rows():
    rows = block_to_rows(["| a | b |", "|---|---|", "| 1 | 2 | 3 |", "| 4 |"])
    assert rows == [["a", "b", ""], ["1", "2", "3"], ["4", "", ""]]


def test_block_to_rows_on_separator_only_block():
    assert block_to_rows(["|---|---|"]) == []
