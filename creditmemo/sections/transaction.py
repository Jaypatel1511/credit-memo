"""Transaction Structure section generator."""
from creditmemo.data.schema import DealProfile, DEAL_TYPES


def generate(deal: DealProfile) -> str:
    lt = deal.loan_terms
    rate_str = f"{lt.interest_rate*100:.2f}%" if lt.interest_rate else "N/A"

    lines = [
        "## Transaction Structure",
        "",
        "### Proposed Terms",
        "",
        f"| Term | Detail |",
        f"|------|--------|",
        f"| Deal Type | {DEAL_TYPES.get(lt.deal_type, lt.deal_type)} |",
        f"| Loan Amount | ${lt.amount:,.0f} (${lt.amount_mm:.2f}MM) |",
        f"| Interest Rate | {rate_str} |",
    ]

    if lt.term_years:
        lines.append(f"| Loan Term | {lt.term_years} years |")
    if lt.amortization_years:
        lines.append(f"| Amortization | {lt.amortization_years} years |")
    if lt.io_periods:
        lines.append(f"| Interest-Only Period | {lt.io_periods} months |")
    if lt.closing_date:
        lines.append(f"| Anticipated Closing | {lt.closing_date} |")
    if lt.maturity_date:
        lines.append(f"| Maturity Date | {lt.maturity_date} |")
    if lt.origination_fee_pct:
        lines.append(
            f"| Origination Fee | {lt.origination_fee_pct*100:.2f}% "
            f"(${lt.origination_fee:,.0f}) |"
        )

    lines.append("")

    if lt.use_of_proceeds:
        lines += [
            "### Use of Proceeds",
            "",
            lt.use_of_proceeds,
            "",
        ]

    if lt.collateral:
        lines += [
            "### Collateral",
            "",
            lt.collateral,
            "",
        ]

    if lt.guarantor:
        lines += [
            "### Guaranty",
            "",
            lt.guarantor,
            "",
        ]

    covenants = []
    if lt.min_dscr_covenant:
        covenants.append(f"Minimum DSCR of {lt.min_dscr_covenant:.2f}x")
    if lt.max_ltv:
        covenants.append(f"Maximum LTV of {lt.max_ltv*100:.0f}%")

    if covenants:
        lines += ["### Financial Covenants", ""]
        for cov in covenants:
            lines.append(f"- {cov}")
        lines.append("")

    # NMTC structure
    if deal.nmtc_terms:
        nt = deal.nmtc_terms
        lines += [
            "### NMTC Structure",
            "",
            f"| Component | Amount |",
            f"|-----------|--------|",
            f"| QEI (NMTC Allocation) | ${nt.nmtc_allocation/1e6:.2f}MM |",
            f"| Total NMTCs (39%) | ${nt.total_nmtcs/1e6:.2f}MM |",
            f"| Credit Price | ${nt.credit_price:.2f}/$1 |",
            f"| Investor Equity | ${nt.investor_equity/1e6:.2f}MM |",
            f"| CDE Fee | {nt.cde_fee_rate*100:.1f}% |",
            f"| Estimated Net Subsidy | ${nt.net_subsidy/1e6:.2f}MM |",
        ]
        if nt.cde_name:
            lines.append(f"| CDE | {nt.cde_name} |")
        if nt.investor_name:
            lines.append(f"| Tax Credit Investor | {nt.investor_name} |")
        lines.append("")

    return "\n".join(lines)
