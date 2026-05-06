import pytest
from creditmemo.memo import CreditMemo


def test_memo_created(sample_deal):
    memo = CreditMemo(sample_deal)
    assert memo.deal == sample_deal


def test_to_markdown_returns_string(sample_deal):
    memo = CreditMemo(sample_deal)
    md = memo.to_markdown()
    assert isinstance(md, str)
    assert len(md) > 100


def test_markdown_contains_deal_name(sample_deal):
    memo = CreditMemo(sample_deal)
    md = memo.to_markdown()
    assert sample_deal.deal_name in md


def test_markdown_contains_borrower(sample_deal):
    memo = CreditMemo(sample_deal)
    md = memo.to_markdown()
    assert sample_deal.borrower.name in md


def test_markdown_contains_recommendation(sample_deal):
    memo = CreditMemo(sample_deal)
    md = memo.to_markdown()
    assert "APPROVE SUBJECT TO CONDITIONS" in md.upper()


def test_markdown_contains_sections(sample_deal):
    memo = CreditMemo(sample_deal)
    md = memo.to_markdown()
    for section in ["Executive Summary", "Borrower Profile",
                    "Transaction Structure", "Financial Analysis",
                    "Impact Analysis", "Risk Assessment",
                    "IC Recommendation"]:
        assert section in md


def test_markdown_contains_conditions(sample_deal):
    memo = CreditMemo(sample_deal)
    md = memo.to_markdown()
    assert "Receipt of final appraisal" in md


def test_section_count(sample_deal):
    memo = CreditMemo(sample_deal)
    assert memo.section_count() >= 6


def test_save_markdown(sample_deal, tmp_path):
    memo = CreditMemo(sample_deal)
    path = str(tmp_path / "test_memo.md")
    memo.save_markdown(path)
    with open(path) as f:
        content = f.read()
    assert sample_deal.deal_name in content


def test_preview_runs(sample_deal, capsys):
    memo = CreditMemo(sample_deal)
    memo.preview(lines=10)
    captured = capsys.readouterr()
    assert len(captured.out) > 0


def test_invalid_input_raises():
    with pytest.raises(TypeError):
        CreditMemo("not a deal profile")
