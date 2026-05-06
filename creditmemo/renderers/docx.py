"""Render credit memo to Word .docx format."""
from creditmemo.data.schema import DealProfile
from creditmemo.renderers.markdown import render as render_markdown


def render(deal: DealProfile, path: str) -> None:
    """
    Render a complete credit memo as a Word .docx file.

    Requires python-docx: pip install python-docx

    Args:
        deal: DealProfile with all deal inputs
        path: Output path for the .docx file
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches
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

    # Header table
    table = doc.add_table(rows=4, cols=2)
    table.style = "Table Grid"
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

    for line in md_content.split("\n"):
        if line.startswith("# "):
            doc.add_heading(line[2:], 1)
        elif line.startswith("## "):
            doc.add_heading(line[3:], 2)
        elif line.startswith("### "):
            doc.add_heading(line[4:], 3)
        elif line.startswith("---"):
            doc.add_paragraph("_" * 60)
        elif line.startswith("| ") and "|" in line[1:]:
            # Table row — skip (already rendered in markdown)
            pass
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line[2:], style="List Bullet")
        elif line and not line.startswith("|"):
            # Clean markdown bold markers
            clean = line.replace("**", "").replace("*", "")
            if clean.strip():
                doc.add_paragraph(clean)

    doc.save(path)
    print(f"Credit memo saved to {path}")
