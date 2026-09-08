"""Unit gates on the shared Markdown-table helpers."""
import pytest

from creditmemo.tables import (
    block_to_rows,
    content_rows,
    escape_cell,
    has_separator_shape,
    is_table_line,
    iter_segments,
    iter_table_blocks,
    separator_index,
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


def test_separator_shape_is_shape_only():
    assert has_separator_shape("|------|-------------|----------|")
    assert has_separator_shape("| :--- | ---: | :---: |")
    assert not has_separator_shape("| IC Chair | | | |")
    assert not has_separator_shape("| Revenue | — | — |")
    # Shape is not a verdict: a not-applicable risk row has the same shape as a
    # delimiter rule, and only position tells them apart.
    assert has_separator_shape("| - | - | - |")


def test_separator_index_is_position_not_content():
    """
    The delimiter rule is the second line of a block and nothing else. A later
    line that happens to look like one is memo content.
    """
    block = ["| a | b |", "|---|---|", "| - | - |", "|---|---|"]
    assert separator_index(block) == 1
    assert block_to_rows(block) == [["a", "b"], ["-", "-"], ["---", "---"]]


def test_an_all_dash_content_row_reaches_the_rows():
    """
    '-' is the commonest not-applicable placeholder an underwriter types. Under
    a content-sniffing rule this row vanished from the .docx and from the
    expected row count at the same time, so the conservation gate stayed green.
    """
    rows = block_to_rows([
        "| Risk | Description | Mitigant |",
        "|------|-------------|----------|",
        "| - | - | - |",
        "| : | -- | -:- |",
    ])
    assert rows == [
        ["Risk", "Description", "Mitigant"],
        ["-", "-", "-"],
        [":", "--", "-:-"],
    ]


def test_an_all_empty_second_line_is_not_a_delimiter():
    """
    GFM requires every delimiter cell to be non-empty. Dropping that
    requirement from has_separator_shape would eat a legitimately empty row.
    """
    assert not has_separator_shape("| | |")
    assert separator_index(["| a | b |", "| | |", "| 1 | 2 |"]) is None
    assert block_to_rows(["| a | b |", "| | |", "| 1 | 2 |"]) == [
        ["a", "b"], ["", ""], ["1", "2"],
    ]


def test_is_table_line():
    assert is_table_line("| a | b |")
    assert is_table_line("  | a | b |")
    assert is_table_line("|---|---|")
    assert not is_table_line("Line one")
    assert not is_table_line("")


def test_iter_segments_keeps_text_and_tables_in_document_order():
    """The renderer walks this; the order it yields is the order Word gets."""
    lines = ["## Head", "", "| a | b |", "|---|---|", "| 1 | 2 |", "", "Tail"]
    kinds = [k for k, _ in iter_segments(lines)]
    assert kinds == ["text", "text", "table", "text", "text"]
    payloads = [p for _, p in iter_segments(lines)]
    assert payloads[0] == "## Head"
    assert payloads[2] == ["| a | b |", "|---|---|", "| 1 | 2 |"]
    assert payloads[4] == "Tail"


def test_content_rows_counts_every_block_in_the_document():
    lines = [
        "## Head", "", "| a | b |", "|---|---|", "| 1 | 2 |", "",
        "### Other", "", "| c |", "|---|", "| - |", "",
    ]
    assert content_rows(lines) == [["a", "b"], ["1", "2"], ["c"], ["-"]]


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


def test_a_lone_delimiter_shaped_line_is_not_a_table_and_is_not_eaten():
    """
    A single '|---|---|' with no header above it is not a table in GFM at all,
    so there is no delimiter to drop. The positional rule refuses to guess and
    keeps the text; guessing is what dropped underwriter rows.
    """
    assert separator_index(["|---|---|"]) is None
    assert block_to_rows(["|---|---|"]) == [["---", "---"]]
