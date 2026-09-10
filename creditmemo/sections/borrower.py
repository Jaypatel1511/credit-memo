"""Borrower Profile section generator."""
from creditmemo import fields
from creditmemo.data.schema import DealProfile, BORROWER_TYPES, SECTORS
from creditmemo.money import money

#: (attribute, affirmative, negative) for the tri-state certification flags, in
#: field order. Each flag carries its own negative string rather than borrowing
#: the affirmative one under a negating header: "**Not certified:** CDFI
#: Certified" is a line that contradicts itself, and it reaches the Word
#: document as the sentence "Not certified: CDFI Certified" — the emphasis
#: markers are flattened on the way, so it is one plain run, not a bold one a
#: reader could skim past. Same shape as impact.TARGET_MARKET_FLAGS.
CERTIFICATION_FLAGS = (
    ("is_cdfi_certified", "CDFI Certified",       "Not CDFI certified"),
    ("is_mdi",            "Minority Depository Institution (MDI)",
                          "Not a Minority Depository Institution (MDI)"),
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

    Each line negates itself. Gated by G8.
    """
    lines = []
    for attr, yes, no in CERTIFICATION_FLAGS:
        value = getattr(b, attr)
        if value is True:
            lines.append(f"- ✅ {yes}")
        elif value is False:
            lines.append(f"- ❌ {no}")
    if not lines:
        return [NO_CERTIFICATION_FLAGS_TEXT, ""]
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
    if fields.is_supplied(b.ceo_name):
        lines.append(f"**CEO/Executive Director:** {b.ceo_name}")
    if fields.is_supplied(b.website):
        lines.append(f"**Website:** {b.website}")

    lines.append("")
    lines.append("### Certifications & Designations")
    lines.append("")
    lines += _certification_lines(b)

    if fields.is_supplied(b.mission):
        lines += ["### Mission", "", b.mission, ""]

    if fields.is_supplied(b.description):
        lines += ["### Organization Description", "", b.description, ""]

    # `is not None`, not truthiness: a borrower with total assets of exactly $0
    # supplied that figure, and it is more material than most.
    #
    # R24. These two were the coarsest money sites in the package: `$MM` at
    # *one* decimal resolves to $100,000, so `total_assets=49_000` rendered
    # `$0.0MM` — the stated-zero rendering, for a figure ten times larger than
    # the one the two-decimal sites lost. They go through the same formatter as
    # every other dollar figure now.
    if b.total_assets is not None or b.annual_revenue is not None:
        lines.append("### Financial Snapshot")
        lines.append("")
        if b.total_assets is not None:
            lines.append(f"- **Total Assets:** {money(b.total_assets)}")
        if b.annual_revenue is not None:
            lines.append(f"- **Annual Revenue:** {money(b.annual_revenue)}")
        lines.append("")

    return "\n".join(lines)
