"""Render credit memo to Word .docx format."""
from typing import List

from creditmemo.data.schema import DealProfile
from creditmemo.renderers.markdown import render as render_markdown
from creditmemo.tables import block_to_rows, is_table_line

#: Word style used for every generated table. "Table Grid" ships with the
#: default python-docx template, so no external template is required.
TABLE_STYLE = "Table Grid"


def _add_table(doc, block: List[str]) -> None:
    """Append one Markdown table block to ``doc`` as a real Word table."""
    rows = block_to_rows(block)
    if not rows:
        return
    n_cols = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=n_cols)
    table.style = TABLE_STYLE
    for r, cells in enumerate(rows):
        for c, text in enumerate(cells):
            cell = table.rows[r].cells[c]
            cell.text = text
            if r == 0:
                # Header row: bold every run python-docx created for the text.
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
    doc.add_paragraph()


def render(deal: DealProfile, path: str) -> None:
    """
    Render a complete credit memo as a Word .docx file.

    Every Markdown table in the memo — deal summary, proposed terms, NMTC
    structure, financial summary, credit metrics, projections, impact metrics,
    risk factors and the signature block — is written as a real Word table.

    Requires python-docx: pip install python-docx

    Args:
        deal: DealProfile with all deal inputs
        path: Output path for the .docx file
    """
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise ImportError(
            "python-docx is required for Word output. "
            "Install it with: pip install python-docx"
        )

    doc = Document()

    # Title
    title = doc.add_heading("INVESTMENT COMMITTEE MEMORANDUM", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_heading(deal.deal_name, 1)

    # Header table — built directly from the deal, not from the Markdown.
    table = doc.add_table(rows=4, cols=2)
    table.style = TABLE_STYLE
    rows_data = [
        ("Fund:", deal.fund_name or "N/A"),
        ("Prepared By:", deal.prepared_by),
        ("Date:", deal.prepared_date),
        ("IC Date:", deal.ic_date or "TBD"),
    ]
    for i, (label, value) in enumerate(rows_data):
        table.rows[i].cells[0].text = label
        table.rows[i].cells[1].text = value

    doc.add_paragraph()

    # Render markdown and parse into docx
    md_content = render_markdown(deal)

    pending_table: List[str] = []

    def flush() -> None:
        if pending_table:
            _add_table(doc, list(pending_table))
            pending_table.clear()

    for line in md_content.split("\n"):
        if is_table_line(line):
            # Buffer contiguous table lines so the whole block becomes one table.
            pending_table.append(line)
            continue
        flush()

        if line.startswith("# "):
            doc.add_heading(line[2:], 1)
        elif line.startswith("## "):
            doc.add_heading(line[3:], 2)
        elif line.startswith("### "):
            doc.add_heading(line[4:], 3)
        elif line.startswith("---"):
            doc.add_paragraph("_" * 60)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line[2:], style="List Bullet")
        elif line:
            # Clean markdown bold markers
            clean = line.replace("**", "").replace("*", "")
            if clean.strip():
                doc.add_paragraph(clean)

    flush()

    doc.save(path)
    print(f"Credit memo saved to {path}")
