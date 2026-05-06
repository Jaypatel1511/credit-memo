"""Impact Analysis section generator."""
from creditmemo.data.schema import DealProfile


def generate(deal: DealProfile) -> str:
    imp = deal.impact_data

    lines = [
        "## Impact Analysis",
        "",
        "### Community Impact Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Jobs Created | {imp.jobs_created:,} |",
        f"| Jobs Retained | {imp.jobs_retained:,} |",
        f"| Total Jobs | {imp.jobs_created + imp.jobs_retained:,} |",
    ]

    if imp.affordable_units:
        lines.append(f"| Affordable Units | {imp.affordable_units:,} |")
    if imp.sq_ft_community_space:
        lines.append(f"| Community Space (sq ft) | {imp.sq_ft_community_space:,.0f} |")
    if imp.patients_served:
        lines.append(f"| Patients Served | {imp.patients_served:,} |")
    if imp.students_served:
        lines.append(f"| Students Served | {imp.students_served:,} |")
    if imp.businesses_supported:
        lines.append(f"| Businesses Supported | {imp.businesses_supported:,} |")

    if deal.loan_terms.amount > 0:
        total_jobs = imp.jobs_created + imp.jobs_retained
        if total_jobs > 0:
            cost_per_job = deal.loan_terms.amount / total_jobs
            lines.append(f"| Cost per Job | ${cost_per_job:,.0f} |")

    lines.append("")
    lines.append("### Target Market & Eligibility")
    lines.append("")

    flags = []
    if imp.is_low_income_area:
        flags.append("✅ Low-Income Area")
    if imp.is_nmtc_eligible:
        flags.append("✅ NMTC Eligible Census Tract")
    if imp.is_opportunity_zone:
        flags.append("✅ Opportunity Zone")
    if imp.is_minority_borrower:
        flags.append("✅ Minority Borrower")
    if imp.is_women_borrower:
        flags.append("✅ Women Borrower")

    if flags:
        for flag in flags:
            lines.append(f"- {flag}")
        lines.append("")

    if imp.census_tract:
        lines.append(f"**Census Tract:** {imp.census_tract}")
        lines.append("")

    if imp.impact_narrative:
        lines += ["### Impact Narrative", "", imp.impact_narrative, ""]

    return "\n".join(lines)
