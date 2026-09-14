"""Transaction Structure section generator."""
from creditmemo import fields
from creditmemo.data.schema import DealProfile, DEAL_TYPES
from creditmemo.money import dollars, money, money_with_mm
from creditmemo.tables import escape_cell

#: (field, the words the footnote uses) for every ``NMTCTerms`` input that
#: reaches neither rendering at any value, in field order.
#:
#: **Derived by perturbation, not by reading the code**: each of the nine
#: ``NMTCTerms`` fields was changed one at a time on the published 0.2.1 wheel
#: and both renderings were diffed against the unperturbed memo. Five moved the
#: memo (``nmtc_allocation``, ``credit_price``, ``cde_fee_rate``, ``cde_name``,
#: ``investor_name``); these four moved neither. Three of them —
#: ``leverage_loan_rate``, ``qlici_a_rate`` and ``qlici_b_rate`` — are
#: *required positional arguments*: a caller cannot construct ``NMTCTerms``
#: without supplying them, and the package then discards them in silence.
#:
#: The README has disclosed this since 0.2.1. The memo did not, and the memo is
#: what reaches an Investment Committee: the section is headed **NMTC
#: Structure** and nothing in it marked the table partial. Adding rows would
#: change the ``.docx`` table shape and needs the gate coverage that goes with
#: it, which is why it is still 0.3.0 work; a line of prose beneath the table
#: changes no shape.
#:
#: ``test_g15_the_footnote_names_exactly_the_discarded_inputs`` re-derives this
#: set by the same perturbation at test time, so a fifth discarded field, or
#: one of these four starting to render, reddens rather than going unnoticed.
UNRENDERED_NMTC_INPUTS = (
    ("leverage_loan_rate", "the leverage loan rate"),
    ("qlici_a_rate",       "the QLICI A rate"),
    ("qlici_b_rate",       "the QLICI B rate"),
    ("compliance_years",   "the compliance period"),
)


def _and_list(phrases) -> str:
    """``a``, ``a and b``, ``a, b and c`` — an English list, no Oxford comma."""
    phrases = list(phrases)
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


#: The footnote itself, built from :data:`UNRENDERED_NMTC_INPUTS` rather than
#: written out, so the two cannot disagree.
UNRENDERED_NMTC_INPUTS_NOTE = (
    "This table does not show every NMTC input the package accepts: "
    + _and_list(label for _, label in UNRENDERED_NMTC_INPUTS)
    + " are accepted by NMTCTerms and appear nowhere in this memo, in either "
      "format. Add them by hand if the Committee needs them."
)


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
        # Beneath the table, not in it: a row would change the .docx table
        # shape, which is the thing 0.2.1 deferred. A paragraph does not.
        lines.append("")
        lines.append(UNRENDERED_NMTC_INPUTS_NOTE)
        lines.append("")

    return "\n".join(lines)
