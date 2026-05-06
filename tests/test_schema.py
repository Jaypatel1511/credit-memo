import pytest
from creditmemo.data.schema import (
    BorrowerProfile, LoanTerms, DealProfile, RiskFactor
)


def test_borrower_created(sample_borrower):
    assert sample_borrower.name == "Southside Community Health Center"
    assert sample_borrower.sector == "healthcare"


def test_invalid_borrower_type_raises():
    with pytest.raises(ValueError, match="borrower_type"):
        BorrowerProfile(
            name="Test", borrower_type="invalid",
            sector="healthcare", state="IL", city="Chicago"
        )


def test_invalid_sector_raises():
    with pytest.raises(ValueError, match="sector"):
        BorrowerProfile(
            name="Test", borrower_type="nonprofit",
            sector="invalid", state="IL", city="Chicago"
        )


def test_loan_terms_created(sample_loan_terms):
    assert sample_loan_terms.amount == 2_500_000
    assert sample_loan_terms.amount_mm == pytest.approx(2.5)


def test_negative_amount_raises():
    with pytest.raises(ValueError, match="amount must be positive"):
        LoanTerms(deal_type="loan", amount=-100_000, interest_rate=0.05)


def test_invalid_deal_type_raises():
    with pytest.raises(ValueError, match="deal_type"):
        LoanTerms(deal_type="invalid", amount=1_000_000)


def test_deal_profile_created(sample_deal):
    assert sample_deal.deal_name == "Southside Health Center — $2.5MM Term Loan"
    assert sample_deal.recommendation == "approve_conditions"


def test_invalid_recommendation_raises(sample_borrower, sample_loan_terms,
                                       sample_financials, sample_impact):
    with pytest.raises(ValueError, match="recommendation"):
        DealProfile(
            deal_name="Test", borrower=sample_borrower,
            loan_terms=sample_loan_terms, financial_data=sample_financials,
            impact_data=sample_impact, recommendation="invalid",
            prepared_by="Test", prepared_date="2026-01-01",
        )


def test_origination_fee(sample_loan_terms):
    assert sample_loan_terms.origination_fee == pytest.approx(25_000)


def test_revenue_trend_increasing(sample_financials):
    assert sample_financials.revenue_trend == "increasing"


def test_risk_factor_created(sample_risks):
    assert len(sample_risks) == 2
    assert sample_risks[0].severity == "Medium"
