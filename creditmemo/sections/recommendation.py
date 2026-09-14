"""IC Recommendation section generator."""
from creditmemo import fields
from creditmemo.data.schema import (
    CONDITIONAL_APPROVAL, CONDITIONS_HEADING,
    CONDITIONS_NOT_AN_APPROVAL_TEXT, DealProfile, RECOMMENDATIONS,
)


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
        # The heading is keyed by recommendation. Through 0.2.1 it was the
        # literal "### Conditions of Approval" under every one of the four,
        # including `decline` — a heading naming the terms of an approval, over
        # a numbered list, in a memo that refuses the deal.
        #
        # RELABELLED RATHER THAN REFUSED. Raising at construction when
        # `conditions` is supplied under a non-conditional recommendation was
        # the other candidate. It is a behaviour change for an existing caller
        # — code that builds a declined memo with conditions works today and
        # would stop working on upgrade — and this release's constraint is that
        # nothing an existing caller does breaks. It is also the wrong refusal:
        # recording the stipulations that went with a decline is a legitimate
        # thing for an underwriter to do, and the package has no standing to
        # forbid it. Dropping the conditions silently was never a candidate: a
        # caller who supplied them must not find them missing.
        lines += [f"### {CONDITIONS_HEADING[deal.recommendation]}", ""]
        if deal.recommendation != CONDITIONAL_APPROVAL:
            lines += [CONDITIONS_NOT_AN_APPROVAL_TEXT, ""]
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
