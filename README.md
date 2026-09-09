# credit-memo 📝

**Generate IC credit memos from structured deal inputs.**

Takes borrower profile, loan terms, financial data, impact metrics, and risk factors
as structured Python inputs and generates a formatted Investment Committee credit
memo in Markdown or Word (.docx) format.

---

## Why credit-memo?

Every CDFI analyst, IC committee, and private credit team writes credit memos from
scratch in Word. credit-memo standardizes the process — define your deal inputs once,
generate a professional IC memo instantly.

---

## Installation

    pip install credit-memo

    # For Word .docx output
    pip install credit-memo[docx]

credit-memo imports nothing outside the standard library. Only the optional
`[docx]` extra adds a dependency (`python-docx`).

---

## Quickstart

    from creditmemo import (
        CreditMemo, DealProfile, BorrowerProfile,
        LoanTerms, FinancialData, ImpactData, RiskFactor,
    )

    borrower = BorrowerProfile(
        name="Southside Community Health Center",
        borrower_type="nonprofit",
        sector="healthcare",
        state="IL",
        city="Chicago",
        year_founded=2005,
        ceo_name="Dr. Maria Johnson",
        mission="To provide quality healthcare to underserved communities.",
        is_cdfi_certified=False,
    )

    loan = LoanTerms(
        deal_type="loan",
        amount=2_500_000,
        interest_rate=0.045,
        term_years=10,
        amortization_years=20,
        io_periods=12,
        collateral="First mortgage on real property",
        use_of_proceeds="Acquisition and renovation of community health facility",
        min_dscr_covenant=1.20,
    )

    financials = FinancialData(
        revenue_y1=2_800_000, revenue_y2=3_000_000, revenue_y3=3_200_000,
        net_income_y1=150_000, net_income_y2=180_000, net_income_y3=210_000,
        dscr=1.35, current_ratio=1.8,
    )

    impact = ImpactData(
        jobs_created=18, jobs_retained=32,
        patients_served=8500,
        is_low_income_area=True,
        is_nmtc_eligible=True,
        is_minority_borrower=True,
    )

    deal = DealProfile(
        deal_name="Southside Health Center — $2.5MM Term Loan",
        borrower=borrower,
        loan_terms=loan,
        financial_data=financials,
        impact_data=impact,
        recommendation="approve_conditions",
        prepared_by="Jay Patel",
        prepared_date="2026-05-06",
        fund_name="NCIF Community Lending Fund",
        conditions=[
            "Receipt of final appraisal satisfactory to lender",
            "Evidence of $500k matching funds from borrower",
        ],
    )

    memo = CreditMemo(deal)
    print(memo.to_markdown())
    memo.save_markdown("southside_health_memo.md")
    memo.save_docx("southside_health_memo.docx")   # requires pip install credit-memo[docx]

---

## Word (.docx) Output

`save_docx()` writes headings, paragraphs, bullet and numbered lists, section
rules and **every table in the memo as a real Word table** — deal summary,
proposed terms, NMTC structure, historical financials, credit metrics,
projections, impact metrics, risk factors and the IC signature block. Tables use
the built-in `Table Grid` style with a bold header row. Conditions of Approval
use Word's `List Number` style, and the rules between sections are paragraph
borders rather than rows of underscores.

The .docx is a pure function of the Markdown the same deal produces: every
heading, paragraph, list item, rule and table in the Word file comes from a line
of that Markdown, and nothing is added that has no line behind it. It does not
apply column widths, merged cells, number alignment, or a firm template.

> **credit-memo 0.2.0 and 0.1.0 printed the memo's front matter twice** in every
> Word file — the title, the deal name and the whole Fund / Prepared By / Date /
> IC Date block appeared once as a hand-built cover block and again from the
> Markdown, in a different shape. **0.1.0 additionally dropped every table.** If
> you generated Word memos with either release, regenerate them. See the
> [changelog](https://github.com/Jaypatel1511/credit-memo/blob/main/CHANGELOG.md).

---

## Memo Sections Generated

1. Executive Summary — deal overview, recommendation, key terms table
2. Borrower Profile — organization description, mission, certifications
3. Transaction Structure — loan terms, collateral, covenants, NMTC structure
4. Financial Analysis — historical financials, key ratios, projections
5. Impact Analysis — jobs, units, demographics, eligibility flags
6. Risk Assessment — risk factors by severity with mitigants
7. IC Recommendation — formal recommendation with conditions and signature block

---

## Stating What You Know, and What You Don't

The eligibility and certification flags are **three-state**:

| value | rendering |
|---|---|
| `True` | the affirmative line — `✅ Low-Income Area` |
| `False` | an explicit negative — `❌ Not a Low-Income Area` |
| `None` *(default)* | omitted entirely |

`is_cdfi_certified`, `is_mdi`, `is_low_income_area`, `is_nmtc_eligible`,
`is_opportunity_zone`, `is_minority_borrower` and `is_women_borrower` all work
this way. Passing `False` says "we checked, and the answer is no"; leaving the
field alone says nothing at all. Before 0.2.1 these were plain booleans
defaulting to `False`, so the two were the same value and both rendered as
silence.

The same principle applies to figures: every optional financial field is tested
for `None`, not for truthiness, so a supplied `0` — no cash on hand, no net
income — is rendered as `$0.00MM` rather than discarded.

And a deal with no `risks` says so as a fact about its inputs. It does not
claim the deal has no risks; the package has no way to know that.

---

## Risk Severities

`RiskFactor.severity` must be one of `High`, `Medium` or `Low`, matched
case-insensitively — `"high"`, `"HIGH"` and `"High"` are all accepted and
normalise to `High`. Anything else raises `ValueError`. All the validated string
fields (`borrower_type`, `sector`, `deal_type`, `recommendation`, `severity`)
behave this way.

---

## Deal Types Supported

- loan — Direct loan or line of credit
- nmtc — New Markets Tax Credit investment
- equity — Equity investment
- grant — Grant or forgivable loan
- guarantee — Loan guarantee

---

## NMTC Deals

    from creditmemo import NMTCTerms

    nmtc = NMTCTerms(
        nmtc_allocation=10_000_000,
        credit_price=0.83,
        leverage_loan_rate=0.045,
        qlici_a_rate=0.045,
        qlici_b_rate=0.010,
        cde_fee_rate=0.02,
        cde_name="Chicago Development Fund",
        investor_name="US Bancorp CDC",
    )

    deal = DealProfile(..., nmtc_terms=nmtc, ...)

---

## Running Tests

    pip install -e ".[docx]" pytest
    pytest tests/ -v

The `.docx` gates skip if `python-docx` is not installed. Set
`CREDITMEMO_REQUIRE_DOCX=1` to make a missing `python-docx` an error instead —
CI does this so the gates can never pass by being skipped.

---

## Who This Is For

- CDFI analysts drafting IC memos for loan committee
- Private credit teams standardizing deal documentation
- CDEs preparing NMTC investment memos
- Impact investors documenting community development deals
- Anyone replacing manual Word memo templates with structured Python inputs

---

## License

MIT 2026 Jaypatel1511
