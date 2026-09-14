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
import re
from collections import Counter
from pathlib import Path

import pytest

from creditmemo.data.schema import RiskFactor
from creditmemo.memo import CreditMemo
from creditmemo.renderers.docx import TABLE_STYLE, parse_prepared_date
from creditmemo.renderers.markdown import render as render_markdown
from creditmemo.tables import (
    block_to_rows,
    iter_segments,
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


#: The two .docx formatting properties README.md promises, written out here
#: rather than read from the renderer: a gate that compares the artifact against
#: creditmemo.renderers.docx.TABLE_STYLE follows that constant wherever it goes
#: and can never fail. README: "Tables use the built-in `Table Grid` style with
#: a bold header row."
DOCUMENTED_TABLE_STYLE = "Table Grid"
README = Path(__file__).resolve().parent.parent / "README.md"

#: Which DealProfile field each metadata label is supposed to be showing. Used
#: to anchor the .docx against the deal itself rather than against the renderer.
METADATA_SOURCE = {
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
    Total rows across the generated .docx tables must equal the number of
    non-separator Markdown table rows.

    Both sides are counted at test time from the actual artifacts.
    """
    doc = _save(any_deal, tmp_path)

    md = render_markdown(any_deal)
    md_rows = len(content_rows(md.split("\n")))

    docx_rows = sum(len(t.rows) for t in doc.tables)

    assert docx_rows == md_rows


def test_docx_table_count_matches_markdown_table_count(any_deal, tmp_path):
    doc = _save(any_deal, tmp_path)
    blocks = _markdown_blocks(any_deal)
    assert len(doc.tables) == len(blocks)


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
        for t in doc.tables
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
    docx_tables = [_grid(t) for t in doc.tables]
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
    for table in doc.tables:
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
    docx_rows = sum(len(t.rows) for t in doc.tables)
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


# ── R5: every piece of content appears exactly once ───────────────────────────
#
# The ruled invariant for 0.2.1: "Every piece of content appears in the .docx
# exactly as many times as it appears in the Markdown."
#
# Until 0.2.1 the renderer emitted a hand-built cover block — a Title, an H1 of
# the deal name and a four-row metadata table read off the DealProfile — and
# then parsed the Markdown, which carries all three itself. The title, the deal
# name and the whole Fund/Prepared By/Date/IC Date block appeared twice in every
# Word memo the package ever produced. Every gate in this module was written to
# subtract `doc.tables[0]` and therefore measured around the duplicate.
#
# WHAT THESE GATES ARE, AND WHAT THEY ARE NOT (R8)
#
# These are DUPLICATION gates. They compare multisets, so they catch a piece of
# content appearing more or fewer times than the Markdown says — which is what
# 0.2.0's hand-built cover block did, and what they were built for.
#
# They are NOT the input-fidelity gate, and must not be relied on as one. The
# normalisers below re-implement the renderer's own transformations:
# `_strip_emphasis` was the renderer's `.replace("*", "")`, and until R17 a
# `_MD_NUMBER = r"^\d+\.\s+(.*)$"` here was character-for-character the
# `_ORDERED_ITEM` regex the renderer matched with. So they removed, on the
# Markdown side, exactly what the renderer destroyed on the Word side, and both
# G1 variants stayed green while
#
#     2019. The borrower refinanced its senior debt at 4.2%.
#
# reached the Investment Committee as item 1. — and while a lone `*` was deleted
# from every paragraph in the document.
#
#     RULE: a gate that re-implements the transformation it is checking shares
#     its blind spot.
#
# Fidelity is gated in tests/test_input_fidelity.py by G11, which asserts against
# the strings the caller put on the DealProfile and re-implements nothing. Both
# of the renderer mutations named above redden G11 while leaving every gate in
# this module green; that contrast is the reason G11 exists.
#
# The comment these lines replace claimed the normalisers were written here
# "rather than imported from the renderer on purpose: a gate that strips list
# markers with the renderer's own regex follows that regex wherever it goes."
# That is true and it is not enough: copying the regex has the same blind spot
# as importing it, one release later.
_MD_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
_MD_BULLET = re.compile(r"^[-*]\s+(.*)$")
#: There is deliberately no `_MD_NUMBER` here any more. R17 stopped the .docx
#: renderer restyling ordered items, so an ordered line's number is now part of
#: the paragraph text on both sides and there is nothing left to normalise away.
#: Deleting the normaliser is what makes these gates able to see the number at
#: all: with it in place, restoring `List Number` in the renderer left every
#: gate in this module green.
_MD_RULE = "---"


def _strip_emphasis(text):
    return text.replace("**", "").replace("*", "").strip()


def _md_atoms(deal):
    """
    Every piece of content in the Markdown memo, as the text a reader sees.

    Table cells count individually, because that is how they land in Word.
    Blank lines and the section rules are syntax, not content.
    """
    md = render_markdown(deal)
    atoms = []
    for kind, payload in iter_segments(md.split("\n")):
        if kind == "table":
            atoms += [c for row in block_to_rows(payload) for c in row]
            continue
        line = payload
        if not line.strip() or line.strip() == _MD_RULE:
            continue
        for pattern in (_MD_HEADING, _MD_BULLET):
            match = pattern.match(line)
            if match:
                line = match.groups()[-1]
                break
        atoms.append(_strip_emphasis(line))
    return atoms


def _docx_atoms(doc):
    """The same, read back out of the saved Word document."""
    atoms = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    atoms += [c.text.strip() for t in doc.tables for r in t.rows for c in r.cells]
    return atoms


def test_g1_every_piece_of_content_appears_exactly_as_often_as_in_the_markdown(
    any_deal, tmp_path
):
    """
    G1 — content multiset.

    Red-proof (must fail): restore the duplicate cover block in
    creditmemo/renderers/docx.py, i.e. re-add

        title = doc.add_heading("INVESTMENT COMMITTEE MEMORANDUM", 0)
        doc.add_heading(deal.deal_name, 1)
        ... the four-row header table ...

    before the iter_segments loop.
    Observed: 2 failed (loan, nmtc) — plus 6 more across G2/G3 and the
    conservation gates.
    """
    doc = _save(any_deal, tmp_path)
    md_counts = Counter(_md_atoms(any_deal))
    docx_counts = Counter(_docx_atoms(doc))
    assert md_counts, "no content — this gate would pass vacuously"
    assert docx_counts == md_counts


def test_g1_holds_for_prose_alone(any_deal, tmp_path):
    """
    G1, restricted to the non-table half of the document.

    Stated separately because that half is where 0.2.0's defects lived and it
    is the half that had no gate at all: on 0.2.0, deleting the entire
    non-table branch of the renderer — title, every heading, every narrative
    paragraph, every bullet and every rule — left the suite at 86 passed.
    """
    doc = _save(any_deal, tmp_path)
    table_cells = Counter(
        c for block in _markdown_blocks(any_deal) for row in block for c in row
    )
    md_prose = Counter(_md_atoms(any_deal)) - table_cells
    docx_prose = Counter(p.text.strip() for p in doc.paragraphs if p.text.strip())
    assert md_prose, "no prose — this gate would pass vacuously"
    assert docx_prose == md_prose


def test_g2_every_heading_appears_exactly_once_as_a_heading(any_deal, tmp_path):
    """
    G2 — heading multiset.

    Every `#`/`##`/`###` heading in the Markdown appears exactly once in the
    .docx as a Title or Heading N paragraph, and the .docx invents none.

    Red-proof (must fail): duplicate any one heading, e.g. change the `## `
    branch of the renderer to call doc.add_heading twice.
    Observed: 2 failed (loan, nmtc).
    """
    doc = _save(any_deal, tmp_path)
    md = render_markdown(any_deal)
    md_headings = []
    for line in md.split("\n"):
        match = _MD_HEADING.match(line)
        if match:
            md_headings.append(_strip_emphasis(match.group(2)))
    docx_headings = [
        p.text.strip() for p in doc.paragraphs
        if p.style.name == "Title" or p.style.name.startswith("Heading")
    ]
    assert md_headings, "no headings — this gate would pass vacuously"
    assert Counter(docx_headings) == Counter(md_headings)
    duplicated = [h for h, n in Counter(docx_headings).items() if n > 1]
    assert not duplicated, f"heading rendered more than once: {duplicated}"


def test_g2_the_first_heading_is_the_title_style(any_deal, tmp_path):
    """
    The memo title takes Word's Title style — one paragraph for one Markdown
    heading. R5 permits styling the first `# ` as Title; it forbids emitting a
    Title paragraph *and* the heading.
    """
    doc = _save(any_deal, tmp_path)
    headings = [p for p in doc.paragraphs
                if p.style.name == "Title" or p.style.name.startswith("Heading")]
    assert headings[0].style.name == "Title"
    assert [p.style.name for p in headings].count("Title") == 1
    md_first = render_markdown(any_deal).split("\n")[0]
    assert headings[0].text == _MD_HEADING.match(md_first).group(2)


def test_g3_table_structure_matches_the_markdown(any_deal, tmp_path):
    """
    G3 — table structure. Table count, and each table's row and column counts.

    Red-proof (must fail): emit one extra table, e.g. call _add_table twice for
    each block.
    Observed: 2 failed (loan, nmtc) — plus 8 more across G1 and the
    conservation gates.
    """
    doc = _save(any_deal, tmp_path)
    md_shape = [(len(b), len(b[0])) for b in _markdown_blocks(any_deal)]
    docx_shape = [(len(t.rows), len(t.columns)) for t in doc.tables]
    assert md_shape, "no tables — this gate would pass vacuously"
    assert docx_shape == md_shape


def test_docx_carries_the_deal_metadata_exactly_once(any_deal, tmp_path):
    """
    The independent anchor, replacing the three gates that used to hold the
    hand-built header table in place.

    Fund / Prepared By / Date / IC Date are checked against the DealProfile
    itself, not against the renderer. Each must be present, and must appear as
    many times as the Markdown says — not the extra time 0.2.0 added.

    The Markdown itself restates some of this metadata (the header block, the
    Executive Summary and the signature block), so the expected count is read
    off the Markdown rather than assumed to be one.
    """
    doc = _save(any_deal, tmp_path)
    atoms = _docx_atoms(doc)
    md_atoms = _md_atoms(any_deal)
    for label, source in METADATA_SOURCE.items():
        value = source(any_deal)
        if not value:
            continue
        rendered = f"{label} {value}"
        expected = md_atoms.count(rendered)
        assert expected >= 1, f"{rendered!r} is not in the Markdown at all"
        assert atoms.count(rendered) == expected, (
            f"{rendered!r} appears {atoms.count(rendered)} times in the .docx, "
            f"{expected} times in the Markdown"
        )


# ── G18 — the Word file's own metadata comes from the deal ───────────────────
#
# Measured on the published 0.2.1 wheel: every .docx this package had ever
# written reported author='python-docx', created=modified=2013-12-23T23:15Z and
# title='', because save_docx never touched core properties and python-docx's
# default template populates them.
#
# A credit memo goes into a loan file, and loan files get examined. Every
# document management system sorts and filters on that date and it is false for
# every memo in the folder. It is also a fidelity defect under this package's
# own invariant: the metadata asserted a creation date that the prepared_date
# on page one contradicted.
#
# EVERY GATE BELOW READS THE PROPERTIES BACK OUT OF A SAVED FILE. None of them
# asserts that a setter was called.

#: python-docx's template defaults, written out here so the gates can name what
#: they are refusing rather than compare against the renderer.
TEMPLATE_AUTHOR = "python-docx"
TEMPLATE_CREATED_YEAR = 2013


def test_g18_the_template_defaults_are_what_they_are_claimed_to_be():
    """
    Guard the guard. If a future python-docx shipped a template with no author
    and no creation date, every gate below would pass on a renderer that sets
    nothing at all.
    """
    bare = docx.Document()
    assert bare.core_properties.author == TEMPLATE_AUTHOR
    assert bare.core_properties.created is not None
    assert bare.core_properties.created.year == TEMPLATE_CREATED_YEAR
    assert bare.core_properties.title == ""


def test_g18_core_properties_come_from_the_deal(any_deal, tmp_path):
    """
    G18. author from `prepared_by`, title from `deal_name`, created and
    modified from `prepared_date`. Read back out of the saved file.

    Red-proof (must fail): delete the `_set_core_properties(doc, deal)` call
    from `creditmemo.renderers.docx.render`.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: 17 failed — this gate on both deals, the no-defaults gate on
    both, all 5 readable-date cases, all 6 unreadable-date cases, and the two
    single-deal gates. Nothing outside G18 sees it: the memo's text is
    unchanged, so every content, heading and conservation gate stays green.
    """
    document = _save(any_deal, tmp_path)
    properties = document.core_properties
    assert properties.author == any_deal.prepared_by
    assert properties.title == any_deal.deal_name
    assert properties.created is not None
    assert (properties.created.year, properties.created.month,
            properties.created.day) == (2026, 5, 6), any_deal.prepared_date
    assert properties.modified == properties.created


def test_g18_no_saved_memo_reports_the_python_docx_defaults(any_deal, tmp_path):
    """
    The refusal half, stated as two independent facts rather than one. Checked
    in the file's bytes as well as through the API, because a property can be
    set on the object and still be written from the template part.
    """
    path = str(tmp_path / "defaults.docx")
    CreditMemo(any_deal).save_docx(path)
    properties = Document(path).core_properties
    assert properties.author != TEMPLATE_AUTHOR
    assert properties.created.year != TEMPLATE_CREATED_YEAR

    import zipfile
    core = zipfile.ZipFile(path).read("docProps/core.xml").decode("utf-8")
    assert f">{TEMPLATE_AUTHOR}<" not in core, core
    assert str(TEMPLATE_CREATED_YEAR) not in core, core


@pytest.mark.parametrize("prepared_date,expected", [
    ("2026-05-06",   (2026, 5, 6)),
    ("2026/05/06",   (2026, 5, 6)),
    ("May 6, 2026",  (2026, 5, 6)),
    ("6 May 2026",   (2026, 5, 6)),
    ("2026-05-06T14:30:00", (2026, 5, 6)),
])
def test_g18_a_readable_prepared_date_becomes_the_creation_date(
    sample_deal, prepared_date, expected, tmp_path
):
    """Several spellings of the same day, all read back out of the file."""
    sample_deal.prepared_date = prepared_date
    properties = _save(sample_deal, tmp_path,
                       name=f"d{abs(hash(prepared_date))}.docx").core_properties
    assert (properties.created.year, properties.created.month,
            properties.created.day) == expected
    assert properties.modified == properties.created


@pytest.mark.parametrize("prepared_date", [
    "next Tuesday", "", "   ", "Q2 2026", "05/06/2026", "2026-13-45",
])
def test_g18_an_unreadable_prepared_date_leaves_the_dates_unset(
    sample_deal, prepared_date, tmp_path
):
    """
    `prepared_date` is a free-form `str`. An unreadable one is not guessed at
    and does not raise — and "unset" means the property is genuinely absent,
    not left at the template's 2013 date, which is the false date this gate
    exists to remove. python-docx cannot clear a core datetime
    (`cp.created = None` raises), so the element is removed.

    `05/06/2026` is here on purpose: reading it requires choosing between 5
    June and 6 May, and choosing is the silent interpretation this package
    refuses elsewhere.

    Red-proof (must fail): make `parse_prepared_date` fall back to
    `datetime.datetime.now()` — the "just put something plausible there"
    mutation, which is the one a future reader is most likely to make.
    Observed: 6 failed — every case here, and nothing else in the suite.
    """
    sample_deal.prepared_date = prepared_date
    path = str(tmp_path / f"u{abs(hash(prepared_date))}.docx")
    CreditMemo(sample_deal).save_docx(path)
    properties = Document(path).core_properties
    assert properties.created is None, properties.created
    assert properties.modified is None, properties.modified
    # And not the template's date by another route.
    import zipfile
    core = zipfile.ZipFile(path).read("docProps/core.xml").decode("utf-8")
    assert "dcterms:created" not in core, core
    assert str(TEMPLATE_CREATED_YEAR) not in core, core
    # The memo itself was still written.
    assert len(Document(path).tables) > 0


def test_g18_an_unreadable_prepared_date_still_sets_author_and_title(
    sample_deal, tmp_path
):
    """The date is the only property the free-form field can withhold."""
    sample_deal.prepared_date = "sometime in the spring"
    properties = _save(sample_deal, tmp_path, name="partial.docx").core_properties
    assert properties.author == sample_deal.prepared_by
    assert properties.title == sample_deal.deal_name
    assert properties.author != TEMPLATE_AUTHOR


def test_g18_the_metadata_follows_the_deal_it_was_given(sample_deal, tmp_path):
    """
    Anchored against the DealProfile, not against a fixed string: two different
    deals must produce two different sets of properties.
    """
    sample_deal.prepared_by = "A. Different Underwriter"
    sample_deal.deal_name = "Northside Facility — $4.1MM Acquisition Loan"
    sample_deal.prepared_date = "2031-02-28"
    properties = _save(sample_deal, tmp_path, name="other.docx").core_properties
    assert properties.author == "A. Different Underwriter"
    assert properties.title == "Northside Facility — $4.1MM Acquisition Loan"
    assert (properties.created.year, properties.created.month,
            properties.created.day) == (2031, 2, 28)


# ── G21 — a property the deal does not state is absent, not the word "None" ──
#
# 0.2.2 is the release that started writing core properties at all, so a Word
# Author reading literally `None` is this release's doing. `prepared_by` and
# `deal_name` are declared `str` and neither is validated, so `None` reaches
# the renderer through the ordinary field-by-field build R20's comment
# describes. Measured on the 0.2.2 wheel:
#
#     prepared_by=None  -> <dc:creator>None</dc:creator>
#     deal_name=None    -> <dc:title>None</dc:title>
#     prepared_by=''    -> <dc:creator></dc:creator>
#
# The posture is Item 5's, unchanged: not written, not substituted for, not
# raised on. The element is removed, because *not setting* it leaves
# python-docx's template default — `python-docx` as the author — which is the
# false metadata 0.2.2 exists to remove.

#: The values that state nothing. `is_supplied`'s three cases, written out here
#: rather than imported, so this gate does not follow the predicate it is
#: holding.
UNSTATED_VALUES = [None, "", "   "]


def _core_xml(path):
    import zipfile
    return zipfile.ZipFile(path).read("docProps/core.xml").decode("utf-8")


@pytest.mark.parametrize("value", UNSTATED_VALUES,
                         ids=["none", "empty", "whitespace"])
def test_g21_an_unstated_prepared_by_leaves_the_author_absent(
    sample_deal, value, tmp_path
):
    """
    G21. Read out of the saved file, twice: through python-docx, and in the
    bytes of `docProps/core.xml`, because a property can read one way through
    the API and be written another way into the part.

    Red-proof (must fail): restore `properties.author = deal.prepared_by` in
    `creditmemo.renderers.docx._set_core_properties`.
    """
    sample_deal.prepared_by = value
    path = str(tmp_path / f"author{UNSTATED_VALUES.index(value)}.docx")
    CreditMemo(sample_deal).save_docx(path)
    core = _core_xml(path)

    assert "dc:creator" not in core, core
    assert ">None<" not in core, core
    assert f">{TEMPLATE_AUTHOR}<" not in core, core
    assert Document(path).core_properties.author == ""
    # And the memo itself was still written; nothing raised.
    assert len(Document(path).tables) > 0


@pytest.mark.parametrize("value", UNSTATED_VALUES,
                         ids=["none", "empty", "whitespace"])
def test_g21_an_unstated_deal_name_leaves_the_title_absent(
    sample_deal, value, tmp_path
):
    """Same rule, same posture, the other text property."""
    sample_deal.deal_name = value
    path = str(tmp_path / f"title{UNSTATED_VALUES.index(value)}.docx")
    CreditMemo(sample_deal).save_docx(path)
    core = _core_xml(path)

    assert "dc:title" not in core, core
    assert ">None<" not in core, core
    assert Document(path).core_properties.title == ""
    assert len(Document(path).tables) > 0


def test_g21_a_stated_author_and_title_are_still_written(sample_deal, tmp_path):
    """
    Guard the guard. A renderer that removed both elements unconditionally
    would pass every case above, and would undo G18.
    """
    path = str(tmp_path / "stated.docx")
    CreditMemo(sample_deal).save_docx(path)
    core = _core_xml(path)
    properties = Document(path).core_properties
    assert properties.author == sample_deal.prepared_by
    assert properties.title == sample_deal.deal_name
    assert "dc:creator" in core
    assert "dc:title" in core


def test_g21_the_body_still_renders_what_it_always_rendered(sample_deal):
    """
    The scope line, gated. The memo *body* has printed `None` for an unstated
    `prepared_by` since before 0.2.2; that is a disclosed defect whose fix is
    0.3.0, and this release fixes the metadata only. If a later round changes
    the body, this gate reddens and the disclosure gets revisited on purpose
    rather than going quietly stale.
    """
    sample_deal.prepared_by = None
    md = CreditMemo(sample_deal).to_markdown()
    assert "**Prepared By:** None" in md


# ── The README's prepared_date table is what the parser does ─────────────────

#: The header row of the README table this gate reads. The spellings are not
#: duplicated here: a list written into the test is a third copy that can agree
#: with neither the README nor the parser.
PREPARED_DATE_TABLE_HEADER = "| `prepared_date` written as | Read as a date |"


def _readme_prepared_date_rows():
    """[(spelling, "yes"|"no")] as README.md states them, in document order."""
    lines = io.open(README, encoding="utf-8").read().split("\n")
    start = lines.index(PREPARED_DATE_TABLE_HEADER)
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append((cells[0].strip("`"), cells[1]))
    return rows


def test_the_readme_date_table_states_what_the_parser_does():
    """
    Item 1. README.md said `prepared_date` was read when written as
    `2026-05-06`, `2026/05/06`, `May 6, 2026`, `6 May 2026`, "or those with a
    time". Measured on the 0.2.2 wheel, only the ISO forms take a time:

        '2026-05-06 09:30:00'   -> 2026-05-06 09:30:00
        '2026-05-06T09:30:00'   -> 2026-05-06 09:30:00
        'May 6, 2026 09:30'     -> None
        '6 May 2026 09:30'      -> None
        '2026/05/06 09:30:00'   -> None

    It fails safe — the property is left unset, never guessed — so nothing
    wrong reached a document, but the prose was false. The prose is now a table
    and this reads it back out of the file, in **both** directions: a spelling
    the README calls readable must parse, and one it calls unreadable must not.

    Red-proof (must fail): add `"%Y/%m/%d %H:%M:%S"` to
    `creditmemo.renderers.docx.PREPARED_DATE_FORMATS` — the widening this round
    declined — or delete `"%d %B %Y"` from it.
    """
    rows = _readme_prepared_date_rows()
    assert len(rows) >= 10, rows
    assert any(claim == "yes" for _, claim in rows), rows
    assert any(claim == "no" for _, claim in rows), rows

    wrong = []
    for spelling, claim in rows:
        parsed = parse_prepared_date(spelling)
        if (parsed is not None) != (claim == "yes"):
            wrong.append((spelling, claim, parsed))
    assert not wrong, (
        "README.md and parse_prepared_date disagree (spelling, README, "
        f"parsed): {wrong}")


def test_the_readme_time_claim_holds():
    """
    The narrowed claim itself: **a time of day is read only after the ISO
    `YYYY-MM-DD` date.** Every time-bearing spelling the README calls readable
    must be ISO-dated, and the time must survive into the parsed value — a
    parser that silently dropped the clock would pass the table gate above.

    Red-proof (must fail): add `"%B %d, %Y %H:%M"` to PREPARED_DATE_FORMATS.
    """
    rows = _readme_prepared_date_rows()
    with_time = [(s, c) for s, c in rows if ":" in s]
    assert with_time, rows
    readable = [s for s, c in with_time if c == "yes"]
    unreadable = [s for s, c in with_time if c == "no"]
    assert readable, "no time-bearing spelling is documented as readable"
    assert unreadable, "the gate has no negative case"

    for spelling in readable:
        assert re.match(r"^\d{4}-\d{2}-\d{2}[T ]", spelling), spelling
        parsed = parse_prepared_date(spelling)
        assert (parsed.hour, parsed.minute) == (9, 30), (spelling, parsed)

    assert "A time of day is read only after the ISO" in io.open(
        README, encoding="utf-8").read()
