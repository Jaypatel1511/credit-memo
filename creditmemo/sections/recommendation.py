"""IC Recommendation section generator."""
from creditmemo import fields
from creditmemo.data.schema import DealProfile, RECOMMENDATIONS


def generate(deal: DealProfile) -> str:
    lines = [
        "## IC Recommendation",
        "",
        f"**Recommendation:** {deal.recommendation_text.upper()}",
        "",
    ]

    # `supplied_items`, not `deal.conditions`: an element that states nothing
    # rendered as a bare number under a heading an Investment Committee reads
    # as the conditions of approval. F11; see creditmemo.fields.
    conditions = fields.supplied_items(deal.conditions)
    if conditions:
        lines += ["### Conditions of Approval", ""]
        for i, cond in enumerate(conditions, 1):
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
