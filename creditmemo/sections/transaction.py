"""Transaction Structure section generator."""
from creditmemo import fields
from creditmemo.data.schema import DealProfile, DEAL_TYPES
from creditmemo.tables import escape_cell


def generate(deal: DealProfile) -> str:
    lt = deal.loan_terms
    # One formatter, shared with the Executive Summary. See executive.py.
    rate_str = fields.or_not_supplied(fields.rate(lt.interest_rate))

    lines = [
        "## Transaction Structure",
        "",
        "### Proposed Terms",
        "",
        f"| Term | Detail |",
        f"|------|--------|",
        f"| Deal Type | {escape_cell(DEAL_TYPES.get(lt.deal_type, lt.deal_type))} |",
        f"| Loan Amount | ${lt.amount:,.0f} (${lt.amount_mm:.2f}MM) |",
        f"| Interest Rate | {rate_str} |",
    ]

    if lt.term_years is not None:
        lines.append(f"| Loan Term | {fields.term(lt.term_years)} |")
    if lt.amortization_years is not None:
        lines.append(f"| Amortization | {fields.term(lt.amortization_years)} |")
    if lt.io_periods:
        lines.append(f"| Interest-Only Period | {lt.io_periods} months |")
    if lt.closing_date is not None:
        lines.append(f"| Anticipated Closing | {escape_cell(lt.closing_date)} |")
    if lt.maturity_date is not None:
        lines.append(f"| Maturity Date | {escape_cell(lt.maturity_date)} |")
    if lt.origination_fee_pct:
        lines.append(
            f"| Origination Fee | {lt.origination_fee_pct*100:.2f}% "
            f"(${lt.origination_fee:,.0f}) |"
        )

    lines.append("")

    if fields.is_supplied(lt.use_of_proceeds):
        lines += [
            "### Use of Proceeds",
            "",
            lt.use_of_proceeds,
            "",
        ]

    if fields.is_supplied(lt.collateral):
        lines += [
            "### Collateral",
            "",
            lt.collateral,
            "",
        ]

    if fields.is_supplied(lt.guarantor):
        lines += [
            "### Guaranty",
            "",
            lt.guarantor,
            "",
        ]

    covenants = []
    if lt.min_dscr_covenant is not None:
        covenants.append(f"Minimum DSCR of {lt.min_dscr_covenant:.2f}x")
    if lt.max_ltv is not None:
        covenants.append(f"Maximum LTV of {lt.max_ltv*100:.0f}%")

    if covenants:
        lines += ["### Financial Covenants", ""]
        for cov in covenants:
            lines.append(f"- {cov}")
        lines.append("")

    # NMTC structure
    if deal.nmtc_terms is not None:
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
        if fields.is_supplied(nt.cde_name):
            lines.append(f"| CDE | {escape_cell(nt.cde_name)} |")
        if fields.is_supplied(nt.investor_name):
            lines.append(f"| Tax Credit Investor | {escape_cell(nt.investor_name)} |")
        lines.append("")

    return "\n".join(lines)
