"""IC Recommendation section generator."""
from creditmemo.data.schema import DealProfile, RECOMMENDATIONS


def generate(deal: DealProfile) -> str:
    lines = [
        "## IC Recommendation",
        "",
        f"**Recommendation:** {deal.recommendation_text.upper()}",
        "",
    ]

    if deal.conditions:
        lines += ["### Conditions of Approval", ""]
        for i, cond in enumerate(deal.conditions, 1):
            lines.append(f"{i}. {cond}")
        lines.append("")

    lines += [
        "### Approval",
        "",
        f"Prepared by: {deal.prepared_by}",
        f"Date: {deal.prepared_date}",
        "",
        "| Role | Name | Signature | Date |",
        "|------|------|-----------|------|",
        "| IC Chair | | | |",
        "| Credit Officer | | | |",
        "| Fund Manager | | | |",
        "",
    ]

    return "\n".join(lines)
