"""
CreditMemo — main public API for credit memo generation.
"""
from creditmemo.data.schema import DealProfile
from creditmemo.renderers.markdown import render as render_md, save as save_md
from creditmemo.renderers.docx import render as render_docx


class CreditMemo:
    """
    Generate IC credit memos from structured deal inputs.

    Usage:
        from creditmemo import CreditMemo, DealProfile

        memo = CreditMemo(deal)
        print(memo.to_markdown())
        memo.save_markdown("memo.md")
        memo.save_docx("memo.docx")
    """

    def __init__(self, deal: DealProfile):
        if not isinstance(deal, DealProfile):
            raise TypeError("CreditMemo requires a DealProfile instance.")
        self.deal = deal

    def to_markdown(self) -> str:
        """Return the full credit memo as a Markdown string."""
        return render_md(self.deal)

    def save_markdown(self, path: str) -> None:
        """Save the credit memo to a Markdown file."""
        save_md(self.deal, path)

    def save_docx(self, path: str) -> None:
        """Save the credit memo to a Word .docx file."""
        render_docx(self.deal, path)

    def preview(self, lines: int = 50) -> None:
        """Print the first N lines of the memo to the console."""
        content = self.to_markdown()
        for line in content.split("\n")[:lines]:
            print(line)

    def section_count(self) -> int:
        """Return the number of sections in the memo."""
        return self.to_markdown().count("\n## ")
