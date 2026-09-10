"""
End-to-end smoke check against an INSTALLED credit-memo.

Run from a directory that is not the repo root, so `creditmemo` resolves to the
installed distribution rather than the source tree. Renders the README
quickstart deal to .docx and asserts the memo's tables actually reached the
Word file — the defect that shipped in 0.1.0.

The deal carries two risk rows the README quickstart does not, because the
README deal has no `risks` at all and so never puts free underwriter text into
a table cell: one row with a literal `|` in it, and one made only of `-`. Those
are the two ways 0.2.0's own table path can silently put a value in the wrong
place or drop it, and without them the installed-wheel check never touches
either.

Row counting goes through creditmemo.tables.content_rows — the same function
the test suite counts with. A second, hand-rolled idea of what a separator row
is used to live in this file, and it disagreed with the package's.

    python scripts/smoke_installed_wheel.py /tmp/smoke.docx

Exits non-zero with a description of what was missing.
"""
import sys

from creditmemo import (
    CreditMemo, DealProfile, BorrowerProfile,
    LoanTerms, FinancialData, ImpactData,
)
from creditmemo.data.schema import RiskFactor
from creditmemo.tables import content_rows
from docx import Document

#: (category, description, mitigant) for the two adversarial risk rows. Each
#: must appear in the .docx as one row, in this field order.
PIPE_RISK = ("Credit", "Payer mix | Medicaid concentration", "3-year contract")
DASH_RISK = ("-", "-", "-")


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
        risks=[
            RiskFactor(category=PIPE_RISK[0], description=PIPE_RISK[1],
                       severity="Medium", mitigant=PIPE_RISK[2]),
            RiskFactor(category=DASH_RISK[0], description=DASH_RISK[1],
                       severity="Low", mitigant=DASH_RISK[2]),
        ],
    )


def main(path: str) -> int:
    deal = build_readme_deal()
    memo = CreditMemo(deal)
    markdown = memo.to_markdown()
    memo.save_docx(path)

    doc = Document(path)
    docx_rows_of_text = [
        [cell.text for cell in row.cells]
        for table in doc.tables for row in table.rows
    ]
    blob = "\n".join(sorted({c for row in docx_rows_of_text for c in row}))

    failures = []

    # Every non-separator Markdown table row must have become a Word table row.
    # 0.2.1 removed the hand-built header table: every table in the .docx now
    # comes from the Markdown, so nothing is subtracted here any more.
    md_rows = len(content_rows(markdown.split("\n")))
    docx_rows = sum(len(t.rows) for t in doc.tables)
    if docx_rows != md_rows:
        failures.append(
            "row conservation: markdown has %d content rows, .docx has %d"
            % (md_rows, docx_rows)
        )

    if len(doc.tables) < 2:
        failures.append("only %d table(s) in the .docx" % len(doc.tables))

    # R5: nothing may appear in the .docx more often than in the Markdown. The
    # memo title and the Fund/Prepared By/Date/IC Date block were emitted twice
    # by every release before 0.2.1.
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for probe in ("Investment Committee Memorandum",
                  "Fund: %s" % deal.fund_name,
                  "Prepared By: %s" % deal.prepared_by):
        md_count = sum(
            1 for line in markdown.split("\n")
            if line.replace("**", "").strip().lstrip("# ") == probe
        )
        if paragraphs.count(probe) != md_count:
            failures.append(
                "%r appears %d time(s) in the .docx and %d time(s) in the "
                "Markdown" % (probe, paragraphs.count(probe), md_count)
            )

    for probe in ("1.35", "4.50%", "8,500"):
        if probe not in blob:
            failures.append("value %r present in the markdown is missing "
                            "from the .docx tables" % probe)

    # A literal '|' must stay inside one cell, and a not-applicable '-' row must
    # not be mistaken for the Markdown delimiter rule and dropped. Checked as
    # whole rows, so a value landing in the wrong column fails too.
    for label, risk in (("pipe", PIPE_RISK), ("dash", DASH_RISK)):
        if list(risk) not in docx_rows_of_text:
            failures.append(
                "the %s risk row %r is not a row of the .docx — it was dropped, "
                "split across cells, or reordered" % (label, list(risk))
            )

    if failures:
        for f in failures:
            print("FAIL:", f, file=sys.stderr)
        return 1

    print("OK: %d tables, %d rows, README probe values present"
          % (len(doc.tables), docx_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "smoke.docx"))
