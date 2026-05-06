# credit-memo 📝

**Generate IC credit memos from structured deal inputs.**

Takes borrower profile, loan terms, financial data, impact metrics, and risk factors
as structured Python inputs and generates a complete, formatted Investment Committee
credit memo in Markdown or Word (.docx) format.

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

## Memo Sections Generated

1. Executive Summary — deal overview, recommendation, key terms table
2. Borrower Profile — organization description, mission, certifications
3. Transaction Structure — loan terms, collateral, covenants, NMTC structure
4. Financial Analysis — historical financials, key ratios, projections
5. Impact Analysis — jobs, units, demographics, eligibility flags
6. Risk Assessment — risk factors by severity with mitigants
7. IC Recommendation — formal recommendation with conditions and signature block

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

    PYTHONPATH=. pytest tests/ -v

29 tests across all modules.

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
