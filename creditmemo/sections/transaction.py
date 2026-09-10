"""Transaction Structure section generator."""
from creditmemo import fields
from creditmemo.data.schema import DealProfile, DEAL_TYPES
from creditmemo.money import dollars, money, money_with_mm
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
        f"| Loan Amount | {money_with_mm(lt.amount)} |",
        f"| Interest Rate | {rate_str} |",
    ]

    if lt.term_years is not None:
        lines.append(f"| Loan Term | {fields.term(lt.term_years)} |")
    if lt.amortization_years is not None:
        lines.append(f"| Amortization | {fields.term(lt.amortization_years)} |")
    if lt.io_periods:
        lines.append(f"| Interest-Only Period | {lt.io_periods} months |")
    # `fields.is_supplied`, not a bare `is not None`. These two are the only
    # `Optional[str]` fields in the package that were tested for `None` alone,
    # against a rule the README, `fields.is_supplied`, the CHANGELOG and G9 all
    # state: for a string, the falsy value is `""` and `""` is absence. A
    # `closing_date=""` therefore rendered `| Anticipated Closing |  |` — a row
    # of the Proposed Terms table, in an IC memo, with a label and no value —
    # while `mission=""` next door correctly rendered nothing at all. R18.
    if fields.is_supplied(lt.closing_date):
        lines.append(f"| Anticipated Closing | {escape_cell(lt.closing_date)} |")
    if fields.is_supplied(lt.maturity_date):
        lines.append(f"| Maturity Date | {escape_cell(lt.maturity_date)} |")
    if lt.origination_fee_pct:
        lines.append(
            f"| Origination Fee | {lt.origination_fee_pct*100:.2f}% "
            f"({dollars(lt.origination_fee)}) |"
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
        # `.1f`, the same precision `FinancialData.ltv` renders at. R23: `.0f`
        # turned a `max_ltv=0.795` covenant into "Maximum LTV of 80%" — a
        # covenant reported looser than it is, at a value that is plausible
        # enough to go unquestioned, in the section an IC reads to learn what
        # the borrower agreed to.
        covenants.append(f"Maximum LTV of {lt.max_ltv*100:.1f}%")

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
            f"| QEI (NMTC Allocation) | {money(nt.nmtc_allocation)} |",
            f"| Total NMTCs (39%) | {money(nt.total_nmtcs)} |",
            # `credit_price` deliberately does not go through creditmemo.money:
            # it is dollars per $1 of credit, a price quoted in the unit the
            # NMTC market quotes it in, not a magnitude in a column of
            # magnitudes. See the module docstring there.
            f"| Credit Price | ${nt.credit_price:.2f}/$1 |",
            f"| Investor Equity | {money(nt.investor_equity)} |",
            f"| CDE Fee | {nt.cde_fee_rate*100:.1f}% |",
            f"| Estimated Net Subsidy | {money(nt.net_subsidy)} |",
        ]
        if fields.is_supplied(nt.cde_name):
            lines.append(f"| CDE | {escape_cell(nt.cde_name)} |")
        if fields.is_supplied(nt.investor_name):
            lines.append(f"| Tax Credit Investor | {escape_cell(nt.investor_name)} |")
        lines.append("")

    return "\n".join(lines)
