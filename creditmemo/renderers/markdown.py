"""Render credit memo to Markdown format."""
from creditmemo import fields
from creditmemo.data.schema import DealProfile
from creditmemo.sections import (
    executive, borrower, transaction,
    financial, impact, risk, recommendation
)

#: The memo's sections, in document order. One module per ``## `` heading.
#:
#: F16. Declared as data because :meth:`creditmemo.memo.CreditMemo.section_count`
#: needs the *structure* of the memo and used to reach for its text instead,
#: counting occurrences of ``"\n## "`` in the rendered Markdown. A caller who
#: wrote a ``## `` line into any prose field — ``deal_summary``, a mission, an
#: impact narrative, all of which the memo reproduces verbatim by design —
#: inflated the count: a seven-section memo reported eight. The renderer now
#: iterates this tuple and the count is its length, so the two cannot disagree
#: and neither can be moved by an input.
SECTIONS = (
    executive, borrower, transaction,
    financial, impact, risk, recommendation,
)


def render(deal: DealProfile) -> str:
    """
    Render a complete credit memo as a Markdown string.

    Args:
        deal: DealProfile with all deal inputs

    Returns:
        Full credit memo as Markdown string
    """
    parts = [
        f"# Investment Committee Memorandum",
        f"# {deal.deal_name}",
        f"",
        f"**Fund:** {fields.or_placeholder(deal.fund_name, 'N/A')}",
        f"**Prepared By:** {deal.prepared_by}",
        f"**Date:** {deal.prepared_date}",
        f"**IC Date:** {fields.or_placeholder(deal.ic_date, 'TBD')}",
        f"",
    ]
    for section in SECTIONS:
        parts += ["---", "", section.generate(deal)]

    return "\n".join(parts)


def save(deal: DealProfile, path: str) -> None:
    """Save credit memo to a Markdown file."""
    content = render(deal)
    with open(path, "w") as f:
        f.write(content)
    print(f"Credit memo saved to {path}")
