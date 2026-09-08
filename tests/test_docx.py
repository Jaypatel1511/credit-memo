"""
Gates on the Word (.docx) renderer.

credit-memo 0.1.0 saved a .docx that dropped every Markdown table row on the
floor — the file wrote successfully and printed its success message, so nothing
in the suite noticed. These tests count rows and cells out of the two real
artifacts (the Markdown string and the saved .docx) and compare them, so no
expected total is ever written down here as a literal.
"""
import pytest

from creditmemo.memo import CreditMemo
from creditmemo.renderers.markdown import render as render_markdown
from creditmemo.tables import (
    block_to_rows,
    is_separator_row,
    is_table_line,
    iter_table_blocks,
)

docx = pytest.importorskip("docx")
Document = docx.Document


def _markdown_blocks(deal):
    """Every Markdown table in the memo, as blocks of content rows."""
    md = render_markdown(deal)
    blocks = [block_to_rows(b) for b in iter_table_blocks(md.split("\n"))]
    return [b for b in blocks if b]


def _save(deal, tmp_path, name="memo.docx"):
    path = str(tmp_path / name)
    CreditMemo(deal).save_docx(path)
    return Document(path)


def _deal_ids():
    return ["loan", "nmtc"]


@pytest.fixture(params=_deal_ids())
def any_deal(request, sample_deal, sample_nmtc_deal):
    return {"loan": sample_deal, "nmtc": sample_nmtc_deal}[request.param]


def test_markdown_has_tables_to_lose(any_deal):
    """Guard the guard: the conservation gates below are vacuous on 0 rows."""
    blocks = _markdown_blocks(any_deal)
    assert blocks, "memo produced no Markdown tables — later gates would pass vacuously"
    assert sum(len(b) for b in blocks) > 0


def test_docx_row_count_conserves_markdown_rows(any_deal, tmp_path):
    """
    Total rows across the generated .docx tables, minus the hand-built header
    table, must equal the number of non-separator Markdown table rows.

    Both sides are counted at test time from the actual artifacts.
    """
    doc = _save(any_deal, tmp_path)

    md = render_markdown(any_deal)
    md_rows = sum(
        1 for line in md.split("\n")
        if is_table_line(line) and not is_separator_row(line)
    )

    # The header block is built directly from the DealProfile, before any
    # Markdown is parsed, so it is the first table in the document. Identify it
    # by its content rather than assuming a position.
    header = doc.tables[0]
    assert header.rows[0].cells[0].text == "Fund:"
    header_rows = len(header.rows)

    docx_rows = sum(len(t.rows) for t in doc.tables)

    assert docx_rows - header_rows == md_rows


def test_docx_table_count_matches_markdown_table_count(any_deal, tmp_path):
    doc = _save(any_deal, tmp_path)
    blocks = _markdown_blocks(any_deal)
    # +1 for the hand-built header table.
    assert len(doc.tables) == len(blocks) + 1


def test_every_markdown_cell_reaches_the_docx(any_deal, tmp_path):
    """
    No cell value may be silently dropped. Compares the multiset of cell texts
    from the Markdown tables against the cells of the parsed .docx tables.
    """
    doc = _save(any_deal, tmp_path)
    md_cells = sorted(
        c for block in _markdown_blocks(any_deal) for row in block for c in row
    )
    docx_cells = sorted(
        c.text
        for t in doc.tables[1:]           # skip the hand-built header table
        for r in t.rows
        for c in r.cells
    )
    assert md_cells == docx_cells


def test_separator_rows_are_not_rendered(any_deal, tmp_path):
    """The |---|---| rule is Markdown syntax, not memo content."""
    doc = _save(any_deal, tmp_path)
    for table in doc.tables:
        for row in table.rows:
            texts = [c.text.strip() for c in row.cells]
            assert not all(
                t and set(t) <= set("-:") for t in texts
            ), f"separator row leaked into the .docx: {texts}"


def test_docx_tables_are_styled_and_rectangular(any_deal, tmp_path):
    doc = _save(any_deal, tmp_path)
    for table in doc.tables:
        assert table.style is not None
        widths = {len(r.cells) for r in table.rows}
        assert len(widths) == 1, f"ragged table: {widths}"


def test_pipe_in_underwriter_text_survives_to_the_docx(sample_deal, tmp_path):
    """
    A literal '|' in a risk description must land in one cell, not split the
    row and shift every value right of it into the wrong column.
    """
    sample_deal.risks[0].description = "Payer mix | Medicaid concentration"
    doc = _save(sample_deal, tmp_path, "pipe.docx")
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    assert "Payer mix | Medicaid concentration" in cells
    assert sample_deal.risks[0].mitigant in cells


def test_bold_markers_stripped_from_cells(sample_deal, tmp_path):
    sample_deal.risks[0].category = "**Credit**"
    doc = _save(sample_deal, tmp_path, "bold.docx")
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    assert "Credit" in cells
    assert "**Credit**" not in cells


def test_save_docx_reports_the_path(sample_deal, tmp_path, capsys):
    path = str(tmp_path / "reported.docx")
    CreditMemo(sample_deal).save_docx(path)
    assert path in capsys.readouterr().out
