"""
End-to-end smoke check against an INSTALLED credit-memo.

Run from a directory that is not the repo root, so `creditmemo` resolves to the
installed distribution rather than the source tree. Renders the README
quickstart deal to .docx and asserts the memo's tables actually reached the
Word file — the defect that shipped in 0.1.0.

    python scripts/smoke_installed_wheel.py /tmp/smoke.docx

Exits non-zero with a description of what was missing.
"""
import sys

from creditmemo import (
    CreditMemo, DealProfile, BorrowerProfile,
    LoanTerms, FinancialData, ImpactData,
)
from docx import Document


def build_readme_deal() -> DealProfile:
    borrower = BorrowerProfile(
        name="Southside Community Health Center",
        borrower_type="nonprofit", sector="healthcare",
        state="IL", city="Chicago", year_founded=2005,
        ceo_name="Dr. Maria Johnson",
        mission="To provide quality healthcare to underserved communities.",
        is_cdfi_certified=False,
    )
    loan = LoanTerms(
        deal_type="loan", amount=2_500_000, interest_rate=0.045,
        term_years=10, amortization_years=20, io_periods=12,
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
        jobs_created=18, jobs_retained=32, patients_served=8500,
        is_low_income_area=True, is_nmtc_eligible=True, is_minority_borrower=True,
    )
    return DealProfile(
        deal_name="Southside Health Center — $2.5MM Term Loan",
        borrower=borrower, loan_terms=loan, financial_data=financials,
        impact_data=impact, recommendation="approve_conditions",
        prepared_by="Jay Patel", prepared_date="2026-05-06",
        fund_name="NCIF Community Lending Fund",
        conditions=[
            "Receipt of final appraisal satisfactory to lender",
            "Evidence of $500k matching funds from borrower",
        ],
    )


def main(path: str) -> int:
    deal = build_readme_deal()
    memo = CreditMemo(deal)
    markdown = memo.to_markdown()
    memo.save_docx(path)

    doc = Document(path)
    docx_cells = {
        cell.text
        for table in doc.tables for row in table.rows for cell in row.cells
    }
    blob = "\n".join(sorted(docx_cells))

    failures = []

    # Every non-separator Markdown table row must have become a Word table row.
    md_rows = sum(
        1 for line in markdown.split("\n")
        if line.strip().startswith("|")
        and not set(line.replace("|", "").replace(" ", "")) <= set("-:")
    )
    header_rows = len(doc.tables[0].rows)
    docx_rows = sum(len(t.rows) for t in doc.tables)
    if docx_rows - header_rows != md_rows:
        failures.append(
            "row conservation: markdown has %d content rows, .docx has %d "
            "rows beyond the %d-row header table"
            % (md_rows, docx_rows - header_rows, header_rows)
        )

    if len(doc.tables) < 2:
        failures.append("only %d table(s) in the .docx" % len(doc.tables))

    for probe in ("1.35", "4.50%", "8,500"):
        if probe not in blob:
            failures.append("value %r present in the markdown is missing "
                            "from the .docx tables" % probe)

    if failures:
        for f in failures:
            print("FAIL:", f, file=sys.stderr)
        return 1

    print("OK: %d tables, %d rows, README probe values present"
          % (len(doc.tables), docx_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "smoke.docx"))
