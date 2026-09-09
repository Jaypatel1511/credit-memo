"""Render credit memo to Word .docx format."""
import re

from creditmemo.data.schema import DealProfile
from creditmemo.renderers.markdown import render as render_markdown
from creditmemo.tables import block_to_rows, iter_segments

#: Word style used for every generated table. "Table Grid" ships with the
#: default python-docx template, so no external template is required. The
#: README documents this style and the bold header row; both are gated.
TABLE_STYLE = "Table Grid"

#: Word's built-in list styles, used instead of literal list markers in body
#: text. Before 0.2.1 the Conditions of Approval arrived as ordinary paragraphs
#: whose text began with a literal "1. ", so Word saw no list at all.
BULLET_STYLE = "List Bullet"
NUMBER_STYLE = "List Number"

#: A Markdown ordered-list item: "1. Receipt of final appraisal".
_ORDERED_ITEM = re.compile(r"^(\d+)\.\s+(.*)$")


def _clean(text: str) -> str:
    """
    Strip Markdown emphasis markers from text bound for a Word run.

    Applied to every text branch. Before 0.2.1 only the plain-paragraph branch
    did this, so a bullet such as ``- **Total Assets:** $8.0MM`` reached Word as
    the literal characters ``**Total Assets:** $8.0MM`` — raw Markdown syntax,
    in the document handed to an Investment Committee.
    """
    return text.replace("**", "").replace("*", "")

#: The horizontal rule the Markdown renderer emits between sections. Matched
#: exactly, not by prefix: ``startswith("---")`` also matched underwriter prose
#: such as "--- see appendix" and replaced the whole sentence with a rule,
#: deleting the text from the Word document without a word on any stream.
RULE_LINE = "---"


def _add_rule(doc) -> None:
    """
    Append a horizontal rule as an empty paragraph with a bottom border.

    Before 0.2.1 this was a paragraph containing sixty literal underscores,
    which is a row of underscores in Word, not a rule: it does not span the
    column, does not follow the page margins, and is selectable text that lands
    in any copy-paste of the memo.
    """
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    paragraph = doc.add_paragraph()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "auto")
    borders.append(bottom)
    paragraph._p.get_or_add_pPr().append(borders)


def _add_table(doc, block) -> None:
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

    The document is a pure function of the Markdown the same deal produces:
    every heading, paragraph, list item, rule and table in the .docx comes from
    a line of that Markdown, and nothing is added that has no line behind it.

    Before 0.2.1 the renderer built a cover block by hand — a ``Title``
    paragraph, an ``H1`` of the deal name and a four-row metadata table read
    straight off the ``DealProfile`` — and *then* parsed the Markdown, which
    carries all three of those things itself. The memo title, the deal name and
    the Fund/Prepared By/Date/IC Date block therefore appeared twice in every
    Word memo the package has ever produced, the second time in a different
    shape from the first. The hand-built block is gone; the first ``#`` heading
    simply takes Word's ``Title`` style.

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

    md_content = render_markdown(deal)

    # iter_segments groups contiguous table lines into blocks and hands back
    # everything else line by line, in order. It is the same grouping the
    # conservation gates count with, so there is only one such rule in the
    # package.
    seen_title = False
    for kind, payload in iter_segments(md_content.split("\n")):
        if kind == "table":
            _add_table(doc, payload)
            continue

        line = payload
        if line.startswith("# "):
            if not seen_title:
                # The memo's own title, in Word's Title style — one paragraph
                # for one Markdown heading, not a synthesised second copy.
                heading = doc.add_heading(_clean(line[2:]), 0)
                heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
                seen_title = True
            else:
                doc.add_heading(_clean(line[2:]), 1)
        elif line.startswith("## "):
            doc.add_heading(_clean(line[3:]), 2)
        elif line.startswith("### "):
            doc.add_heading(_clean(line[4:]), 3)
        elif line.strip() == RULE_LINE:
            _add_rule(doc)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(_clean(line[2:]), style=BULLET_STYLE)
        elif _ORDERED_ITEM.match(line):
            doc.add_paragraph(_clean(_ORDERED_ITEM.match(line).group(2)),
                              style=NUMBER_STYLE)
        elif line:
            clean = _clean(line)
            if clean.strip():
                doc.add_paragraph(clean)

    doc.save(path)
    print(f"Credit memo saved to {path}")
