"""
Gates on the Word (.docx) renderer.

credit-memo 0.1.0 saved a .docx that dropped every Markdown table row on the
floor — the file wrote successfully and printed its success message, so nothing
in the suite noticed. These tests count rows and cells out of the two real
artifacts (the Markdown string and the saved .docx) and compare them, so no
expected total is ever written down here as a literal.

Counting is not enough on its own. A renderer that puts every value in the
document in the wrong cell conserves every count, and this package's whole
defect history — 0.1.0 dropping tables, the pipe bug — is values landing in the
wrong place. So the load-bearing gate here is positional: table for table, row
for row, cell for cell.
"""
import io
from pathlib import Path

import pytest

from creditmemo.data.schema import RiskFactor
from creditmemo.memo import CreditMemo
from creditmemo.renderers.docx import TABLE_STYLE, header_rows_data
from creditmemo.renderers.markdown import render as render_markdown
from creditmemo.tables import (
    block_to_rows,
    content_rows,
    iter_table_blocks,
    separator_index,
    split_row,
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


def _grid(table):
    """One .docx table as a list of rows of cell text, in document order."""
    return [[c.text for c in r.cells] for r in table.rows]


#: The header table's labels, stated here rather than derived, because a gate
#: that reads them out of the renderer follows the renderer when a row goes
#: missing. Changing this list is a deliberate change to the memo's front page.
HEADER_LABELS = ["Fund:", "Prepared By:", "Date:", "IC Date:"]

#: The two .docx formatting properties README.md promises, written out here
#: rather than read from the renderer: a gate that compares the artifact against
#: creditmemo.renderers.docx.TABLE_STYLE follows that constant wherever it goes
#: and can never fail. README: "Tables use the built-in `Table Grid` style with
#: a bold header row."
DOCUMENTED_TABLE_STYLE = "Table Grid"
README = Path(__file__).resolve().parent.parent / "README.md"

#: Which DealProfile field each header label is supposed to be showing.
HEADER_SOURCE = {
    "Fund:": lambda d: d.fund_name,
    "Prepared By:": lambda d: d.prepared_by,
    "Date:": lambda d: d.prepared_date,
    "IC Date:": lambda d: d.ic_date,
}


@pytest.fixture(params=_deal_ids())
def any_deal(request, sample_deal, sample_nmtc_deal):
    return {"loan": sample_deal, "nmtc": sample_nmtc_deal}[request.param]


def test_markdown_has_tables_to_lose(any_deal):
    """Guard the guard: the conservation gates below are vacuous on 0 rows."""
    blocks = _markdown_blocks(any_deal)
    assert blocks, "memo produced no Markdown tables — later gates would pass vacuously"
    assert sum(len(b) for b in blocks) > 0


def test_the_deal_matrix_covers_two_different_deals(sample_deal, sample_nmtc_deal):
    """
    Guard the guard: `any_deal` claims to render a loan memo and an NMTC memo.

    sample_nmtc_deal used to mutate sample_deal and hand the same object back,
    and this module requests both fixtures — so both members of the matrix were
    the NMTC deal, every any_deal gate ran it twice, and the plain loan memo,
    the package's primary case, was never rendered to .docx at all.
    """
    assert sample_deal is not sample_nmtc_deal
    assert sample_deal.loan_terms.deal_type == "loan"
    assert sample_deal.nmtc_terms is None
    assert sample_nmtc_deal.loan_terms.deal_type == "nmtc"
    assert sample_nmtc_deal.nmtc_terms is not None
    # And the two really do produce different memos.
    assert _markdown_blocks(sample_deal) != _markdown_blocks(sample_nmtc_deal)


def test_docx_row_count_conserves_markdown_rows(any_deal, tmp_path):
    """
    Total rows across the generated .docx tables, minus the hand-built header
    table, must equal the number of non-separator Markdown table rows.

    Both sides are counted at test time from the actual artifacts.
    """
    doc = _save(any_deal, tmp_path)

    md = render_markdown(any_deal)
    md_rows = len(content_rows(md.split("\n")))

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


def test_docx_cells_match_the_markdown_positionally(any_deal, tmp_path):
    """
    Table for table, row for row, cell for cell — not a multiset, not a count.

    Reversing every table's row order, or every row's cell order, conserves
    every count and every cell value while rendering
    `| Debt Service Coverage Ratio | 1.35x | >= 1.25x |` in Word as
    `>= 1.25x | 1.35x | Debt Service Coverage Ratio`. Nothing but position
    catches that.
    """
    doc = _save(any_deal, tmp_path)
    md_blocks = _markdown_blocks(any_deal)
    assert md_blocks, "no Markdown tables — this gate would pass vacuously"
    docx_tables = [_grid(t) for t in doc.tables[1:]]  # skip hand-built header
    assert docx_tables == md_blocks


def test_risk_rows_carry_each_risk_in_field_order(sample_deal, tmp_path):
    """
    An order anchor that does not pass through creditmemo.tables at all.

    Every other gate here compares the .docx against the Markdown through the
    shared helpers, so a change inside those helpers moves both sides together.
    This one compares against the DealProfile itself.
    """
    doc = _save(sample_deal, tmp_path, "risks.docx")
    rows = [row for t in doc.tables for row in _grid(t)]
    assert sample_deal.risks, "no risks — this gate would pass vacuously"
    for risk in sample_deal.risks:
        assert [risk.category, risk.description, risk.mitigant] in rows, (
            "risk %r is not a row of (category, description, mitigant)"
            % risk.category
        )


def test_the_delimiter_rule_is_not_rendered(any_deal, tmp_path):
    """
    The `|---|---|` rule is Markdown syntax, not memo content.

    Stated against the delimiter lines the memo actually emitted, not against
    "any row that looks like dashes" — a risk row of `| - | - | - |` is content
    and must survive.
    """
    doc = _save(any_deal, tmp_path)
    md = render_markdown(any_deal)
    rules = []
    for block in iter_table_blocks(md.split("\n")):
        i = separator_index(block)
        if i is not None:
            rules.append(split_row(block[i]))
    assert rules, "the memo emitted no delimiter rules — gate is vacuous"
    rendered = [row for t in doc.tables for row in _grid(t)]
    for rule in rules:
        assert rule not in rendered, f"delimiter rule leaked into the .docx: {rule}"


def test_docx_tables_are_rectangular(any_deal, tmp_path):
    doc = _save(any_deal, tmp_path)
    for table in doc.tables:
        widths = {len(r.cells) for r in table.rows}
        assert len(widths) == 1, f"ragged table: {widths}"


def test_docx_tables_use_the_documented_style(any_deal, tmp_path):
    """README: "Tables use the built-in `Table Grid` style"."""
    doc = _save(any_deal, tmp_path)
    assert doc.tables, "no tables — this gate would pass vacuously"
    for table in doc.tables:
        assert table.style.name == DOCUMENTED_TABLE_STYLE
    # And the renderer still declares the style the README names.
    assert TABLE_STYLE == DOCUMENTED_TABLE_STYLE


def test_the_readme_documents_the_formatting_that_is_gated():
    """
    Keep the promise and the gate in step. If the .docx formatting changes, the
    README sentence has to change with it, and this fails until it does.
    """
    text = io.open(README, encoding="utf-8").read()
    assert "`%s` style" % DOCUMENTED_TABLE_STYLE in text
    assert "bold header row" in text


def test_docx_table_header_row_is_bold_and_body_rows_are_not(any_deal, tmp_path):
    """README: "... with a bold header row."."""
    doc = _save(any_deal, tmp_path)
    bold_runs = 0
    body_runs = 0
    for table in doc.tables[1:]:  # the hand-built header table has no header row
        for cell in table.rows[0].cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    assert run.bold is True, f"header cell {cell.text!r} is not bold"
                    bold_runs += 1
        for row in table.rows[1:]:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        assert not run.bold, f"body cell {cell.text!r} is bold"
                        body_runs += 1
    assert bold_runs, "no header runs examined — this gate would pass vacuously"
    assert body_runs, "no body runs examined — this gate would pass vacuously"


def test_docx_header_table_has_every_documented_label(any_deal, tmp_path):
    """
    The hand-built header table is the only part of the .docx with no Markdown
    counterpart, so the conservation gates measure it from the artifact and
    would follow it anywhere. This is the independent anchor.
    """
    doc = _save(any_deal, tmp_path)
    header = doc.tables[0]
    assert [r.cells[0].text for r in header.rows] == HEADER_LABELS


def test_docx_header_table_matches_the_renderer_construction(any_deal, tmp_path):
    doc = _save(any_deal, tmp_path)
    assert _grid(doc.tables[0]) == [list(p) for p in header_rows_data(any_deal)]


def test_docx_header_values_are_present_when_the_deal_field_is(any_deal, tmp_path):
    """
    Blanking a header value keeps every label and every row count intact. Each
    value is checked against the DealProfile field it claims to show.
    """
    doc = _save(any_deal, tmp_path)
    for row in doc.tables[0].rows:
        label, value = row.cells[0].text, row.cells[1].text
        source = HEADER_SOURCE[label](any_deal)
        assert value.strip(), f"header value for {label!r} is blank"
        if source:
            assert value == str(source), (
                f"header shows {value!r} for {label!r}, deal says {source!r}"
            )


@pytest.mark.parametrize("category,description,mitigant", [
    ("-", "-", "-"),
    (":", "--", "-:-"),
])
def test_a_risk_row_of_dashes_survives_to_the_docx(
    sample_deal, tmp_path, category, description, mitigant
):
    """
    "-" is the commonest not-applicable placeholder an underwriter types, and a
    row made only of "-" and ":" has the shape of a Markdown delimiter rule.

    A content-sniffing separator test dropped such a row from the .docx *and*
    from the expected row count at the same time, so every conservation gate
    stayed green while the row was gone — the same silent divergence 0.2.0
    exists to fix.
    """
    sample_deal.risks.append(RiskFactor(
        category=category, description=description,
        mitigant=mitigant, severity="High",
    ))
    doc = _save(sample_deal, tmp_path, "dash.docx")
    rows = [row for t in doc.tables for row in _grid(t)]
    assert [category, description, mitigant] in rows

    # And the conservation gate must still be measuring something real.
    md_rows = len(content_rows(render_markdown(sample_deal).split("\n")))
    docx_rows = sum(len(t.rows) for t in doc.tables) - len(doc.tables[0].rows)
    assert docx_rows == md_rows


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
