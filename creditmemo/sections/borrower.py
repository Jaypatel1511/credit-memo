"""Borrower Profile section generator."""
from creditmemo.data.schema import DealProfile, BORROWER_TYPES, SECTORS


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

    if b.year_founded:
        lines.append(f"**Year Founded:** {b.year_founded}")
    if b.ceo_name:
        lines.append(f"**CEO/Executive Director:** {b.ceo_name}")
    if b.website:
        lines.append(f"**Website:** {b.website}")

    lines.append("")

    certifications = []
    if b.is_cdfi_certified:
        certifications.append("CDFI Certified")
    if b.is_mdi:
        certifications.append("Minority Depository Institution (MDI)")
    if certifications:
        lines.append(f"**Certifications:** {', '.join(certifications)}")
        lines.append("")

    if b.mission:
        lines += ["### Mission", "", b.mission, ""]

    if b.description:
        lines += ["### Organization Description", "", b.description, ""]

    if b.total_assets or b.annual_revenue:
        lines.append("### Financial Snapshot")
        lines.append("")
        if b.total_assets:
            lines.append(f"- **Total Assets:** ${b.total_assets/1e6:.1f}MM")
        if b.annual_revenue:
            lines.append(f"- **Annual Revenue:** ${b.annual_revenue/1e6:.1f}MM")
        lines.append("")

    return "\n".join(lines)
