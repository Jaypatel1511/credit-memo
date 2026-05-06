import pytest
from creditmemo.data.schema import (
    DealProfile, BorrowerProfile, LoanTerms,
    FinancialData, ImpactData, NMTCTerms, RiskFactor,
)


@pytest.fixture
def sample_borrower():
    return BorrowerProfile(
        name="Southside Community Health Center",
        borrower_type="nonprofit",
        sector="healthcare",
        state="IL",
        city="Chicago",
        year_founded=2005,
        ceo_name="Dr. Maria Johnson",
        total_assets=8_000_000,
        annual_revenue=3_200_000,
        description="A federally qualified health center serving low-income communities.",
        mission="To provide quality healthcare to underserved communities.",
        is_cdfi_certified=False,
    )


@pytest.fixture
def sample_loan_terms():
    return LoanTerms(
        deal_type="loan",
        amount=2_500_000,
        interest_rate=0.045,
        term_years=10,
        amortization_years=20,
        io_periods=12,
        collateral="First mortgage on real property",
        use_of_proceeds="Acquisition and renovation of community health facility",
        closing_date="2026-06-01",
        maturity_date="2036-06-01",
        min_dscr_covenant=1.20,
        origination_fee_pct=0.01,
    )


@pytest.fixture
def sample_financials():
    return FinancialData(
        revenue_y1=2_800_000,
        revenue_y2=3_000_000,
        revenue_y3=3_200_000,
        net_income_y1=150_000,
        net_income_y2=180_000,
        net_income_y3=210_000,
        total_assets=8_000_000,
        total_liabilities=3_500_000,
        net_assets_equity=4_500_000,
        cash=450_000,
        dscr=1.35,
        current_ratio=1.8,
        debt_to_equity=0.78,
        projected_dscr_y1=1.38,
        projected_dscr_y2=1.42,
        projected_dscr_y3=1.47,
    )


@pytest.fixture
def sample_impact():
    return ImpactData(
        jobs_created=18,
        jobs_retained=32,
        patients_served=8500,
        is_low_income_area=True,
        is_nmtc_eligible=True,
        is_minority_borrower=True,
        census_tract="17031840100",
        impact_narrative="The project will serve 8,500 low-income patients annually.",
    )


@pytest.fixture
def sample_risks():
    return [
        RiskFactor(
            category="Credit",
            description="Revenue concentration in Medicaid reimbursements",
            severity="Medium",
            mitigant="Diversified payer mix; 3-year Medicaid contract in place",
        ),
        RiskFactor(
            category="Market",
            description="Healthcare reimbursement rate uncertainty",
            severity="Low",
            mitigant="Conservative revenue projections used in underwriting",
        ),
    ]


@pytest.fixture
def sample_deal(sample_borrower, sample_loan_terms,
                sample_financials, sample_impact, sample_risks):
    return DealProfile(
        deal_name="Southside Health Center — $2.5MM Term Loan",
        borrower=sample_borrower,
        loan_terms=sample_loan_terms,
        financial_data=sample_financials,
        impact_data=sample_impact,
        recommendation="approve_conditions",
        prepared_by="Jay Patel",
        prepared_date="2026-05-06",
        ic_date="2026-05-15",
        fund_name="NCIF Community Lending Fund",
        risks=sample_risks,
        conditions=[
            "Receipt of final appraisal satisfactory to lender",
            "Evidence of $500k matching funds from borrower",
            "Completion of environmental review",
        ],
        deal_summary="NCIF proposes a $2.5MM term loan to finance the acquisition "
                     "and renovation of a community health facility on Chicago's south side.",
    )
