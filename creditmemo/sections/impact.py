"""Impact Analysis section generator."""
from creditmemo.data.schema import DealProfile

#: (attribute, affirmative, negative) for the tri-state eligibility flags, in
#: field order. A flag set to ``False`` is a statement the caller made and gets
#: rendered; a flag left ``None`` is not, and gets nothing.
TARGET_MARKET_FLAGS = (
    ("is_low_income_area",   "Low-Income Area",            "Not a Low-Income Area"),
    ("is_nmtc_eligible",     "NMTC Eligible Census Tract",
                             "Not an NMTC Eligible Census Tract"),
    ("is_opportunity_zone",  "Opportunity Zone",           "Not an Opportunity Zone"),
    ("is_minority_borrower", "Minority Borrower",          "Not a Minority Borrower"),
    ("is_women_borrower",    "Women Borrower",             "Not a Women Borrower"),
)

#: What the block says when every eligibility flag is ``None``. Before 0.2.1
#: this case rendered a bare "### Target Market & Eligibility" heading with
#: nothing under it at all.
NO_TARGET_MARKET_FLAGS_TEXT = (
    "No target-market or eligibility flags were provided."
)


def _target_market_lines(imp) -> list:
    lines = []
    for attr, yes, no in TARGET_MARKET_FLAGS:
        value = getattr(imp, attr)
        if value is True:
            lines.append(f"- ✅ {yes}")
        elif value is False:
            lines.append(f"- ❌ {no}")
    if not lines:
        return [NO_TARGET_MARKET_FLAGS_TEXT, ""]
    lines.append("")
    return lines


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
    lines += _target_market_lines(imp)

    if imp.census_tract:
        lines.append(f"**Census Tract:** {imp.census_tract}")
        lines.append("")

    if imp.impact_narrative:
        lines += ["### Impact Narrative", "", imp.impact_narrative, ""]

    return "\n".join(lines)
