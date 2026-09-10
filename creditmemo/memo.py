"""
CreditMemo — main public API for credit memo generation.
"""
from creditmemo.data.schema import DealProfile
from creditmemo.renderers.markdown import (
    SECTIONS, render as render_md, save as save_md,
)
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
        """
        Return the number of sections in the memo.

        F16. This counted occurrences of ``"\\n## "`` in the rendered Markdown,
        so it was a property of the memo's *text* and not of its structure. The
        memo reproduces caller prose verbatim — that is the whole point of the
        input-fidelity work — so a ``## `` line inside ``deal_summary``, a
        mission or an impact narrative was counted as a section, and a
        seven-section memo reported eight. It is the length of
        :data:`creditmemo.renderers.markdown.SECTIONS`, which is the tuple the
        renderer itself iterates; no input can move it.
        """
        return len(SECTIONS)
