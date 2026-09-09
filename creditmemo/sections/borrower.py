"""Borrower Profile section generator."""
from creditmemo.data.schema import DealProfile, BORROWER_TYPES, SECTORS

#: (attribute, label) for the tri-state certification flags, in field order.
CERTIFICATION_FLAGS = (
    ("is_cdfi_certified", "CDFI Certified"),
    ("is_mdi", "Minority Depository Institution (MDI)"),
)

#: What the block says when every certification flag is ``None``.
NO_CERTIFICATION_FLAGS_TEXT = (
    "No certification or designation flags were provided."
)


def _certification_lines(b) -> list:
    """
    Render the tri-state certification flags.

    ``True`` affirms, ``False`` states the negative explicitly, ``None`` says
    nothing. Before 0.2.1 these were plain ``bool`` defaulting to ``False``, so
    "we checked, and this borrower is not CDFI certified" and "nobody filled
    this in" produced byte-identical memos.
    """
    held = [label for attr, label in CERTIFICATION_FLAGS
            if getattr(b, attr) is True]
    not_held = [label for attr, label in CERTIFICATION_FLAGS
                if getattr(b, attr) is False]

    if not held and not not_held:
        return [NO_CERTIFICATION_FLAGS_TEXT, ""]

    lines = []
    if held:
        lines.append(f"**Certifications:** {', '.join(held)}")
    if not_held:
        lines.append(f"**Not certified:** {', '.join(not_held)}")
    lines.append("")
    return lines


def generate(deal: DealProfile) -> str:
    b = deal.borrower

    lines = [
        "## Borrower Profile",
        "",
        f"**Organization:** {b.name}",
        f"**Type:** {BORROWER_TYPES.get(b.borrower_type, b.borrower_type)}",
        f"**Sector:** {SECTORS.get(b.sector, b.sector)}",
        f"**Location:** {b.city}, {b.state}",
    ]

    if b.year_founded is not None:
        lines.append(f"**Year Founded:** {b.year_founded}")
    if b.ceo_name:
        lines.append(f"**CEO/Executive Director:** {b.ceo_name}")
    if b.website:
        lines.append(f"**Website:** {b.website}")

    lines.append("")
    lines += _certification_lines(b)

    if b.mission:
        lines += ["### Mission", "", b.mission, ""]

    if b.description:
        lines += ["### Organization Description", "", b.description, ""]

    # `is not None`, not truthiness: a borrower with total assets of exactly $0
    # supplied that figure, and it is more material than most.
    if b.total_assets is not None or b.annual_revenue is not None:
        lines.append("### Financial Snapshot")
        lines.append("")
        if b.total_assets is not None:
            lines.append(f"- **Total Assets:** ${b.total_assets/1e6:.1f}MM")
        if b.annual_revenue is not None:
            lines.append(f"- **Annual Revenue:** ${b.annual_revenue/1e6:.1f}MM")
        lines.append("")

    return "\n".join(lines)
