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


#: (ImpactData field, the value, the row the memo must show for it). Every
#: optional Community Impact Metrics row, which between them were four of the
#: five statements in impact.py that no test executed.
IMPACT_ROWS = [
    ("affordable_units",       24,     "| Affordable Units | 24 |"),
    ("sq_ft_community_space",  12500.0, "| Community Space (sq ft) | 12,500 |"),
    ("patients_served",        8500,   "| Patients Served | 8,500 |"),
    ("students_served",        340,    "| Students Served | 340 |"),
    ("businesses_supported",   12,     "| Businesses Supported | 12 |"),
]


@pytest.mark.parametrize("field,value,expected", IMPACT_ROWS,
                         ids=[r[0] for r in IMPACT_ROWS])
def test_every_optional_impact_metric_renders_its_row(sample_deal, field, value,
                                                      expected):
    """
    The expected strings are written out rather than formatted with the
    section's own f-string, for the reason ZERO_RENDERINGS is: a gate that
    formats its expectation the way the code does follows the code anywhere.
    The thousands separators are part of what is being checked.
    """
    from creditmemo.data.schema import ImpactData

    supplied = ImpactData(**{field: value})
    assert expected in impact.generate(_deal_with_impact(sample_deal, supplied))

    absent = ImpactData()
    assert expected not in impact.generate(_deal_with_impact(sample_deal, absent))


def _deal_with_impact(deal, impact_data):
    import copy

    clone = copy.copy(deal)
    clone.impact_data = impact_data
    return clone
