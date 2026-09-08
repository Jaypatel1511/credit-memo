"""Executive Summary section generator."""
from creditmemo.data.schema import DealProfile, DEAL_TYPES, SECTORS
from creditmemo.tables import escape_cell


def generate(deal: DealProfile) -> str:
    b = deal.borrower
    lt = deal.loan_terms
    rate_str = f"{lt.interest_rate*100:.2f}%" if lt.interest_rate else "N/A"
    term_str = f"{lt.term_years} years" if lt.term_years else "N/A"

    lines = [
        "## Executive Summary",
        "",
        f"**Deal Name:** {deal.deal_name}",
        f"**Prepared By:** {deal.prepared_by}",
        f"**Date:** {deal.prepared_date}",
        f"**IC Date:** {deal.ic_date or 'TBD'}",
        "",
        "### Recommendation",
        "",
        f"**{deal.recommendation_text.upper()}**",
        "",
    ]

    if deal.conditions:
        lines.append("**Subject to the following conditions:**")
        for cond in deal.conditions:
            lines.append(f"- {cond}")
        lines.append("")

    lines += [
        "### Deal Summary",
        "",
        f"| Item | Details |",
        f"|------|---------|",
        f"| Borrower | {escape_cell(b.name)} |",
        f"| Borrower Type | {escape_cell(b.borrower_type.replace('_', ' ').title())} |",
        f"| Sector | {escape_cell(SECTORS.get(b.sector, b.sector))} |",
        f"| Location | {escape_cell(b.city)}, {escape_cell(b.state)} |",
        f"| Deal Type | {escape_cell(DEAL_TYPES.get(lt.deal_type, lt.deal_type))} |",
        f"| Amount | ${lt.amount_mm:.2f}MM |",
        f"| Interest Rate | {rate_str} |",
        f"| Term | {term_str} |",
        f"| Use of Proceeds | {escape_cell(lt.use_of_proceeds or 'See Transaction Structure')} |",
        "",
    ]

    if deal.deal_summary:
        lines += [deal.deal_summary, ""]

    return "\n".join(lines)
