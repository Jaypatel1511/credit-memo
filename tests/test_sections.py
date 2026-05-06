import pytest
from creditmemo.sections import executive, borrower, transaction, financial, impact, risk, recommendation


def test_executive_section(sample_deal):
    result = executive.generate(sample_deal)
    assert "Executive Summary" in result
    assert sample_deal.deal_name in result
    assert "APPROVE" in result.upper()


def test_borrower_section(sample_deal):
    result = borrower.generate(sample_deal)
    assert "Borrower Profile" in result
    assert sample_deal.borrower.name in result
    assert "Chicago" in result


def test_transaction_section(sample_deal):
    result = transaction.generate(sample_deal)
    assert "Transaction Structure" in result
    assert "$2.50MM" in result or "2,500,000" in result


def test_financial_section(sample_deal):
    result = financial.generate(sample_deal)
    assert "Financial Analysis" in result
    assert "1.35" in result


def test_impact_section(sample_deal):
    result = impact.generate(sample_deal)
    assert "Impact Analysis" in result
    assert "8,500" in result


def test_risk_section(sample_deal):
    result = risk.generate(sample_deal)
    assert "Risk Assessment" in result
    assert "Medicaid" in result


def test_recommendation_section(sample_deal):
    result = recommendation.generate(sample_deal)
    assert "IC Recommendation" in result
    assert "APPROVE" in result.upper()
