"""Render credit memo to Markdown format."""
from creditmemo.data.schema import DealProfile
from creditmemo.sections import (
    executive, borrower, transaction,
    financial, impact, risk, recommendation
)


def render(deal: DealProfile) -> str:
    """
    Render a complete credit memo as a Markdown string.

    Args:
        deal: DealProfile with all deal inputs

    Returns:
        Full credit memo as Markdown string
    """
    sections = [
        f"# Investment Committee Memorandum",
        f"# {deal.deal_name}",
        f"",
        f"**Fund:** {deal.fund_name or 'N/A'}",
        f"**Prepared By:** {deal.prepared_by}",
        f"**Date:** {deal.prepared_date}",
        f"**IC Date:** {deal.ic_date or 'TBD'}",
        f"",
        "---",
        "",
        executive.generate(deal),
        "---",
        "",
        borrower.generate(deal),
        "---",
        "",
        transaction.generate(deal),
        "---",
        "",
        financial.generate(deal),
        "---",
        "",
        impact.generate(deal),
        "---",
        "",
        risk.generate(deal),
        "---",
        "",
        recommendation.generate(deal),
    ]

    return "\n".join(sections)


def save(deal: DealProfile, path: str) -> None:
    """Save credit memo to a Markdown file."""
    content = render(deal)
    with open(path, "w") as f:
        f.write(content)
    print(f"Credit memo saved to {path}")
