"""
Gates on what the memo says about the inputs it was given.

0.2.0's .docx defects were about *shape*. These are about *truth*: a memo that
states a finding the caller never supplied, or silently discards one they did.
Both failure modes were silent in 0.2.0 — nothing raised, nothing warned, and
the memo read as though the analysis had been done.

Every gate here ships with the mutation that reddens it, in its docstring.
"""
import datetime
import io
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from creditmemo.data.schema import (
    BORROWER_TYPES as BORROWER_TYPES_FOR_TEST,
    BorrowerProfile, DealProfile, FinancialData, ImpactData, LoanTerms,
    NMTCTerms, RiskFactor, SEVERITIES,
)
from creditmemo.memo import CreditMemo
from creditmemo.sections import risk as risk_section

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "creditmemo"


def _package_sources():
    """Every shipped .py file. tests/ is deliberately not among them."""
    return sorted(PACKAGE.rglob("*.py"))


def _deal(borrower=None, impact=None, risks=None, financials=None,
          loan_terms=None, **kw):
    return DealProfile(
        deal_name="Test Deal",
        borrower=borrower or BorrowerProfile(
            name="Test Borrower", borrower_type="nonprofit",
            sector="healthcare", state="IL", city="Chicago"),
        loan_terms=loan_terms or LoanTerms(deal_type="loan", amount=2_500_000,
                                           interest_rate=0.045, term_years=10),
        financial_data=financials if financials is not None else FinancialData(dscr=1.35),
        impact_data=impact or ImpactData(),
        recommendation="approve_conditions",
        prepared_by="Jay Patel", prepared_date="2026-05-06",
        fund_name="Test Fund", risks=risks or [], **kw)


# ── G4 — severity round-trip ─────────────────────────────────────────────────

ACCEPTED_SPELLINGS = [
    "High", "Medium", "Low",              # canonical
    "high", "medium", "low",              # the natural spelling
    "HIGH", "MEDIUM", "LOW",
    "hIgH", " Medium ",                   # mixed case and stray whitespace
]

REJECTED_SPELLINGS = ["Critical", "Med", "severe", "", "none", "1", "High Risk"]


@pytest.mark.parametrize("spelling", ACCEPTED_SPELLINGS)
def test_g4_every_accepted_severity_spelling_reaches_the_memo(spelling):
    """
    G4, accept half. Before 0.2.1 only the three exact title-case spellings
    rendered; every other value constructed without complaint and then vanished
    from the memo, with no warning on any stream.

    Red-proof (must fail): drop the __post_init__ from RiskFactor.
    Observed: 5 failed here (the non-canonical spellings) + 7 in the reject half.
    """
    factor = RiskFactor(category="Credit", description="UNIQUE-DESCRIPTION-XYZ",
                        severity=spelling, mitigant="Mitigated")
    assert factor.severity in SEVERITIES, "severity was not normalised"
    md = CreditMemo(_deal(risks=[factor])).to_markdown()
    assert "UNIQUE-DESCRIPTION-XYZ" in md, f"{spelling!r} was silently dropped"
    assert f"### {factor.severity} Risk Factors" in md


@pytest.mark.parametrize("spelling", REJECTED_SPELLINGS)
def test_g4_every_rejected_severity_raises(spelling):
    """
    G4, reject half — the half a removed validation fails.

    Red-proof (must fail): delete RiskFactor.__post_init__.
    Observed: 7 failed here.
    """
    with pytest.raises(ValueError, match="severity"):
        RiskFactor(category="Credit", description="d", severity=spelling,
                   mitigant="m")


def test_g4_the_severity_error_names_the_allowed_values():
    """The same error shape borrower_type raises, per R2."""
    with pytest.raises(ValueError) as exc:
        RiskFactor(category="C", description="d", severity="Critical", mitigant="m")
    for value in SEVERITIES:
        assert value in str(exc.value)


#: Values that are not strings at all. `_normalise_choice` calls `.strip()` and
#: `.lower()` on the candidate, so without the isinstance guard every one of
#: these raises AttributeError from inside the schema instead of the ValueError
#: that names the allowed vocabulary — and `None`, the likeliest of them by far
#: for a field read out of a spreadsheet cell that was blank, is the one a
#: caller is most likely to meet.
NON_STRING_CHOICES = [None, 5, 0, True, ["nonprofit"], b"nonprofit", ("cdfi",)]


@pytest.mark.parametrize("value", NON_STRING_CHOICES, ids=lambda v: repr(v))
def test_g4_a_non_string_choice_is_refused_by_the_same_error(value):
    """
    Every validated enum field rejects a non-string with the ValueError that
    names its vocabulary, not with an AttributeError from `.strip()`.

    This is the branch of `_normalise_choice` that no test executed. It matters
    because the error is the whole user interface of a validated field: a
    caller who gets `AttributeError: 'NoneType' object has no attribute
    'strip'` learns nothing about what the field wanted.
    """
    from creditmemo.data.schema import _normalise_choice

    with pytest.raises(ValueError) as error:
        _normalise_choice(value, BORROWER_TYPES_FOR_TEST, "borrower_type")
    assert "borrower_type must be one of" in str(error.value)

    with pytest.raises(ValueError) as error:
        BorrowerProfile(name="N", borrower_type=value, sector="healthcare",
                        state="IL", city="Chicago")
    assert "borrower_type must be one of" in str(error.value)

    with pytest.raises(ValueError) as error:
        RiskFactor(category="Credit", description="d", severity=value,
                   mitigant="m")
    assert "severity must be one of" in str(error.value)


def test_severity_vocabulary_is_still_three_levels():
    """
    R2: "Do not add Critical." Whether the scale should carry a level above
    High is a design question, not a patch-release decision. If this list ever
    grows, that was a deliberate call and this line changes with it.
    """
    assert SEVERITIES == ("High", "Medium", "Low")


def test_string_enums_agree_about_case():
    """
    R2 consistency check. borrower_type was case-sensitive and severity was not
    validated at all; both are now case-insensitive, which is the only
    direction that rejects nothing previously accepted.
    """
    assert BorrowerProfile(name="N", borrower_type="NonProfit", sector="Healthcare",
                           state="IL", city="Chicago").borrower_type == "nonprofit"
    assert LoanTerms(deal_type="NMTC", amount=1).deal_type == "nmtc"
    with pytest.raises(ValueError, match="borrower_type"):
        BorrowerProfile(name="N", borrower_type="tribal", sector="healthcare",
                        state="IL", city="Chicago")


# ── G5 — the empty-risk sentence, gated as prose ─────────────────────────────

#: The exact ruled text for 0.2.1.
RULED_NO_RISKS_TEXT = (
    "**No risk factors were provided.** This section reflects the risk factors "
    "supplied with this deal; it is not an assessment that no material risks "
    "exist."
)

#: Sentence shapes that assert, as a finding, that no risks exist. The ruled
#: text contains "no material risks exist" itself — as the thing it disclaims —
#: so matches are checked against the ruled spans rather than searched for
#: blindly. That is why this uses finditer and not search.
FORBIDDEN_CLAIMS = [
    re.compile(r"no\s+(specific\s+)?risks\s+identified", re.I),
    re.compile(r"no\s+material\s+risks\s+exist", re.I),
    re.compile(r"beyond\s+standard\s+credit\s+considerations", re.I),
]


def _ruled_spans(text):
    return [m.span() for m in re.finditer(re.escape(RULED_NO_RISKS_TEXT), text)]


def test_g5_the_empty_risk_sentence_is_exactly_as_ruled():
    assert risk_section.NO_RISKS_TEXT == RULED_NO_RISKS_TEXT
    md = CreditMemo(_deal(risks=[])).to_markdown()
    assert RULED_NO_RISKS_TEXT in md


def test_g5_no_shipped_module_asserts_that_risks_do_not_exist():
    """
    G5. The package must contain no sentence claiming, as a finding, that the
    deal has no risks. tests/ is excluded so this gate can hold the string it
    forbids.

    Red-proof (must fail): restore "No specific risks identified beyond
    standard credit considerations." in creditmemo/sections/risk.py.
    Observed: 2 failed (this gate and G5's exact-text gate).
    """
    offences = []
    for path in _package_sources():
        text = io.open(path, encoding="utf-8").read()
        allowed = _ruled_spans(text)
        for pattern in FORBIDDEN_CLAIMS:
            for match in pattern.finditer(text):
                if any(a <= match.start() and match.end() <= b for a, b in allowed):
                    continue
                offences.append(f"{path.relative_to(ROOT)}: {match.group(0)!r}")
    assert not offences, "memo asserts an absence of risk it cannot know: %s" % offences


def test_g5_gate_is_not_vacuous():
    """Guard the guard: the forbidden patterns really do match 0.2.0's text."""
    old = "No specific risks identified beyond standard credit considerations."
    assert any(p.search(old) for p in FORBIDDEN_CLAIMS)
    # ...and the ruled replacement is not itself an offence.
    allowed = _ruled_spans(RULED_NO_RISKS_TEXT)
    for pattern in FORBIDDEN_CLAIMS:
        for match in pattern.finditer(RULED_NO_RISKS_TEXT):
            assert any(a <= match.start() and match.end() <= b for a, b in allowed)


# ── G6 — the seven flags are three-state ─────────────────────────────────────

BORROWER_FLAGS = ["is_cdfi_certified", "is_mdi"]
IMPACT_FLAGS = ["is_low_income_area", "is_nmtc_eligible", "is_opportunity_zone",
                "is_minority_borrower", "is_women_borrower"]
ALL_FLAGS = BORROWER_FLAGS + IMPACT_FLAGS


def _render_with_flag(flag, value):
    if flag in BORROWER_FLAGS:
        borrower = BorrowerProfile(
            name="Test Borrower", borrower_type="nonprofit", sector="healthcare",
            state="IL", city="Chicago", **{flag: value})
        return CreditMemo(_deal(borrower=borrower)).to_markdown()
    return CreditMemo(_deal(impact=ImpactData(**{flag: value}))).to_markdown()


@pytest.mark.parametrize("flag", ALL_FLAGS)
def test_g6_true_false_and_none_render_three_distinct_memos(flag):
    """
    G6. True affirms, False states the negative explicitly, None says nothing.

    Until 0.2.1 all seven were `bool = False`, so False and "never touched"
    were the same value and produced byte-identical memos — the package could
    not represent "we checked, and the answer is no".

    Red-proof (must fail): collapse the False branch into the None branch, i.e.
    render only `is True` and drop the negative line.
    Observed: 7 failed, one per flag.
    """
    yes, no, unset = (_render_with_flag(flag, True),
                      _render_with_flag(flag, False),
                      _render_with_flag(flag, None))
    assert yes != no, f"{flag}: True and False render identically"
    assert no != unset, f"{flag}: False renders the same as unset"
    assert yes != unset, f"{flag}: True renders the same as unset"


@pytest.mark.parametrize("flag", ALL_FLAGS)
def test_g6_none_is_the_default_and_renders_nothing_extra(flag):
    """
    R4 is output-neutral for callers who omit these fields: they move from
    False-rendered-as-nothing to None-rendered-as-nothing.
    """
    assert _render_with_flag(flag, None) == CreditMemo(_deal()).to_markdown()


def test_g6_a_section_of_all_none_flags_says_so():
    """R4: no bare heading with nothing under it."""
    md = CreditMemo(_deal(impact=ImpactData())).to_markdown()
    assert "No target-market or eligibility flags were provided." in md
    assert "### Target Market & Eligibility\n\n---" not in md
    md = CreditMemo(_deal()).to_markdown()
    assert "No certification or designation flags were provided." in md


# ── G7 — no invented tax status ──────────────────────────────────────────────

def test_g7_a_nonprofit_memo_never_asserts_a_501_status():
    """
    G7. `nonprofit` is the only value available for a 501(c)(4) advocacy
    organisation, a 501(c)(6) trade association, a church or a tribal
    nonprofit. Asserting 501(c)(3) to an IC is an invented, checkable legal
    fact, and it bears on charitable purpose, grant eligibility and UBIT.

    Red-proof (must fail): restore "(501c3)" in BORROWER_TYPES.
    Observed: 2 failed (this gate and the package-source gate below).
    """
    md = CreditMemo(_deal()).to_markdown()
    assert "Nonprofit organization" in md
    assert "501" not in md


def test_g7_no_shipped_module_mentions_a_501_status():
    for path in _package_sources():
        text = io.open(path, encoding="utf-8").read()
        assert "501" not in text, f"{path.relative_to(ROOT)} names a 501 status"


# ── G8 — every rendered line survives being read alone ───────────────────────

#: A `**bold**` span and the text beside it are separate *runs*: that is how
#: Markdown renders them, how renderers/docx.py emits them (a Word run with
#: bold set, then a plain one), and how a reader skimming a memo takes them in.
#: A claim is only negated if the negation reaches the run the claim is in —
#: a negation stranded in a neighbouring run leaves the claim asserting itself.
_BOLD_RUN = re.compile(r"(\*\*.*?\*\*)")
_NEGATION = re.compile(r"\b(not|no|never|nor|neither)\b", re.I)
_LEADING_DECORATION = re.compile(r"^[^0-9A-Za-z(]+")


def _runs(line):
    """The runs of a rendered line, decoration and emphasis markers stripped."""
    parts = [p.strip(" *\t-•") for p in _BOLD_RUN.split(line)]
    return [_LEADING_DECORATION.sub("", p).strip() for p in parts if p.strip(" *\t-•")]


def _lines_added_by(rendering, baseline):
    """The lines `rendering` has that the all-`None` `baseline` does not."""
    absent = set(baseline.splitlines())
    return [ln for ln in rendering.splitlines() if ln.strip() and ln not in absent]


@pytest.mark.parametrize("flag", ALL_FLAGS)
def test_g8_a_false_flag_never_leaves_the_affirmative_claim_unnegated(flag):
    """
    G8. Every line the negative branch renders must survive being read alone.

    Through 0.2.1 the borrower certification block put the negation in a shared
    header and reused the affirmative label list under it, so `is_cdfi_certified
    =False` rendered `**Not certified:** CDFI Certified` — a sentence that
    contradicts itself, and that reaches the Word document as the sentence
    "Not certified: CDFI Certified", the emphasis markers flattened on the way.
    `Minority Depository
    Institution (MDI)` read acceptably under the same header only because it is
    a bare noun phrase; the construction was wrong for any label carrying a past
    participle, and one of the two did.

    The affirmative claim is taken from the flag's `True` rendering, not from
    any declaration the renderer reads, so the gate compares two independently
    produced outputs.

    Note this is a *run*-level property, not substring absence. The impact
    section's negatives contain their affirmative label as a substring
    ("Not a Low-Income Area") and are correct, because the negation sits in the
    same run as the label; a naive substring check would red on them and be
    wrong.

    Red-proof (must fail): restore the header-plus-affirmative-label
    construction in creditmemo/sections/borrower.py.
    Observed: 2 failed (is_cdfi_certified, is_mdi).
    """
    unset = _render_with_flag(flag, None)
    claims = {run for line in _lines_added_by(_render_with_flag(flag, True), unset)
              for run in _runs(line)[-1:]}
    assert claims, f"{flag}: True rendered no affirmative claim to compare against"

    for line in _lines_added_by(_render_with_flag(flag, False), unset):
        for run in _runs(line):
            for claim in claims:
                at = run.lower().find(claim.lower())
                if at == -1:
                    continue
                assert _NEGATION.search(run[:at]), (
                    f"{flag}: the negative rendering asserts {claim!r} in a run "
                    f"that does not negate it: {run!r} (line: {line!r})")


# ── Defects found while building the above, not named in the build prompt ────

def test_a_supplied_zero_is_not_discarded_as_if_it_were_absent():
    """
    Every Optional financial field is tested with `is not None`, never for
    truthiness.

    Through 0.2.0 the Balance Sheet block was gated on
    `any([total_assets, total_liabilities, net_assets_equity])` and each row on
    a bare `if f.<field>:`. Two consequences, both silent:

      * `FinancialData(cash=450_000)` rendered no Balance Sheet section at all
        — the one figure supplied was the only one never consulted by the gate;
      * a supplied 0 — no cash on hand, no net income, a fully depreciated
        asset base — was indistinguishable from a field nobody filled in, and
        a zero cash balance is among the most material numbers in a credit file.

    Red-proof (must fail): change any `is not None` back to truthiness in
    creditmemo/sections/financial.py — the section gate
    (`has_balance`), the cash row, or the total-assets row.
    Observed: 1 failed for each of the three.
    """
    # The section gate: cash used to be consulted only *after* three other
    # fields had already decided the section did not exist.
    md = CreditMemo(_deal(financials=FinancialData(cash=450_000))).to_markdown()
    assert "Balance Sheet" in md, "the only figure supplied was dropped"
    assert "| Cash & Equivalents | $450,000 |" in md

    # A supplied zero is a number, not an absence — in either position.
    md = CreditMemo(_deal(financials=FinancialData(cash=0))).to_markdown()
    assert "| Cash & Equivalents | $0 |" in md, "a supplied zero was dropped"

    md = CreditMemo(_deal(financials=FinancialData(
        total_assets=0, total_liabilities=3_500_000))).to_markdown()
    assert "| Total Assets | $0 |" in md, "a supplied zero was dropped"


def test_a_borrower_zero_is_not_discarded_either():
    borrower = BorrowerProfile(
        name="N", borrower_type="nonprofit", sector="healthcare", state="IL",
        city="Chicago", total_assets=0.0)
    md = CreditMemo(_deal(borrower=borrower)).to_markdown()
    assert "Financial Snapshot" in md
    assert "**Total Assets:** $0" in md


def test_prose_that_begins_with_a_pipe_stays_prose(tmp_path):
    """
    A leading '|' alone used to make a line a table.

    `deal_summary="| we structured this as a leveraged loan"` left the Markdown
    exactly as written and arrived in the .docx as a one-cell Word table with
    the pipe eaten — underwriter narrative silently restructured into data.
    A run of pipe lines is now a table only if it carries a delimiter rule
    where GFM requires one, which every table this package emits does.

    Red-proof (must fail): drop the separator_index check from
    creditmemo.tables.iter_segments.
    Observed: 1 failed.
    """
    docx = pytest.importorskip("docx")
    sentence = "| we structured this as a leveraged loan"
    deal = _deal(deal_summary=sentence)
    assert sentence in CreditMemo(deal).to_markdown()
    path = str(tmp_path / "pipe_prose.docx")
    CreditMemo(deal).save_docx(path)
    doc = docx.Document(path)
    assert sentence in [p.text for p in doc.paragraphs], "prose became a table"
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    assert "we structured this as a leveraged loan" not in cells


def test_prose_that_begins_with_three_dashes_is_not_deleted(tmp_path):
    """
    The horizontal-rule branch matched `startswith("---")`, so underwriter
    prose beginning with a dash run — "--- see appendix" — was replaced by a
    rule and the sentence was gone from the Word document entirely. Nothing
    raised; the .docx saved and reported success. The rule line is now matched
    exactly, which is the only form the Markdown renderer emits.

    Red-proof (must fail): change `line.strip() == RULE_LINE` back to
    `line.startswith("---")`.
    Observed: 1 failed.
    """
    docx = pytest.importorskip("docx")
    sentence = "--- see appendix B for the full rent roll"
    deal = _deal(deal_summary=sentence)
    path = str(tmp_path / "dash_prose.docx")
    CreditMemo(deal).save_docx(path)
    doc = docx.Document(path)
    assert any("see appendix B" in p.text for p in doc.paragraphs), \
        "the sentence was deleted from the Word document"


def test_no_markdown_emphasis_markers_survive_into_the_word_document(tmp_path):
    """
    Only the plain-paragraph branch stripped `**`. Bullets kept theirs, so
    `- **Total Assets:** $8.00MM` reached Word as the literal characters
    `**Total Assets:** $8.00MM` — raw Markdown in the IC's document.

    Red-proof (must fail): drop _clean() from the bullet branch of the renderer.
    Observed: 1 failed.
    """
    docx = pytest.importorskip("docx")
    borrower = BorrowerProfile(
        name="N", borrower_type="nonprofit", sector="healthcare", state="IL",
        city="Chicago", total_assets=8_000_000, annual_revenue=3_200_000)
    path = str(tmp_path / "emphasis.docx")
    CreditMemo(_deal(borrower=borrower)).save_docx(path)
    doc = docx.Document(path)
    texts = [p.text for p in doc.paragraphs]
    texts += [c.text for t in doc.tables for r in t.rows for c in r.cells]
    offenders = [t for t in texts if "**" in t]
    assert not offenders, f"literal Markdown emphasis in the .docx: {offenders}"
    assert "Total Assets: $8.00MM" in texts


def test_a_date_object_survives_both_renderers(tmp_path):
    """
    The 0.2.1 carry, verified to still reproduce on 0.2.0 before being fixed:
    a datetime.date in prepared_date rendered fine in Markdown and raised
    `TypeError: 'datetime.date' object is not iterable` in save_docx.

    It raised because the hand-built header table wrote the raw DealProfile
    value straight into a Word cell, while the Markdown path interpolated it
    into an f-string. Removing that table (R5) removes the only place the two
    paths could disagree about types, so this is fixed by R5 rather than by a
    cast — and this gate is what says so.

    Red-proof (must fail): restore the hand-built header table.
    Observed: 1 failed, with the original TypeError.
    """
    docx = pytest.importorskip("docx")
    deal = _deal()
    deal.prepared_date = datetime.date(2026, 5, 6)
    assert "2026-05-06" in CreditMemo(deal).to_markdown()
    path = str(tmp_path / "dated.docx")
    CreditMemo(deal).save_docx(path)
    doc = docx.Document(path)
    assert any("2026-05-06" in p.text for p in doc.paragraphs)


# ── The README's table list is the memo's table list ─────────────────────────

#: (the Markdown heading that introduces a table, the phrase README.md uses for
#: it in the Word-output section). Written out here because it is the reviewed
#: surface: a table added to the memo, or a phrase edited out of the README,
#: has to appear as a diff in this file.
#:
#: F14. This listed one risk table and the fixture below carried one `High`
#: risk, so `### Medium Risk Factors` and `### Low Risk Factors` fell outside
#: both this list and the assertion — and the gate's
#: `len(doc.tables) == len(DOCUMENTED_TABLES)` would have *failed* on a deal
#: with all three severities, which is the ordinary case. A memo with all three
#: renders twelve tables, not ten; measured, and README.md now says twelve.
#: The fixture carries all three so the gate sees the memo the README describes.
DOCUMENTED_TABLES = [
    ("### Deal Summary",                       "deal summary"),
    ("### Proposed Terms",                     "proposed terms"),
    ("### NMTC Structure",                     "NMTC structure"),
    ("### Historical Financial Summary",       "historical financials"),
    ("### Balance Sheet Summary (Most Recent)", "balance sheet summary"),
    ("### Key Credit Metrics",                 "credit metrics"),
    ("### Financial Projections",              "projections"),
    ("### Community Impact Metrics",           "impact metrics"),
    ("### High Risk Factors",                  "high risk factors"),
    ("### Medium Risk Factors",                "medium risk factors"),
    ("### Low Risk Factors",                   "low risk factors"),
    ("### Approval",                           "IC signature block"),
]


def _fully_populated_deal():
    """
    A deal that renders every table the package can render — which means all
    three risk severities, one table each. F14.
    """
    return _deal(
        loan_terms=LoanTerms(deal_type="nmtc", amount=2_500_000,
                             interest_rate=0.045, term_years=10,
                             min_dscr_covenant=1.20, max_ltv=0.75),
        financials=FinancialData(
            revenue_y1=2_800_000, revenue_y3=3_200_000,
            total_assets=8_000_000, cash=450_000,
            dscr=1.35, ltv=75.0, projected_dscr_y1=1.38),
        impact=ImpactData(jobs_created=18),
        risks=[RiskFactor(category="Credit", description="Concentration",
                          severity="High", mitigant="Guaranty"),
               RiskFactor(category="Market", description="Reimbursement rates",
                          severity="Medium", mitigant="Conservative projections"),
               RiskFactor(category="Operational", description="Key person",
                          severity="Low", mitigant="Succession plan")],
        nmtc_terms=NMTCTerms(
            nmtc_allocation=10_000_000, credit_price=0.83,
            leverage_loan_rate=0.045, qlici_a_rate=0.045, qlici_b_rate=0.0,
            cde_fee_rate=0.02),
        conditions=["Receipt of final appraisal"])


def _table_headings(md):
    """The heading above each Markdown table block, in document order."""
    lines = md.split("\n")
    headings = []
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        if i and lines[i - 1].startswith("|"):
            continue
        j = i - 1
        while j >= 0 and not lines[j].startswith("#"):
            j -= 1
        headings.append(lines[j] if j >= 0 else "(no heading)")
    return headings


def test_the_readme_names_every_table_the_memo_renders(tmp_path):
    """
    The README enumerated nine tables in the Word-output section and the memo
    renders ten: **Balance Sheet Summary** was missing from the list, and it is
    the one an IC reads for the borrower's cash position. Nothing was wrong with
    the code; a reader counting tables against the README would have concluded
    one had been dropped.

    F14. The fixture then carried a single `High` risk, so the two other
    severity tables were outside the list *and* outside the assertion, and this
    gate would have reddened on any deal with all three — the ordinary case.
    Measured: twelve tables with all three severities. The fixture carries all
    three and the README says twelve.

    Three things are checked together, because any one of them alone drifts:
    the memo's own table headings, the count of real Word tables in the saved
    .docx, and the README phrase for each.

    Red-proof (must fail): delete "balance sheet summary" from the Word output
    section of README.md.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: 1 failed, 426 passed — "tables the README does not name:
    ['### Balance Sheet Summary (Most Recent)']". (The passed count moved with
    the suite; the failure is the same one.)

    Second red-proof (must fail), for F14: revert `_fully_populated_deal` to the
    single `High` risk it carried. Observed: 1 failed, 426 passed — the
    rendered table list no longer matches the declared one.
    """
    pytest.importorskip("docx")
    import docx as _docx

    deal = _fully_populated_deal()
    md = CreditMemo(deal).to_markdown()
    rendered = _table_headings(md)
    declared = [heading for heading, _ in DOCUMENTED_TABLES]
    assert rendered == declared, (
        f"the memo's tables are not the ones this gate declares.\n"
        f"rendered: {rendered}\ndeclared: {declared}")

    path = str(tmp_path / "tables.docx")
    CreditMemo(deal).save_docx(path)
    assert len(_docx.Document(path).tables) == len(DOCUMENTED_TABLES), (
        f"{len(_docx.Document(path).tables)} Word tables for "
        f"{len(DOCUMENTED_TABLES)} Markdown tables")

    readme = io.open(ROOT / "README.md", encoding="utf-8").read().lower()
    unnamed = [heading for heading, phrase in DOCUMENTED_TABLES
               if phrase.lower() not in readme]
    assert not unnamed, f"tables the README does not name: {unnamed}"


# ── Control characters: a refusal that names what it refused ─────────────────

#: (label, the character, whether Word can store it). The accepted three are
#: here so the gate cannot pass by refusing everything.
CONTROL_CHARACTERS = [
    ("vertical_tab",   "\x0b", False),
    ("form_feed",      "\x0c", False),
    ("nul",            "\x00", False),
    ("bell",           "\x07", False),
    ("escape",         "\x1b", False),
    ("tab",            "\t",   True),
    ("newline",        "\n",   True),
    ("delete",         "\x7f", True),
]


@pytest.mark.parametrize("label,char,storable", CONTROL_CHARACTERS,
                         ids=[c[0] for c in CONTROL_CHARACTERS])
def test_a_control_character_is_refused_by_name_or_stored(
    label, char, storable, tmp_path
):
    r"""
    A control character in underwriter text is routine — `\x0b` and `\x0c` are
    what a paste out of a PDF leaves behind — and `save_markdown` accepts them.
    `save_docx` did not, and said so like this:

        ValueError: All strings must be XML compatible: Unicode or ASCII,
        no NULL bytes or control characters

    raised from lxml, naming no field, no line, no character and no file, after
    the caller had already been told the Markdown was written. The file is not
    written either way; nothing is sanitised, because substituting or deleting a
    character is the silent alteration this release exists to remove. What
    changed is that the refusal now names the codepoint and the line.

    The three storable characters are in the same parametrisation so that a
    renderer which refused *everything* — or which sanitised, and so refused
    nothing — cannot pass.

    Red-proof (must fail): delete the `_reject_control_characters(lines)` call
    from creditmemo/renderers/docx.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: 5 failed, 335 passed — the five unstorable characters — each
    raising lxml's unnamed message instead.
    """
    pytest.importorskip("docx")
    deal = _deal(deal_summary=f"Sourced from the PDF{char}continued here.")
    memo = CreditMemo(deal)

    # The Markdown half takes it either way; that is the asymmetry.
    memo.save_markdown(str(tmp_path / f"{label}.md"))

    path = str(tmp_path / f"{label}.docx")
    if storable:
        memo.save_docx(path)
        return
    with pytest.raises(ValueError) as error:
        memo.save_docx(path)
    message = str(error.value)
    assert f"U+{ord(char):04X}" in message, (
        f"{label}: the refusal does not name the character: {message!r}")
    assert "memo line" in message, (
        f"{label}: the refusal does not say where: {message!r}")
    assert "XML compatible" not in message, (
        f"{label}: this is still lxml's unnamed message: {message!r}")


# ── G13 — Word supplies no number, and loses none ────────────────────────────
#
# R17. 0.2.1 restyled every ordered-list line into Word's `List Number` style,
# emitting only the text after the number and letting Word draw its own. The
# test this replaces asserted exactly that, and passed. What it did not assert
# is what Word then prints, and Word does not restart a list: every `List
# Number` paragraph in a python-docx document inherits one continuous numbering
# definition (`numId=5`, resolved from the style, with no paragraph-level
# `w:numPr` anywhere to override it).
#
# Measured at 2031b0a on a deal with a two-item ordered list in `deal_summary`
# and three `conditions`. The Markdown reads
#
#     1. Execute the loan agreement          <- deal_summary
#     2. Fund the escrow
#     1. Receipt of final appraisal          <- Conditions of Approval
#     2. Evidence of matching funds
#     3. Environmental review
#
# and the .docx holds five `List Number` paragraphs whose text has the number
# stripped, all on the one definition. Word therefore prints the Conditions of
# Approval as 3, 4, 5 — a numbered condition list, in an Investment Committee
# memo, whose numbers are not the ones the memo's own Markdown states.
#
# The same restyling has a second route to the same class of loss. A condition
# with an embedded newline:
#
#     conditions=["Receipt of appraisal",
#                 "Payoff of the 2019 note\n3. Third-party report"]
#
# renders as a 1,2,3 run in the Markdown, and the caller's own literal "3." on
# the continuation line is deleted on the way into Word. That made the claim in
# `_ordered_item_lines` — "No input loses a number the caller wrote" — false as
# written, by a route its run-of-1..n rule was not looking at.
#
# THE RULING (R17): ordered items are plain `Normal` paragraphs whose text
# carries the number exactly as the Markdown has it. No `List Number` anywhere.
# `List Bullet` stays: a bullet glyph carries no information, so letting Word
# draw it substitutes nothing. A number is a value the underwriter wrote.
#
# The alternative — per-paragraph `w:numPr` with `w:startOverride` — would also
# work and was rejected: it is raw OOXML surgery that would need auditing of its
# own, against a governing principle that already says worst case a list loses
# its styling, no case loses a number the caller wrote.

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: The one numbering format Word may supply on this package's behalf. A bullet
#: glyph says what the "- " in the Markdown said; a numeral says something the
#: Markdown may not say at all.
PERMITTED_NUMFMT = "bullet"


def _numbering_format(doc, paragraph):
    """
    What Word draws in the margin for `paragraph`, or None if it draws nothing.

    Resolved the way Word resolves it: a paragraph-level `w:numPr` wins,
    otherwise the style chain is walked to its base. The `w:numId` found is
    mapped through `numbering.xml`'s `w:num` -> `w:abstractNum` -> first
    `w:lvl` to the `w:numFmt` value — "bullet", "decimal", "lowerRoman", and so
    on. Nothing here is imported from creditmemo; this reads the saved file.
    """
    num_id = None
    pPr = paragraph._p.pPr
    if pPr is not None:
        num_pr = pPr.find(_W + "numPr")
        if num_pr is not None and num_pr.find(_W + "numId") is not None:
            num_id = num_pr.find(_W + "numId").get(_W + "val")
    if num_id is None:
        style = paragraph.style
        while style is not None:
            style_pPr = style.element.find(_W + "pPr")
            if style_pPr is not None:
                num_pr = style_pPr.find(_W + "numPr")
                if num_pr is not None and num_pr.find(_W + "numId") is not None:
                    num_id = num_pr.find(_W + "numId").get(_W + "val")
                    break
            style = style.base_style
    if num_id is None:
        return None
    numbering = doc.part.numbering_part.element
    for num in numbering.findall(_W + "num"):
        if num.get(_W + "numId") != num_id:
            continue
        abstract_id = num.find(_W + "abstractNumId").get(_W + "val")
        for abstract in numbering.findall(_W + "abstractNum"):
            if abstract.get(_W + "abstractNumId") == abstract_id:
                lvl = abstract.find(_W + "lvl")
                if lvl is None:
                    return None
                fmt = lvl.find(_W + "numFmt")
                return None if fmt is None else fmt.get(_W + "val")
    return None


#: The two shapes R17 was measured on, each as (label, DealProfile kwargs).
#:
#: The first is the blocking one: two independent ordered runs in one document,
#: which is what makes Word's continuation visible. The second is the route
#: through a caller string that carries its own newline and its own number.
G13_DEALS = [
    ("two_runs", dict(
        deal_summary=("Closing sequence:\n"
                      "1. Execute the loan agreement\n"
                      "2. Fund the escrow"),
        conditions=["Receipt of final appraisal",
                    "Evidence of matching funds",
                    "Environmental review"])),
    ("embedded_number", dict(
        conditions=["Receipt of appraisal",
                    "Payoff of the 2019 note\n3. Third-party report"])),
    ("chronology", dict(
        deal_summary=("2019. The borrower refinanced its senior debt at 4.2%.\n"
                      "2024. The borrower drew $1.2MM on the line."))),
]


@pytest.mark.parametrize("label,kwargs", G13_DEALS, ids=[d[0] for d in G13_DEALS])
def test_g13_every_ordered_number_in_the_markdown_is_in_the_word_document(
    label, kwargs, tmp_path
):
    r"""
    G13, half one. Every line the Markdown begins with a number, the Word
    document holds verbatim — number included, in a paragraph of its own.

    Ground truth is the Markdown the same deal produces, not a list written out
    here, and the comparison is of whole lines: a gate that compared only the
    text after the number could not see the number go missing, which is the
    blind spot the gate this replaces had.

    Red-proof (must fail): restore 2031b0a's renderer whole —
    `git show 2031b0a:creditmemo/renderers/docx.py > creditmemo/renderers/docx.py`
    — which is the `List Number` branch with its run-of-1..n restriction.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed, with only the ordered-item branch put back and the rest of the
    renderer left alone: 9 failed, 331 passed — 2 here (two_runs,
    embedded_number), 2 in G13's other half, 1 in the declaration gate, and 4 in
    tests/test_docx.py (G1 and G1-prose, loan and nmtc). Reverting the whole
    file to 2031b0a gives 14 failed, 326 passed; the extra 5 are the
    control-character gate, whose check the same revert removes.

    `chronology` stays green under that mutation and is not slack: 2031b0a's
    run-of-1..n rule deliberately left it alone, so it is the shape that
    distinguishes that restriction from the unrestricted branch of 0.2.0, which
    reddens all three.

    At 2031b0a, with `List Number` live, the suite was 284 passed. No gate that
    existed before this round fails on the restoration, and the one gate that
    named the style asserted its presence — which is why the defect shipped as
    far as it did.
    """
    pytest.importorskip("docx")
    import docx as _docx

    deal = _deal(**kwargs)
    md = CreditMemo(deal).to_markdown()
    ordered = [line for line in md.split("\n")
               if re.match(r"^\d+\.\s", line)]
    assert ordered, f"{label}: no ordered line in the Markdown — gate is vacuous"

    path = str(tmp_path / f"{label}.docx")
    CreditMemo(deal).save_docx(path)
    doc = _docx.Document(path)
    paragraphs = [p.text for p in doc.paragraphs]

    for line in ordered:
        assert line in paragraphs, (
            f"{label}: the Markdown line {line!r} is not a paragraph of the "
            f"Word document. Word document paragraphs beginning with a digit: "
            f"{[p for p in paragraphs if p[:1].isdigit()]}")


@pytest.mark.parametrize("label,kwargs", G13_DEALS, ids=[d[0] for d in G13_DEALS])
def test_g13_word_supplies_no_number_in_the_document(label, kwargs, tmp_path):
    """
    G13, half two. No paragraph in the document gets its number from Word.

    Half one would still pass if the renderer both kept the number in the text
    *and* put the paragraph on a numbered list definition — the reader would
    then see "1. 1. Execute the loan agreement", or worse, "3. 1. Receipt of
    final appraisal". So the numbering definition every paragraph resolves to is
    read out of the saved file and required to draw a bullet or nothing.

    Red-proof (must fail): restore 2031b0a's renderer whole —
    `git show 2031b0a:creditmemo/renderers/docx.py > creditmemo/renderers/docx.py`.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: 9 failed, 331 passed; 2 of them here — two_runs and
    embedded_number — each naming numFmt='decimal' on the paragraphs Word
    would have numbered itself.
    """
    pytest.importorskip("docx")
    import docx as _docx

    deal = _deal(**kwargs)
    path = str(tmp_path / f"{label}-numbering.docx")
    CreditMemo(deal).save_docx(path)
    doc = _docx.Document(path)

    supplied = [(p.style.name, p.text, _numbering_format(doc, p))
                for p in doc.paragraphs
                if _numbering_format(doc, p) not in (None, PERMITTED_NUMFMT)]
    assert not supplied, (
        f"{label}: Word supplies the number for these paragraphs: {supplied}")


def test_g13_is_not_vacuous(tmp_path):
    """
    Guard the guard, twice over.

    `_numbering_format` has to be able to *see* a Word-supplied number, or half
    two passes on any document at all. So a `List Number` paragraph is built
    here directly with python-docx — outside the package — and the helper is
    required to report a non-bullet format for it, and "bullet" for a
    `List Bullet` one.

    And the memo really does put bullets on the bullet style, so "no numbering"
    is not being satisfied by the renderer having stopped styling lists at all.
    """
    pytest.importorskip("docx")
    import docx as _docx

    probe = _docx.Document()
    probe.add_paragraph("a number", style="List Number")
    probe.add_paragraph("a bullet", style="List Bullet")
    probe_path = str(tmp_path / "probe.docx")
    probe.save(probe_path)
    probe = _docx.Document(probe_path)
    formats = [_numbering_format(probe, p) for p in probe.paragraphs]
    assert formats[0] not in (None, PERMITTED_NUMFMT), (
        f"the helper cannot see a Word-supplied number: {formats[0]!r}")
    assert formats[1] == PERMITTED_NUMFMT, (
        f"the helper does not recognise a bullet: {formats[1]!r}")

    deal = _deal(conditions=["Receipt of final appraisal", "Evidence of match"])
    path = str(tmp_path / "bullets.docx")
    CreditMemo(deal).save_docx(path)
    doc = _docx.Document(path)
    assert any(_numbering_format(doc, p) == PERMITTED_NUMFMT
               for p in doc.paragraphs), (
        "no bulleted paragraph in the memo — half two would pass vacuously")


def test_g13_no_shipped_module_asks_word_for_a_number():
    """
    G13's declaration half: the ruling, stated where a reader of the renderer
    will meet it, and pinned so that reintroducing the style is a visible diff
    in this file rather than a silent one in the renderer.
    """
    from creditmemo.renderers import docx as docx_renderer

    import ast

    assert docx_renderer.BULLET_STYLE == "List Bullet"
    assert not hasattr(docx_renderer, "NUMBER_STYLE"), (
        "the renderer declares a numbered list style again — see R17")

    # String *constants*, not source text: R17 is a ruling worth writing down,
    # and the renderer's own docstring names the style in order to say why it
    # is gone. A prose mention is the record; a live literal is the defect. So
    # docstrings are subtracted and comments never enter the AST at all.
    live = []
    for path in _package_sources():
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    docstrings.add(id(body[0].value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings
                    and "List Number" in node.value):
                live.append(f"{path.name}:{node.lineno}")
    assert not live, (
        f"a shipped module has a live 'List Number' string literal: {live} "
        f"— see R17")


def test_section_rules_are_word_borders_not_rows_of_underscores(tmp_path):
    """
    The rule between sections was a paragraph of sixty literal underscores:
    selectable text that does not span the column, does not follow the page
    margins and lands in every copy-paste of the memo.
    """
    docx = pytest.importorskip("docx")
    path = str(tmp_path / "rules.docx")
    CreditMemo(_deal()).save_docx(path)
    doc = docx.Document(path)
    assert not any("____" in p.text for p in doc.paragraphs)
    bordered = [p for p in doc.paragraphs
                if p._p.find(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr"
                ) is not None
                and p._p.pPr.find(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pBdr"
                ) is not None]
    assert bordered, "no bordered paragraph — the rules are gone entirely"



#: R10/G8 addendum. Every flag's affirmative and negative, pinned as literals.
#:
#: The constants themselves are the reviewed surface: these are written out
#: here rather than imported, so that changing a negative string in
#: creditmemo/sections/ cannot be done without the change also appearing as a
#: diff in this file, in front of whoever reviews it.
DECLARED_FLAG_TEXT = {
    "is_cdfi_certified":   ("CDFI Certified",
                            "Not CDFI certified"),
    "is_mdi":              ("Minority Depository Institution (MDI)",
                            "Not a Minority Depository Institution (MDI)"),
    "is_low_income_area":  ("Low-Income Area",
                            "Not a Low-Income Area"),
    "is_nmtc_eligible":    ("NMTC Eligible Census Tract",
                            "Not an NMTC Eligible Census Tract"),
    "is_opportunity_zone": ("Opportunity Zone",
                            "Not an Opportunity Zone"),
    "is_minority_borrower": ("Minority Borrower",
                             "Not a Minority Borrower"),
    "is_women_borrower":   ("Women Borrower",
                            "Not a Women Borrower"),
}


def _declared_flags():
    from creditmemo.sections import borrower as borrower_section
    from creditmemo.sections import impact as impact_section
    return {attr: (yes, no) for attr, yes, no
            in (*borrower_section.CERTIFICATION_FLAGS,
                *impact_section.TARGET_MARKET_FLAGS)}


@pytest.mark.parametrize("flag", ALL_FLAGS)
def test_g8_a_rendered_negative_is_the_flags_declared_negative_constant(flag):
    """
    G8 addendum, per R10.

    The audit showed that `- ❌ No longer relevant: CDFI Certified` passes the
    run-level gate above, because `_NEGATION` matches the unrelated "No" earlier
    in the run. That is a real limit and it cannot be closed by a smarter regex.

    So this gate stops trying to decide negation and pins the rendering instead:
    each flag renders exactly its declared negative constant, and each constant
    is exactly the literal in DECLARED_FLAG_TEXT above. The constants become the
    reviewed surface — a change to any of them fails here and shows as a diff in
    this file — rather than a string the renderer can quietly rewrite.

    THE RESIDUAL LIMIT, STATED PLAINLY: no gate in this suite can tell whether a
    declared negative constant actually negates its affirmative. If someone sets
    the constant for `is_cdfi_certified` to "No longer relevant: CDFI Certified",
    this gate and the run-level gate above will both go green as soon as the
    literal here is updated to match, and the memo will assert to an Investment
    Committee something the caller did not say. That is a code-review property,
    not a machine-checkable one. This class is not closed; it is narrowed to one
    reviewed table of fourteen strings.

    Red-proof (must fail): change any negative in
    creditmemo/sections/borrower.py or creditmemo/sections/impact.py.
    Observed: 2 failed per changed constant (this gate and the declaration gate
    below).
    """
    yes, no = DECLARED_FLAG_TEXT[flag]
    unset = _render_with_flag(flag, None)

    assert _lines_added_by(_render_with_flag(flag, False), unset) == [f"- ❌ {no}"], (
        f"{flag}: the False rendering is not exactly its declared negative")
    assert _lines_added_by(_render_with_flag(flag, True), unset) == [f"- ✅ {yes}"], (
        f"{flag}: the True rendering is not exactly its declared affirmative")


def test_g8_the_declared_flag_constants_are_the_reviewed_ones():
    """
    The other half of the addendum: the package's own constants must equal the
    literals pinned above, and the two flag tables must between them cover
    exactly the seven flags — no flag rendering through a string that was never
    reviewed here.
    """
    declared = _declared_flags()
    assert set(declared) == set(DECLARED_FLAG_TEXT) == set(ALL_FLAGS)
    for flag, (yes, no) in DECLARED_FLAG_TEXT.items():
        assert declared[flag] == (yes, no), (
            f"{flag}: the package declares {declared[flag]!r}, this suite "
            f"reviewed {(yes, no)!r}")


# ── G9 — a supplied zero is a number, in every section that shows it ──────────
#
# R6/F1. `interest_rate` and `term_years` are `Optional[...] = None`, so `0` is
# representable and distinguishable from "not supplied" — and both were tested
# for truthiness. Measured at 6d01957 with `interest_rate=0.0, term_years=0`:
#
#     | Interest Rate | N/A |        <- Executive Summary
#     | Term          | N/A |        <- Executive Summary
#     | Interest Rate | N/A |        <- Transaction Structure
#     | Loan Term     | 0 years |    <- Transaction Structure
#
# A 0% forgivable loan, an EQ2 note and a 0% QLICI B tranche are routine
# instruments for this package's callers. "N/A" tells the Investment Committee
# the rate is unknown when the caller stated it is zero — and the two sections
# disagreed with each other about the same field on the same deal.

#: Every numeric `Optional` field, the zero a caller might supply, and the text
#: the memo must show for it.
#:
#: The expected strings are written out here rather than produced with the
#: renderer's own formatter. Rule (i) — ground truth derived independently of
#: the declaration — and R8's extension of it — independently of the
#: transformation — both apply: a gate that formats its expectation by calling
#: `creditmemo.fields.rate` follows that function wherever it goes and can
#: never fail.
#: R24 added the fifth column. Through 0.2.1 the money rows expected
#: `"$0.00MM"` — which is also what a *supplied $4,999* produced, so the gate
#: for this release's central ruling asserted the violation's own output and
#: could not distinguish the property from its breach. The probe is a small
#: non-zero the row must NOT render as the zero text; every money row carries
#: the $4,999 that used to collapse.
#:
#: The ratio and rate rows carry a probe too, but a larger one, and that is a
#: disclosure rather than a choice: `_fmt_ratio` and `creditmemo.fields.rate`
#: still round a small non-zero into the zero rendering (`_fmt_ratio(0.001)` is
#: `"0.00x"`). R24 ruled on dollar magnitudes; the rest of the formatter
#: surface is 0.3.0, and this column is where that shows.
ZERO_RENDERINGS = [
    # (holder, field, the zero supplied, the text the memo must show,
    #  a non-zero that must NOT produce that text)
    ("loan_terms",     "interest_rate",        0.0, "0.00%", 0.045),
    # Full rows, not bare "0 years": the probe assertion R24 added found that
    # `"0 years"` is a substring of `"20 years"`, so an expectation written that
    # loosely reported the *amortization* row as proof about the *term* row.
    ("loan_terms",     "term_years",           0,   "| Loan Term | 0 years |", 5),
    ("loan_terms",     "amortization_years",   0,   "| Amortization | 0 years |", 20),
    ("loan_terms",     "min_dscr_covenant",    0.0, "Minimum DSCR of 0.00x", 1.20),
    ("loan_terms",     "max_ltv",              0.0, "Maximum LTV of 0.0%", 0.75),
    ("borrower",       "year_founded",         0,   "**Year Founded:** 0", 2005),
    ("borrower",       "total_assets",         0.0, "**Total Assets:** $0", 4_999),
    ("borrower",       "annual_revenue",       0.0, "**Annual Revenue:** $0", 4_999),
    ("financial_data", "revenue_y1",           0.0, "| Revenue | $0 | N/A | N/A |", 4_999),
    ("financial_data", "revenue_y2",           0.0, "| Revenue | N/A | $0 | N/A |", 4_999),
    ("financial_data", "revenue_y3",           0.0, "| Revenue | N/A | N/A | $0 |", 4_999),
    ("financial_data", "net_income_y1",        0.0, "| Net Income | $0 | N/A | N/A |", 4_999),
    ("financial_data", "net_income_y2",        0.0, "| Net Income | N/A | $0 | N/A |", 4_999),
    ("financial_data", "net_income_y3",        0.0, "| Net Income | N/A | N/A | $0 |", 4_999),
    ("financial_data", "ebitda_y1",            0.0, "| EBITDA | $0 | N/A | N/A |", 4_999),
    ("financial_data", "ebitda_y2",            0.0, "| EBITDA | N/A | $0 | N/A |", 4_999),
    ("financial_data", "ebitda_y3",            0.0, "| EBITDA | N/A | N/A | $0 |", 4_999),
    ("financial_data", "total_assets",         0.0, "| Total Assets | $0 |", 4_999),
    ("financial_data", "total_liabilities",    0.0, "| Total Liabilities | $0 |", 4_999),
    ("financial_data", "net_assets_equity",    0.0, "| Net Assets / Equity | $0 |", 4_999),
    ("financial_data", "cash",                 0.0, "| Cash & Equivalents | $0 |", 4_999),
    ("financial_data", "dscr",                 0.0, "0.00x", 1.35),
    ("financial_data", "current_ratio",        0.0, "0.00x", 1.80),
    ("financial_data", "debt_to_equity",       0.0, "0.00x", 0.78),
    # A fraction in (0, 1.0] raises rather than render a false LTV (R14/R20),
    # so the probe is on the percentage-point scale this field declares.
    ("financial_data", "ltv",                  0.0, "0.0%", 75.0),
    ("financial_data", "projected_revenue_y1", 0.0, "| Revenue | $0 | — | — |", 4_999),
    # The Projections DSCR row gated all three years on `projected_dscr_y1`,
    # so a supplied Year-2 or Year-3 figure was dropped and the section
    # rendered a header-only table — the `has_balance`/`cash` defect of
    # 0.2.0, still live in the block next door. Found by this gate's
    # coverage check, not by any list.
    ("financial_data", "projected_dscr_y1",    0.0, "| DSCR | 0.00x | N/A | N/A |", 1.38),
    ("financial_data", "projected_dscr_y2",    0.0, "| DSCR | N/A | 0.00x | N/A |", 1.42),
    ("financial_data", "projected_dscr_y3",    0.0, "| DSCR | N/A | N/A | 0.00x |", 1.47),
]

#: The `Optional[bool]` fields are gated by G6/G8, which already require the
#: `False` rendering to differ from both `True` and unset. Named here so this
#: gate's coverage claim can be checked against the schema.
ZERO_EXEMPT_OPTIONAL = set(ALL_FLAGS) | {
    # Optional[str]: the falsy value is "", which states nothing and whose
    # rendering would be a section heading over an empty body — the bare
    # heading R4 closed. See test_g9_the_optional_string_rule_is_stated.
    "ceo_name", "website", "mission", "description", "collateral", "guarantor",
    "use_of_proceeds", "closing_date", "maturity_date", "census_tract",
    "impact_narrative", "cde_name", "investor_name", "fund_name", "ic_date",
    "deal_summary",
    # Optional[NMTCTerms]: a dataclass with no __bool__/__len__ is always
    # truthy, so truthiness and `is not None` cannot disagree about it.
    "nmtc_terms",
}


def _deal_with_zero(holder, field, value):
    """A deal whose only unusual input is `holder.field = value`."""
    if holder == "loan_terms":
        kw = dict(deal_type="loan", amount=2_500_000)
        kw[field] = value
        return _deal(loan_terms=LoanTerms(**kw))
    if holder == "borrower":
        kw = dict(name="Test Borrower", borrower_type="nonprofit",
                  sector="healthcare", state="IL", city="Chicago")
        kw[field] = value
        return _deal(borrower=BorrowerProfile(**kw))
    if holder == "financial_data":
        return _deal(financials=FinancialData(**{field: value}))
    raise AssertionError(holder)


@pytest.mark.parametrize("holder,field,zero,expected,probe", ZERO_RENDERINGS,
                         ids=lambda v: v if isinstance(v, str) else None)
def test_g9_a_supplied_zero_renders_as_the_value(holder, field, zero, expected,
                                                 probe):
    """
    G9. A supplied `0` / `0.0` renders as the value — never as "N/A", never as
    an omitted row.

    Three renderings are measured, not one, because the first two alone let
    this gate pass on a package that does not have the property:

      * `expected` must be ABSENT when the field is `None` — so the gate cannot
        pass because some *other* field happens to produce the same text;
      * `expected` must be PRESENT when the field is zero;
      * `expected` must be ABSENT when the field holds `probe`, a non-zero.

    R24 added the third. Without it this gate asserted `"$0.00MM"` for a
    supplied zero — and `"$0.00MM"` was also what a supplied $4,999 produced,
    at every money site in the package. The gate for the ruling that a stated
    zero must reach the memo could not tell a stated zero from a figure the
    memo had destroyed, which is this release's signature failure: a gate that
    shares the blind spot of the thing it checks.

    Red-proof for the third assertion (must fail): in creditmemo/money.py,
    replace the body of `money` with the unconditional divide it replaced —
        return f"${value/1e6:,.2f}MM"
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: see G14's docstring, which reds on the same mutation.

    Red-proof (must fail): revert *both* `interest_rate` sites — the one in
    creditmemo/sections/executive.py and the one in
    creditmemo/sections/transaction.py — to a truthiness test.
    Observed: 2 failed — this gate's `interest_rate` row, and the cross-section
    gate below.

    Reverting one site alone reds only the cross-section gate, and that is the
    intended division of labour: this gate asks whether a supplied zero reaches
    the memo at all, the next asks whether every section agrees about it. Only
    the two together catch a field that one section prints and another does not.

    Second red-proof (must fail): revert the Projections DSCR row in
    creditmemo/sections/financial.py to `if f.projected_dscr_y1 is not None:`.
    Observed: 2 failed (projected_dscr_y2, projected_dscr_y3).
    """
    unset = CreditMemo(_deal_with_zero(holder, field, None)).to_markdown()
    assert expected not in unset, (
        f"{holder}.{field}: {expected!r} is in the memo even when the field is "
        "unset, so this gate would pass without the field being rendered")

    md = CreditMemo(_deal_with_zero(holder, field, zero)).to_markdown()
    assert expected in md, (
        f"{holder}.{field}={zero!r} was supplied and the memo does not show "
        f"{expected!r}")

    nonzero = CreditMemo(_deal_with_zero(holder, field, probe)).to_markdown()
    assert expected not in nonzero, (
        f"{holder}.{field}={probe!r} renders as {expected!r} — the text this "
        f"gate requires for a *stated zero*. The memo cannot distinguish the "
        f"figure the caller supplied from zero, and neither can this gate.")


#: The fields the Executive Summary and the Transaction Structure both show.
#: Two sections rendered `interest_rate` from two separate f-strings and
#: disagreed about `0.0`; they now go through one helper.
SHARED_ACROSS_SECTIONS = [
    ("interest_rate", [0.0, 0.045, 0.125], "%"),
    ("term_years",    [0, 1, 10],          " years"),
]


@pytest.mark.parametrize("field,values,mark", SHARED_ACROSS_SECTIONS)
def test_g9_a_shared_field_renders_identically_in_every_section(field, values, mark):
    """
    G9, second half. The same field must read the same way in every section
    that shows it, for every value including zero.

    Ground truth is the two rendered sections, compared against each other —
    not against any helper either of them calls.

    Red-proof (must fail): revert either section's site to truthiness.
    Observed: 1 failed (the 0 case) per reverted site.
    """
    for value in values:
        md = CreditMemo(_deal_with_zero(
            "loan_terms", field, value)).to_markdown()
        executive = md.split("## Borrower Profile")[0]
        transaction = md.split("## Transaction Structure")[1].split("## Financial")[0]

        def cells(section):
            return {c.strip() for line in section.splitlines()
                    if line.startswith("|") for c in line.split("|")
                    if mark in c and "N/A" not in c and set(c.strip()) - set("-: ")}

        in_exec, in_txn = cells(executive), cells(transaction)
        assert in_exec, f"{field}={value!r}: Executive Summary shows no value"
        assert in_txn, f"{field}={value!r}: Transaction Structure shows no value"
        assert in_exec == in_txn, (
            f"{field}={value!r}: Executive Summary says {sorted(in_exec)} and "
            f"Transaction Structure says {sorted(in_txn)}")


def test_g9_covers_every_optional_field_on_every_dataclass():
    """
    Guard the guard, and the answer to "the audit said four, I found three".

    Every `Optional` field on every dataclass in the schema is either in
    ZERO_RENDERINGS, or named in ZERO_EXEMPT_OPTIONAL with the reason it is
    exempt. A new `Optional` field cannot be added without a decision here.
    """
    import dataclasses
    import typing

    from creditmemo.data import schema as schema_module

    optional = set()
    for name in dir(schema_module):
        obj = getattr(schema_module, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        hints = typing.get_type_hints(obj)
        for f in dataclasses.fields(obj):
            t = hints[f.name]
            if (typing.get_origin(t) is typing.Union
                    and type(None) in typing.get_args(t)):
                optional.add(f.name)

    covered = {row[1] for row in ZERO_RENDERINGS}
    assert optional, "no Optional fields found — this gate would pass vacuously"
    missing = optional - covered - ZERO_EXEMPT_OPTIONAL
    assert not missing, f"Optional fields with no zero-rendering decision: {sorted(missing)}"
    stale = (covered | ZERO_EXEMPT_OPTIONAL) - optional
    assert not stale, f"named here but no longer Optional on any dataclass: {sorted(stale)}"


def test_g9_the_optional_string_rule_is_stated():
    """
    The one place this fix departs from "every `Optional` field is tested with
    `is not None`", stated as a behaviour rather than left implicit.

    For an `Optional[str]` the falsy value is `""`. An empty string is not a
    figure a caller stated; rendering it would put a section heading over an
    empty body, which is the defect R4 closed for the flag blocks. So `""` is
    treated as absence, uniformly, through one named predicate — and that is
    gated here so the exception is reviewed rather than incidental.
    """
    from creditmemo import fields as fields_module

    assert fields_module.is_supplied(0) is True
    assert fields_module.is_supplied(0.0) is True
    assert fields_module.is_supplied(False) is True
    assert fields_module.is_supplied(None) is False
    assert fields_module.is_supplied("") is False
    assert fields_module.is_supplied("x") is True

    borrower = BorrowerProfile(
        name="N", borrower_type="nonprofit", sector="healthcare", state="IL",
        city="Chicago", mission="")
    md = CreditMemo(_deal(borrower=borrower)).to_markdown()
    assert "### Mission" not in md, "an empty mission produced a bare heading"


def _optional_str_fields():
    """
    Every `Optional[str]` field in the schema, as (dataclass name, field name).

    Discovered from the annotations, not listed: a new optional string field is
    covered by the gate below the moment it is declared, without anyone
    remembering to add it here.
    """
    import dataclasses
    import typing

    from creditmemo.data import schema as schema_module

    found = []
    for name in dir(schema_module):
        obj = getattr(schema_module, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        hints = typing.get_type_hints(obj)
        for f in dataclasses.fields(obj):
            t = hints[f.name]
            args = typing.get_args(t)
            if (typing.get_origin(t) is typing.Union
                    and type(None) in args and str in args):
                found.append((name, f.name))
    return sorted(found)


def _deal_with_string(cls_name, field, value):
    """A deal whose only unusual input is `cls_name.field = value`."""
    borrower_kw = dict(name="Test Borrower", borrower_type="nonprofit",
                       sector="healthcare", state="IL", city="Chicago")
    loan_kw = dict(deal_type="loan", amount=2_500_000, interest_rate=0.045,
                   term_years=10)
    impact_kw = {}
    nmtc_kw = dict(nmtc_allocation=10_000_000, credit_price=0.83,
                   leverage_loan_rate=0.045, qlici_a_rate=0.045,
                   qlici_b_rate=0.0, cde_fee_rate=0.02)
    deal_kw = dict(deal_name="Test Deal", recommendation="approve_conditions",
                   prepared_by="Jay Patel", prepared_date="2026-05-06",
                   fund_name="Test Fund", ic_date="2026-06-01",
                   deal_summary="A summary.",
                   conditions=["Receipt of final appraisal"], risks=[])
    target = {"BorrowerProfile": borrower_kw, "LoanTerms": loan_kw,
              "ImpactData": impact_kw, "NMTCTerms": nmtc_kw,
              "DealProfile": deal_kw}[cls_name]
    target[field] = value
    return DealProfile(
        borrower=BorrowerProfile(**borrower_kw),
        loan_terms=LoanTerms(**loan_kw),
        financial_data=FinancialData(dscr=1.35),
        impact_data=ImpactData(**impact_kw),
        nmtc_terms=NMTCTerms(**nmtc_kw),
        **deal_kw)


@pytest.mark.parametrize("cls_name,field", _optional_str_fields(),
                         ids=lambda v: v)
def test_g9_an_empty_optional_string_renders_as_absence(cls_name, field):
    """
    G9's string half, applied to every `Optional[str]` field rather than to
    `mission` alone.

    THE PROPERTY, and the reason it is stated this way: a field set to `""`
    must produce a memo byte-identical to the same field left `None`. That is
    what "the package treats an empty string as absence" means, and it is
    checked against rendered output rather than against `fields.is_supplied`,
    so a section that reaches its own conclusion about `""` — by a bare
    `is not None`, or by an `or`-fallback, or by anything else — is caught
    whichever mechanism it used. Nothing here asserts *how* a section decides.

    R18. The gate this replaces exercised `mission` and nothing else, and
    `mission` was one of the fields that was already right. `closing_date` and
    `maturity_date` were tested with a bare `is not None` in
    sections/transaction.py, so `closing_date=""` rendered

        | Anticipated Closing |  |

    — a labelled row of the Proposed Terms table with no value in it — while
    the README, `fields.is_supplied`'s docstring, the CHANGELOG and this gate's
    own `ZERO_EXEMPT_OPTIONAL` all stated that `""` is absence. Four documents
    were right and the code was wrong; the code moved.

    Red-proof (must fail): restore `if lt.closing_date is not None:` in
    creditmemo/sections/transaction.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: 1 failed, 339 passed — LoanTerms.closing_date, showing the empty
    row. Restoring both lines: 2 failed, 338 passed.
    """
    empty = CreditMemo(_deal_with_string(cls_name, field, "")).to_markdown()
    absent = CreditMemo(_deal_with_string(cls_name, field, None)).to_markdown()
    assert empty == absent, (
        f"{cls_name}.{field}: an empty string renders differently from an "
        f"absent one.\nOnly in the empty rendering: "
        f"{sorted(set(empty.split(chr(10))) - set(absent.split(chr(10))))}")


def test_g9_the_empty_string_gate_is_not_vacuous():
    """
    Guard the guard. The gate above compares two renderings, so it would pass
    on a package that rendered nothing at all, or on a field the memo never
    shows. Both are ruled out here: every field it covers must reach the memo
    when it holds a real value, and the covered set must be non-empty.
    """
    covered = _optional_str_fields()
    assert covered, "no Optional[str] fields found — the gate is vacuous"
    unreachable = []
    for cls_name, field in covered:
        token = "SENTINELVALUE"
        md = CreditMemo(_deal_with_string(cls_name, field, token)).to_markdown()
        if token not in md:
            unreachable.append(f"{cls_name}.{field}")
    assert not unreachable, (
        f"the empty-string gate covers fields the memo never renders, so it "
        f"cannot see them change: {unreachable}")


# ── G10 — revenue_trend, the memo's one automated analytical claim ────────────
#
# R7/F2. `schema.py` gated the property on `if self.revenue_y1 and
# self.revenue_y3`. Revenue falling from $5MM to zero is the most alarming
# thing the field can express, and it was the one case the memo would not
# report. Confirmed by reading the property before relying on `is not None`:
# both branches are bare comparisons of the two values, there is no division,
# so `is not None` is a complete fix and needs no zero-guard of its own.

REVENUE_TREND_CASES = [
    # (revenue_y1, revenue_y3, direction)
    (5_000_000, 0,         "decreasing"),   # the collapse the memo would not report
    (0,         5_000_000, "increasing"),   # and the recovery from nothing
    (0,         0,         "stable"),
    (0.0,       0.0,       "stable"),
    (2_800_000, 3_200_000, "increasing"),
    (3_200_000, 2_800_000, "decreasing"),
    (3_000_000, 3_000_000, "stable"),
    (0,         1,         "increasing"),
    (1,         0,         "decreasing"),
]

REVENUE_TREND_ABSENT = [(None, None), (5_000_000, None), (None, 5_000_000)]


@pytest.mark.parametrize("y1,y3,direction", REVENUE_TREND_CASES)
def test_g10_revenue_trend_reports_a_direction_for_every_supplied_pair(y1, y3, direction):
    """
    G10. Both values supplied — zeros included — always yields a direction, and
    the memo prints it.

    Red-proof (must fail): restore `if self.revenue_y1 and self.revenue_y3:`
    in creditmemo/data/schema.py.
    Observed: 13 failed — 6 here (every case with a zero endpoint), the same 6
    in the section-line gate below, and the branch-coverage gate.
    """
    f = FinancialData(revenue_y1=y1, revenue_y3=y3)
    assert f.revenue_trend == direction


@pytest.mark.parametrize("y1,y3,direction", REVENUE_TREND_CASES)
def test_g10_the_memo_states_the_trend_it_computed(y1, y3, direction):
    """The property is not the memo. This gate reads the rendered line."""
    md = CreditMemo(_deal(financials=FinancialData(
        revenue_y1=y1, revenue_y3=y3))).to_markdown()
    assert f"**Revenue Trend:** {direction.title()} — " in md, (
        f"revenue_y1={y1!r} revenue_y3={y3!r}: the memo states no trend")
    assert f"revenue has been {direction} over the historical period." in md


@pytest.mark.parametrize("y1,y3", REVENUE_TREND_ABSENT)
def test_g10_a_missing_endpoint_states_no_trend(y1, y3):
    """`None` is absence, and absence is still the one case with no direction."""
    f = FinancialData(revenue_y1=y1, revenue_y3=y3)
    assert f.revenue_trend is None
    assert "**Revenue Trend:**" not in CreditMemo(
        _deal(financials=f)).to_markdown()


def test_g10_all_three_branches_execute():
    """
    The `decreasing` and `stable` branches had no suite coverage at all: the
    memo's only automated analytical claim had both of its adverse branches
    ungated. Asserted as a set so a branch that stops being reachable reds
    here rather than going quietly uncovered.
    """
    seen = {FinancialData(revenue_y1=y1, revenue_y3=y3).revenue_trend
            for y1, y3, _ in REVENUE_TREND_CASES}
    assert seen == {"increasing", "decreasing", "stable"}


def test_g10_the_trend_property_does_not_divide():
    """
    R7 asked for this to be confirmed rather than assumed: `is not None` is a
    complete fix only if no branch divides by an endpoint. Read off the source,
    so it stays true if the property is ever rewritten.
    """
    import ast
    import inspect

    source = textwrap.dedent(inspect.getsource(
        FinancialData.revenue_trend.fget))
    divisions = [n for n in ast.walk(ast.parse(source))
                 if isinstance(n, ast.BinOp)
                 and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod))]
    assert not divisions, (
        "revenue_trend now divides; `is not None` alone no longer guards it")



# ── G11 — the input-fidelity gate ────────────────────────────────────────────
#
# R8's structural ruling. tests/test_docx.py's G1/G2/G3 normalise the Markdown
# with `_MD_NUMBER = r"^\d+\.\s+(.*)$"` — the renderer's own `_ORDERED_ITEM` —
# and with a `_strip_emphasis` that replicates the renderer's `.replace("*","")`.
# So the gate removed, on the Markdown side, exactly what the renderer destroyed
# on the Word side, and both G1 variants stayed green while the string
# "2019. The borrower refinanced its senior debt at 4.2%." reached the
# Investment Committee as "1. The borrower refinanced its senior debt at 4.2%."
#
#     RULE: a gate that re-implements the transformation it is checking shares
#     its blind spot.
#
# Rule (i) required ground truth derived independently of the *declaration*.
# This extends it to the *transformation*. For a rendering-fidelity gate the
# only safe ground truth is the string the caller supplied, so everything below
# compares against values read straight off the DealProfile. There is no regex
# in this section, and nothing here imports from creditmemo.renderers or
# creditmemo.tables.
#
# The multiset gates in tests/test_docx.py stay: they catch duplication, which
# this does not. They are no longer the fidelity gate.

#: The shape every sentinel takes. One line, carrying each construct the
#: renderers were destroying:
#:
#:   "2019."   a number the underwriter wrote at the start of a line — the
#:             renderer matched it as an ordered-list item, emitted only the
#:             text, and let Word substitute its own "1."
#:   "5 * 3"   a lone asterisk, which is multiplication and not emphasis. It
#:             was deleted from paragraphs and kept in table cells, so the same
#:             character survived in one half of the document and not the other.
#:   "#"       a hash that is not a heading marker, because it is not leading.
#:
#: It carries no "|", no "\" and no newline: a Markdown table cell escapes the
#: first two and folds the third, by design and by GFM's rules, so those cannot
#: appear unchanged in the Markdown. They have their own positional gates in
#: tests/test_docx.py (test_pipe_in_underwriter_text_survives_to_the_docx).
#:
#: It also does not *begin* with "#", "- " or "* ". A line that begins with a
#: real Markdown block marker is restyled into the Word equivalent of that
#: marker — a heading, a bullet — which is the deferral CHANGELOG.md discloses.
#: That class replaces a marker with its equivalent; "2019." was replaced with a
#: different number, which is why it is here.
#:
#: "1. " is no longer in that list. R17 stopped ordered lines being restyled at
#: all, so a leading "1. " is now content like any other text and G13 gates it
#: directly.
SENTINEL_SHAPE = "2019. {token} margin improved 5 * 3 bps # not a heading"

#: Every free-text string a caller can put on a DealProfile, keyed by
#: "Dataclass.field". This is the reviewed surface: a new free-text field
#: cannot be added without a line here, because
#: test_g11_covers_every_free_text_field_on_every_dataclass reds until there is.
#:
#: The five validated enums (borrower_type, sector, deal_type, recommendation,
#: severity) are not free text — they are normalised to a canonical spelling on
#: construction and rendered through a label map, which G4 gates.
G11_FIELDS = [
    ("BorrowerProfile", "name"),
    ("BorrowerProfile", "state"),
    ("BorrowerProfile", "city"),
    ("BorrowerProfile", "ceo_name"),
    ("BorrowerProfile", "description"),
    ("BorrowerProfile", "mission"),
    ("BorrowerProfile", "website"),
    ("LoanTerms", "collateral"),
    ("LoanTerms", "guarantor"),
    ("LoanTerms", "use_of_proceeds"),
    ("LoanTerms", "closing_date"),
    ("LoanTerms", "maturity_date"),
    ("NMTCTerms", "cde_name"),
    ("NMTCTerms", "investor_name"),
    ("ImpactData", "census_tract"),
    ("ImpactData", "impact_narrative"),
    ("DealProfile", "deal_name"),
    ("DealProfile", "prepared_by"),
    ("DealProfile", "prepared_date"),
    ("DealProfile", "fund_name"),
    ("DealProfile", "ic_date"),
    ("DealProfile", "deal_summary"),
    ("DealProfile", "conditions"),
    ("RiskFactor", "category"),
    ("RiskFactor", "description"),
    ("RiskFactor", "mitigant"),
]

#: The enum fields, named so the coverage check can subtract them and so any
#: new validated field has to be classified deliberately.
G11_VALIDATED_ENUMS = {
    ("BorrowerProfile", "borrower_type"),
    ("BorrowerProfile", "sector"),
    ("LoanTerms", "deal_type"),
    ("DealProfile", "recommendation"),
    ("RiskFactor", "severity"),
}


def _sentinels():
    """{"Class.field": the exact string the caller supplied}."""
    return {f"{cls}.{field}": SENTINEL_SHAPE.format(token=f"TOKEN{i:02d}")
            for i, (cls, field) in enumerate(G11_FIELDS)}


def _sentinel_deal():
    """
    A DealProfile whose every free-text string is a distinct sentinel.

    Nothing about this deal is plausible; that is not what it is for. Every
    other input is left at whatever keeps the memo rendering every section.
    """
    v = _sentinels()
    borrower = BorrowerProfile(
        name=v["BorrowerProfile.name"],
        borrower_type="nonprofit", sector="healthcare",
        state=v["BorrowerProfile.state"], city=v["BorrowerProfile.city"],
        year_founded=2005, ceo_name=v["BorrowerProfile.ceo_name"],
        total_assets=8_000_000, annual_revenue=3_200_000,
        description=v["BorrowerProfile.description"],
        mission=v["BorrowerProfile.mission"],
        website=v["BorrowerProfile.website"],
        is_cdfi_certified=True, is_mdi=False)
    loan_terms = LoanTerms(
        deal_type="nmtc", amount=2_500_000, interest_rate=0.045, term_years=10,
        amortization_years=20, io_periods=12,
        collateral=v["LoanTerms.collateral"],
        guarantor=v["LoanTerms.guarantor"],
        use_of_proceeds=v["LoanTerms.use_of_proceeds"],
        closing_date=v["LoanTerms.closing_date"],
        maturity_date=v["LoanTerms.maturity_date"],
        min_dscr_covenant=1.20, max_ltv=0.75, origination_fee_pct=0.01)
    nmtc_terms = NMTCTerms(
        nmtc_allocation=10_000_000, credit_price=0.83, leverage_loan_rate=0.045,
        qlici_a_rate=0.045, qlici_b_rate=0.0, cde_fee_rate=0.02,
        cde_name=v["NMTCTerms.cde_name"],
        investor_name=v["NMTCTerms.investor_name"])
    impact = ImpactData(
        jobs_created=18, jobs_retained=32, patients_served=8500,
        is_low_income_area=True, is_women_borrower=False,
        census_tract=v["ImpactData.census_tract"],
        impact_narrative=v["ImpactData.impact_narrative"])
    risks = [RiskFactor(category=v["RiskFactor.category"],
                        description=v["RiskFactor.description"],
                        severity="Medium",
                        mitigant=v["RiskFactor.mitigant"])]
    return DealProfile(
        deal_name=v["DealProfile.deal_name"], borrower=borrower,
        loan_terms=loan_terms, financial_data=FinancialData(
            revenue_y1=2_800_000, revenue_y3=3_200_000, cash=450_000,
            dscr=1.35, projected_dscr_y1=1.38),
        impact_data=impact, nmtc_terms=nmtc_terms,
        recommendation="approve_conditions",
        prepared_by=v["DealProfile.prepared_by"],
        prepared_date=v["DealProfile.prepared_date"],
        fund_name=v["DealProfile.fund_name"],
        ic_date=v["DealProfile.ic_date"],
        deal_summary=v["DealProfile.deal_summary"],
        risks=risks,
        conditions=[v["DealProfile.conditions"], "A second condition"])


def _docx_texts(path):
    """
    Every string a reader can see in the Word document.

    Paragraph text and cell text, verbatim. No stripping, no unescaping, no
    re-parsing: whatever python-docx reports is what Word shows.
    """
    import docx as _docx
    doc = _docx.Document(path)
    return ([p.text for p in doc.paragraphs]
            + [c.text for t in doc.tables for r in t.rows for c in r.cells])


@pytest.mark.parametrize("where", sorted(_sentinels()))
def test_g11_every_caller_supplied_string_survives_into_the_markdown(where):
    """
    G11, Markdown half.

    Red-proof (must fail): none needed on this half at 0.2.1 — the Markdown
    renderer interpolates these values and does not transform them. It is
    stated so that a future transformation on the Markdown side cannot be
    introduced silently, and so the .docx half has a Markdown baseline to be
    compared against rather than being the only claim.
    """
    supplied = _sentinels()[where]
    md = CreditMemo(_sentinel_deal()).to_markdown()
    assert supplied in md, f"{where}: the caller's string is not in the Markdown"


@pytest.mark.parametrize("where", sorted(_sentinels()))
def test_g11_every_caller_supplied_string_survives_into_the_docx(where, tmp_path):
    r"""
    G11, Word half — the load-bearing one.

    The assertion is a count of the string the caller handed the DealProfile,
    in the paragraphs and cells of the saved document, against the count of that
    same string in the Markdown. Nothing is normalised on either side, and the
    expected multiplicity is not written down: it is read off the Markdown,
    whose fidelity for exactly these values the half above establishes. A field
    the memo shows twice must survive both times, so a value that arrives intact
    in a table cell cannot cover for the same value being mangled in a
    paragraph — which is precisely the shape of F4.

    Red-proof (must fail), both of which pass tests/test_docx.py's G1:
      * restore the unrestricted `_ORDERED_ITEM` branch in
        creditmemo/renderers/docx.py — the one that matched any `\d+\.` line
        and emitted only group(2).
        Observed: 7 failed here (every sentinel the memo renders as its own
        body line); `pytest tests/test_docx.py -k g1_` stayed green, 4 passed.
      * restore the unconditional `.replace("*", "")` in
        creditmemo/text.py's strip_emphasis.
        Observed: 26 failed here — every sentinel, both halves of the document;
        `pytest tests/test_docx.py -k g1_` stayed green, 4 passed.
    """
    pytest.importorskip("docx")
    deal = _sentinel_deal()
    supplied = _sentinels()[where]
    path = str(tmp_path / "fidelity.docx")
    CreditMemo(deal).save_docx(path)

    in_markdown = CreditMemo(deal).to_markdown().count(supplied)
    assert in_markdown >= 1, f"{where}: not in the Markdown — gate is vacuous"
    in_docx = sum(t.count(supplied) for t in _docx_texts(path))
    assert in_docx == in_markdown, (
        f"{where}: the caller supplied {supplied!r}; the Markdown shows it "
        f"{in_markdown} time(s) and the Word document {in_docx} time(s)")


def test_g11_covers_every_free_text_field_on_every_dataclass():
    """
    Guard the guard. Every `str`/`Optional[str]` field on every dataclass in the
    schema — and every list-of-string field — is either given a sentinel or
    named as a validated enum. A field added without a decision reds here.

    R19. The list half of that claim used to be spelled `or f.name ==
    "conditions"`: the docstring said "every list-of-string field" and the code
    named one field. Adding `covenants: list = field(default_factory=list)` to
    DealProfile left the suite green, and the field reached neither rendering.
    Lists are now classified by what they hold, so the claim and the check are
    the same statement:

      * a list whose element type is `str` is caller text and needs a sentinel;
      * a list of anything else is covered through that thing's own fields
        (`risks` is `List[RiskFactor]`, and RiskFactor's three strings are in
        G11_FIELDS);
      * a bare `list`, with no element type, is undecided and reds here until
        someone decides.

    Red-proof (must fail): add `covenants: list = field(default_factory=list)`
    to DealProfile in creditmemo/data/schema.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: 1 failed, 339 passed — "free-text fields with no G11 decision:
    [('DealProfile', 'covenants')]".
    """
    import dataclasses
    import typing

    from creditmemo.data import schema as schema_module

    text_fields = set()
    for name in dir(schema_module):
        obj = getattr(schema_module, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        hints = typing.get_type_hints(obj)
        for f in dataclasses.fields(obj):
            t = hints[f.name]
            args = typing.get_args(t)
            is_text = t is str or (typing.get_origin(t) is typing.Union
                                   and str in args)
            # A list of strings, or a list that has not said what it holds.
            is_text_list = ((t is list or typing.get_origin(t) is list)
                            and (not args or str in args))
            if is_text or is_text_list:
                text_fields.add((name, f.name))

    assert text_fields, "no text fields found — this gate would pass vacuously"
    declared = set(G11_FIELDS) | G11_VALIDATED_ENUMS
    missing = text_fields - declared
    assert not missing, f"free-text fields with no G11 decision: {sorted(missing)}"
    stale = declared - text_fields
    assert not stale, f"named in G11 but not a text field any more: {sorted(stale)}"


def test_g11_is_not_vacuous():
    """
    Guard the guard: the sentinels really are distinct, really do carry every
    shape the gate exists for, and really do all appear in a rendered memo.
    """
    values = _sentinels()
    assert len(set(values.values())) == len(G11_FIELDS) == len(values)
    for v in values.values():
        assert v.startswith("2019. "), "no leading number — the F3 shape is gone"
        assert " * " in v, "no lone asterisk — the F4 shape is gone"
        assert "#" in v, "no non-leading hash"
        assert "|" not in v and "\\" not in v and "\n" not in v
    md = CreditMemo(_sentinel_deal()).to_markdown()
    assert all(v in md for v in values.values())


# ── G12 — the two LTV fields never disagree about one supplied number ────────
#
# R14. `LoanTerms.max_ltv` is a fraction: transaction.py renders `max_ltv*100`,
# so `0.75` prints `Maximum LTV of 75%`. That is the package's dominant
# convention — `interest_rate`, `cde_fee_rate` and `origination_fee_pct` are
# all fractions. `FinancialData.ltv` is the sole exception: financial.py
# renders it with no scaling, so it means percentage *points*. Neither field
# said so anywhere — not on the declaration, not in README.md.
#
# Measured at 6ebcc6c with `ltv=0.75, max_ltv=0.75` on one deal:
#
#     - Maximum LTV of 75%              <- Transaction Structure
#     | Loan to Value | 0.8% | <= 80% | <- Financial Analysis
#
# The same supplied number, rendered as two different percentages in one memo,
# in both the Markdown and the .docx. A 75% LTV reaches the Investment
# Committee as 0.8% against a `<= 80%` benchmark.
#
# 0.2.1 does not unify the scales — that is a breaking change and 0.3.0 work.
# It makes the ambiguous band raise instead of rendering falsely.

#: The band `FinancialData.ltv` refuses, and why the edges sit here.
#:
#: `max_ltv` is a covenant cap expressed as a fraction, so the numbers a caller
#: might plausibly send to *both* fields are the fractions in [0.0, 1.0] — a
#: cap above 100% is not a credit control. Across that band:
#:
#:   0.0        both conventions agree (0% either way), and R6's supplied-zero
#:              ruling requires it to render, so it is allowed.
#:   (0.0, 1.0] can only be the fraction convention. Read as percentage points
#:              it claims an LTV of one percent or less — under a cent of debt
#:              per dollar of collateral. Rejected.
#:   > 1.0      taken at face value as percentage points.
LTV_FRACTION_BAND_MAX = 1.0

#: Numbers a caller could send to both `ltv` and `max_ltv` on one deal.
#: Every one is a legitimate `max_ltv`.
LTV_SHARED_NUMBERS = [0.0, 0.5, 0.65, 0.75, 0.8, 0.9, 0.95, 1.0]


def _ltv_percentages(md):
    """
    The two LTV percentages the memo states, read back out of the rendered
    text rather than recomputed.

    Ground truth derived independently of the renderer — rule (i). A gate that
    asked `fields`/`financial.py` to format its own expectation would follow
    the defect wherever it went.
    """
    covenant = re.search(r"Maximum LTV of ([\d.]+)%", md)
    metric = re.search(r"\| Loan to Value \| ([\d.]+)% \|", md)
    assert covenant, "the covenant line vanished; this gate no longer measures it"
    assert metric, "the Loan to Value row vanished; this gate no longer measures it"
    return float(covenant.group(1)), float(metric.group(1))


@pytest.mark.parametrize("number", LTV_SHARED_NUMBERS)
def test_g12_one_number_never_becomes_two_percentages(number):
    """
    G12. For any number that is a legitimate `max_ltv`, a deal that supplies it
    to `ltv` as well either refuses to construct or renders one percentage,
    not two.

    Red-proof (must fail): delete the `ltv` check from
    `FinancialData.__post_init__` and re-run. `ltv=0.75` then constructs, and
    the memo states `Maximum LTV of 75%` beside `| Loan to Value | 0.8% |`.
    """
    try:
        deal = _deal(
            financials=FinancialData(ltv=number),
            loan_terms=LoanTerms(deal_type="loan", amount=2_500_000,
                                 max_ltv=number))
    except ValueError:
        # Refused, loudly. That is the 0.2.1 answer for the ambiguous band.
        assert number > 0.0, "a supplied zero must still render — see G9"
        assert number <= LTV_FRACTION_BAND_MAX
        return

    covenant_pct, metric_pct = _ltv_percentages(CreditMemo(deal).to_markdown())
    assert covenant_pct == pytest.approx(metric_pct), (
        f"ltv={number} and max_ltv={number} rendered as {metric_pct}% and "
        f"{covenant_pct}% in one memo")


def test_g12_the_refusal_names_the_unit_it_wanted():
    """
    A loud error is only better than a false number if the reader can act on
    it. The message must name the field, the unit expected, and the value
    rejected — the shape `_normalise_choice` already uses for `borrower_type`.

    Red-proof (must fail): replace the message with a bare
    `raise ValueError("bad ltv")`.
    """
    with pytest.raises(ValueError) as excinfo:
        FinancialData(ltv=0.75)
    message = str(excinfo.value)
    assert "ltv" in message
    assert "0.75" in message, "the rejected value is not quoted back"
    assert "percentage points" in message, "the expected unit is not named"
    assert "75.0" in message, "the message does not show the accepted spelling"


def test_g12_a_real_ltv_still_constructs():
    """
    The refusal must not cost the package a legitimate input. Every one of
    these is an LTV an underwriter writes down, in percentage points.

    Red-proof (must fail): widen the band to `ltv < 5` — the "no real loan is
    below a few percent" threshold — and `1.25` (a nearly repaid loan against
    appreciated collateral) stops constructing.
    """
    for real in (1.25, 2.0, 4.9, 25.0, 62.5, 75.0, 80.0, 97.5, 105.0):
        assert FinancialData(ltv=real).ltv == real


def test_g12_zero_is_the_one_number_both_conventions_agree_on():
    """
    Why `0.0` is exempt rather than rejected with the rest of the band: it is
    the single value the fraction and percentage-point readings render
    identically, so it carries no ambiguity to fail loudly about — and G9
    requires a supplied zero to reach the memo.
    """
    assert FinancialData(ltv=0.0).ltv == 0.0
    md = CreditMemo(_deal(
        financials=FinancialData(ltv=0.0),
        loan_terms=LoanTerms(deal_type="loan", amount=2_500_000,
                             max_ltv=0.0))).to_markdown()
    assert _ltv_percentages(md) == (0.0, 0.0)


def test_g12_holds_in_the_word_document_too(tmp_path):
    """
    R14's escalation over F3: the scale defect is wrong in *both* renderings,
    where F3 was .docx-only. The .docx is built from this Markdown, so a gate
    that only read the Markdown would be assuming the half that broke in 0.2.0.
    """
    docx = pytest.importorskip("docx")
    with pytest.raises(ValueError):
        FinancialData(ltv=0.75)

    path = tmp_path / "ltv.docx"
    CreditMemo(_deal(
        financials=FinancialData(ltv=75.0),
        loan_terms=LoanTerms(deal_type="loan", amount=2_500_000,
                             max_ltv=0.75))).save_docx(str(path))
    document = docx.Document(str(path))
    text = "\n".join(
        [p.text for p in document.paragraphs]
        + [c.text for t in document.tables for r in t.rows for c in r.cells])
    assert "75" in text
    assert "0.8%" not in text, "the fraction rendering survived into the .docx"


#: The values a caller reading a spreadsheet row might assign after building
#: the object, and what each must do. The band is the same one the constructor
#: refuses; the point of the list is that the *route* is different.
POST_CONSTRUCTION_LTV = [
    (0.75, "raises"),   # the R14 defect verbatim: rendered as 0.8%
    (0.8,  "raises"),   # and the CHANGELOG's own counter-example
    (1.0,  "raises"),   # the top of the band
    (0.0,  "renders"),  # the one value both conventions agree on
    (75.0, "renders"),  # the documented scale
    (100.0, "renders"),
    (None, "renders"),
]


@pytest.mark.parametrize("value,outcome", POST_CONSTRUCTION_LTV,
                         ids=lambda v: str(v))
def test_g12_a_post_construction_ltv_is_refused_at_the_render_boundary(
    value, outcome, tmp_path
):
    """
    G12 addendum, R20. The scale check is on the value that gets rendered, not
    only on the value that gets constructed.

    `FinancialData` is a plain dataclass, so `__post_init__` sees only what the
    constructor was handed. Measured at 2031b0a:

        f = FinancialData()
        f.ltv = 0.75            # nothing raises
        CreditMemo(deal).to_markdown()
        -> | Loan to Value | 0.8% | <= 80% |

    which is R14's defect, unaltered, reached by assembling the object field by
    field — the shape you get reading a spreadsheet row, and the shape a caller
    who hit the constructor's error message would most naturally fall back to.
    Freezing the dataclass would also close it, and is a breaking change that
    this round rules out of scope.

    Both renderings are exercised, because a check in only one of them would
    leave the .docx path — which is where every defect of this class in 0.2.0
    lived — unguarded.

    Red-proof (must fail): delete the `_reject_fractional_ltv(f.ltv)` call from
    creditmemo/sections/financial.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: 3 failed, 337 passed — the three values in the band — each
    reporting "DID NOT RAISE".
    """
    pytest.importorskip("docx")
    financials = FinancialData()
    financials.ltv = value
    memo = CreditMemo(_deal(financials=financials))

    if outcome == "raises":
        with pytest.raises(ValueError) as markdown_error:
            memo.to_markdown()
        assert "percentage points" in str(markdown_error.value)
        with pytest.raises(ValueError):
            memo.save_docx(str(tmp_path / "ltv.docx"))
        return

    md = memo.to_markdown()
    assert "| Loan to Value |" in md
    memo.save_docx(str(tmp_path / "ltv.docx"))


def test_g12_the_constructor_check_still_fires_first():
    """
    Guard the guard for the addendum above. The render-boundary call is an
    addition, not a replacement: a bad `ltv` passed to the constructor must
    still fail there, where the traceback points at the caller's own line
    rather than at a section generator.
    """
    with pytest.raises(ValueError) as error:
        FinancialData(ltv=0.75)
    assert "percentage points" in str(error.value)


def test_g12_max_ltv_renders_at_the_same_precision_as_the_ltv_it_caps():
    """
    R23. `max_ltv` rendered `.0f` while `FinancialData.ltv` renders `.1f`, so a
    `max_ltv=0.795` covenant printed as

        - Maximum LTV of 80%

    — a covenant reported looser than the borrower agreed to, at a value
    plausible enough that nobody would query it, in the section an IC reads to
    learn the terms. The two fields describe the same quantity and are read
    against each other; they now print at the same precision.

    The expected strings are written out rather than produced with the
    renderer's own format spec, for the reason ZERO_RENDERINGS is: a gate that
    formats its expectation the way the code does follows the code anywhere.

    Red-proof (must fail): restore `{lt.max_ltv*100:.0f}%` in
    creditmemo/sections/transaction.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc python -m pytest tests/ -q
    Observed: 2 failed, 338 passed — this gate, showing "Maximum LTV of 80%"
    for max_ltv=0.795, and G9's `max_ltv` zero row, which pins the same
    formatter at "Maximum LTV of 0.0%".
    """
    for value, expected in ((0.795, "Maximum LTV of 79.5%"),
                            (0.75, "Maximum LTV of 75.0%"),
                            (0.804, "Maximum LTV of 80.4%")):
        md = CreditMemo(_deal(loan_terms=LoanTerms(
            deal_type="loan", amount=2_500_000, max_ltv=value))).to_markdown()
        assert expected in md, (
            f"max_ltv={value}: expected {expected!r}; the covenant lines are "
            f"{[l for l in md.split(chr(10)) if 'Maximum LTV' in l]}")

    # And the rounding really was hiding something: at .0f these three
    # different covenants printed as two.
    assert len({f"{v*100:.0f}" for v in (0.795, 0.804)}) == 1


def test_g12_documents_the_unit_on_every_rate_and_ratio_field():
    """
    An undocumented unit is what produced R14, so the gate is on the
    documentation, not only the validation. Every rate and ratio field on the
    schema must carry a comment saying which scale it is in.

    Red-proof (must fail): delete the `#:` comment above `FinancialData.ltv`.
    """
    import ast
    import inspect

    from creditmemo.data import schema as schema_module

    source = inspect.getsource(schema_module)
    lines = source.splitlines()
    tree = ast.parse(source)

    #: Field name -> the dataclass it lives on. Every one is a rate, a ratio
    #: or a fee whose number is meaningless without a unit.
    unit_bearing = {
        "BorrowerProfile": (),
        "LoanTerms": ("interest_rate", "max_ltv", "origination_fee_pct",
                      "min_dscr_covenant"),
        "FinancialData": ("dscr", "current_ratio", "debt_to_equity", "ltv",
                          "projected_dscr_y1", "projected_dscr_y2",
                          "projected_dscr_y3"),
        "NMTCTerms": ("credit_price", "leverage_loan_rate", "qlici_a_rate",
                      "qlici_b_rate", "cde_fee_rate"),
    }

    undocumented = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name not in unit_bearing:
            continue
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            name = getattr(statement.target, "id", None)
            if name not in unit_bearing[node.name]:
                continue
            # The comment block immediately above the declaration.
            above = []
            index = statement.lineno - 2
            while index >= 0 and lines[index].strip().startswith("#"):
                above.append(lines[index])
                index -= 1
            if not any(word in "\n".join(above).lower() for word in
                       ("fraction", "percentage point", "multiple", "dollars")):
                undocumented.append(f"{node.name}.{name}")

    assert not undocumented, (
        f"rate/ratio fields with no unit documented: {sorted(undocumented)}")


def test_g12_the_unit_gate_covers_every_such_field():
    """
    Guard the guard: the hand-written list above must not drift away from the
    schema. Any field whose name marks it as a rate, ratio, fee or price has
    to appear in it.
    """
    import ast
    import inspect

    from creditmemo.data import schema as schema_module

    marks = ("_rate", "rate_", "ratio", "_pct", "dscr", "ltv", "price")
    #: `debt_to_equity` is a ratio whose name carries none of the marks above.
    #: Listed here so the guard can still check it has not vanished, without
    #: pretending the name test would have found it.
    unmarked = {"debt_to_equity"}
    declared = {
        "interest_rate", "max_ltv", "origination_fee_pct", "min_dscr_covenant",
        "dscr", "current_ratio", "debt_to_equity", "ltv",
        "projected_dscr_y1", "projected_dscr_y2", "projected_dscr_y3",
        "credit_price", "leverage_loan_rate", "qlici_a_rate", "qlici_b_rate",
        "cde_fee_rate",
    }
    found = set()
    tree = ast.parse(inspect.getsource(schema_module))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign):
                name = getattr(statement.target, "id", None)
                if name and any(m in name for m in marks):
                    found.add(name)
    all_fields = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            all_fields |= {getattr(s.target, "id", None) for s in node.body
                           if isinstance(s, ast.AnnAssign)}

    assert not (found - declared), (
        f"unit-bearing fields the gate does not name: {sorted(found - declared)}")
    assert not (declared - all_fields), (
        f"named by the gate but gone from the schema: {sorted(declared - all_fields)}")
    assert unmarked <= declared


# ── Packaging ────────────────────────────────────────────────────────────────

def _declared_runtime_dependencies():
    text = io.open(ROOT / "pyproject.toml", encoding="utf-8").read()
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
    assert block, "no [project].dependencies in pyproject.toml"
    return re.findall(r'"([^"]+)"', block.group(1))


def _package_source():
    return "\n".join(io.open(p, encoding="utf-8").read() for p in _package_sources())


def _imports(source, module):
    """True if `source` has a top-level-looking import of `module`."""
    return bool(re.search(rf"^\s*(?:import|from)\s+{re.escape(module)}\b",
                          source, re.M))


def test_every_declared_runtime_dependency_is_actually_imported():
    """
    0.1.0 and 0.2.0 declared `pandas>=1.4.0` as a hard runtime dependency. No
    module in the package imports pandas, or anything else outside the standard
    library — so every install pulled pandas and numpy, and inherited their
    platform and Python-version constraints, to build strings.

    With `dependencies = []` this loop runs zero times and passes vacuously,
    which is the correct outcome and not a working gate. What keeps it honest is
    test_the_declared_dependency_gate_is_not_vacuous below.
    """
    source = _package_source()
    for dep in _declared_runtime_dependencies():
        module = re.split(r"[<>=!~\[; ]", dep)[0].replace("-", "_")
        assert _imports(source, module), (
            f"{dep!r} is declared as a runtime dependency but never imported")


def test_the_declared_dependency_gate_is_not_vacuous():
    """
    Guard the guard, per F9.

    The gate above is latent: `dependencies = []` is deliberate, so its loop
    body never executes and it cannot fail for any reason. Every other guard in
    this suite has a would-pass-vacuously check; this is that check. It exercises
    the gate's actual predicate against a module the package does import and one
    it does not, so a broken predicate reds here rather than waiting for the day
    a dependency is added back.
    """
    source = _package_source()
    assert _imports(source, "re"), (
        "the predicate does not recognise an import the package really has")
    assert not _imports(source, "pandas"), (
        "the predicate claims an import the package does not have")
    assert not _imports(source, "reprlib"), (
        "the predicate matches on a prefix; `import re` is not `import reprlib`")
    assert _declared_runtime_dependencies() == [], (
        "credit-memo now declares a runtime dependency; the gate above is no "
        "longer vacuous and this docstring needs rewriting")


#: Derives the set of modules to block from what is actually installed, rather
#: than naming a few. Run inside the subprocess, so it sees that interpreter's
#: environment and not this one's.
_DERIVE_BLOCKED = """
import sys
try:
    from importlib.metadata import distributions
except ImportError:                       # pragma: no cover - Python < 3.8
    from importlib_metadata import distributions

BLOCKED = set()
for dist in distributions():
    top = dist.read_text("top_level.txt") or ""
    BLOCKED.update(name.strip() for name in top.splitlines())
    for path in (dist.files or []):
        parts = path.parts
        if len(parts) > 1:
            BLOCKED.add(parts[0])
        elif parts and parts[0].endswith(".py"):
            BLOCKED.add(parts[0][:-3])
BLOCKED = {name for name in BLOCKED
           if name.isidentifier() and not name.startswith("_")}
BLOCKED.discard("creditmemo")
"""


def test_the_package_renders_a_memo_with_no_third_party_import():
    """
    Derived from behaviour, not from the declaration: block every third-party
    import and render a full memo anyway.

    The blocked set is derived from the distributions installed in the
    subprocess's own environment, per F10. It used to be the literal
    ``("pandas", "numpy", "docx")``, so ``import pytest`` in a shipped module
    passed both dependency gates — the gate named three of the things it was
    looking for instead of describing the property.

    That also makes the red-proof reproducible in the project's declared
    environment, per F11. The old red-proof was "add ``import pandas`` to any
    module in creditmemo/", and pandas is not installed here: it gives a conftest
    ImportError and 0 tests run, not 1 failed. Any installed distribution now
    reddens it.

    Red-proof (must fail): add ``import docx`` at module level to any module in
    creditmemo/ — python-docx is installed whenever the declared ``[docx]``
    extra is, which CI enforces with CREDITMEMO_REQUIRE_DOCX=1.
    Observed: 1 failed, with ``ImportError: blocked for this test: docx``.
    """
    program = _DERIVE_BLOCKED + textwrap.dedent("""
        assert BLOCKED, "no installed distributions found — gate is vacuous"
        class Blocker:
            def find_module(self, name, path=None):
                return self if name.split(".")[0] in BLOCKED else None
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in BLOCKED:
                    raise ImportError("blocked for this test: " + name)
                return None
        sys.meta_path.insert(0, Blocker())
        from creditmemo import (CreditMemo, DealProfile, BorrowerProfile,
                                LoanTerms, FinancialData, ImpactData)
        deal = DealProfile(
            deal_name="D",
            borrower=BorrowerProfile(name="N", borrower_type="nonprofit",
                                     sector="healthcare", state="IL", city="Chicago"),
            loan_terms=LoanTerms(deal_type="loan", amount=1_000_000),
            financial_data=FinancialData(dscr=1.2), impact_data=ImpactData(),
            recommendation="approve", prepared_by="J", prepared_date="2026-01-01")
        assert "Investment Committee Memorandum" in CreditMemo(deal).to_markdown()
        print("blocked:" + ",".join(sorted(BLOCKED)))
        print("ok")
    """)
    result = subprocess.run([sys.executable, "-c", program],
                            capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout

    blocked = set()
    for line in result.stdout.splitlines():
        if line.startswith("blocked:"):
            blocked = set(line[len("blocked:"):].split(","))
    assert blocked, "the subprocess derived an empty blocked set — gate is vacuous"
    assert "creditmemo" not in blocked, "the package blocked itself"


def test_the_derived_blocked_set_names_the_dependency_it_must_block():
    """
    Guard the guard for F10/F11: the derivation has to actually name the
    third-party packages that are present, or the gate above blocks nothing and
    passes for the wrong reason. python-docx is the one this project declares,
    and the one that gate's red-proof uses.
    """
    pytest.importorskip("docx")
    program = _DERIVE_BLOCKED + textwrap.dedent("""
        assert "docx" in BLOCKED, sorted(BLOCKED)[:40]
        assert "creditmemo" not in BLOCKED
        print("ok")
    """)
    result = subprocess.run([sys.executable, "-c", program],
                            capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, result.stdout + result.stderr


# ── G14 — a dollar figure says which figure it is ────────────────────────────
#
# R24. Every money site formatted its own, in the `$MM` unit, at two decimals —
# one decimal in the borrower snapshot. Two decimals of `$MM` resolve to
# $10,000, so measured at 3acaf7b:
#
#     supplied         0 -> | Revenue | $0.00MM |   | Cash & Equivalents | $0.00MM |
#     supplied     4,999 -> | Revenue | $0.00MM |   | Cash & Equivalents | $0.00MM |
#     total_assets=49,000 -> - **Total Assets:** $0.0MM
#
# and the memo contradicted itself two lines apart, because the trend is
# computed on the raw values and was right:
#
#     | Revenue | $0.00MM | N/A | $0.00MM |
#     **Revenue Trend:** Increasing — revenue has been increasing ...
#
# `microenterprise` is a declared SECTORS value and $5k-$50k is that product's
# normal size, so this is not a corner: it is the package's own stated audience
# reading a destroyed figure as a stated zero, in the Investment Committee memo,
# with no cue that anything was lost.

#: Magnitudes swept by G14, spanning $1 to $100,000,000. Each is also swept
#: negative. The small end is where the `$MM` divide destroyed the figure; the
#: values around $1,000,000 straddle the unit crossover; the cents values are
#: below the dollar form's own floor.
MONEY_SWEEP = [
    0.004, 0.005, 0.01, 0.4, 1, 1.4, 99, 100, 999, 1_000, 4_999, 4_999.60,
    5_000, 9_999, 10_000, 49_000, 50_000, 99_999, 100_000, 999_999,
    999_999.99, 1_000_000, 1_000_001, 1_234_567, 2_500_000, 4_999_999,
    5_000_000, 10_000_000, 99_999_999, 100_000_000,
]

#: How much a rendered figure is allowed to differ from the value behind it,
#: per format. These are the formats' own claims, read off the characters:
#: two decimals of `$MM` claim $10,000 of resolution, so half of that either
#: way; a dollars-and-cents string claims the cent.
_MM_TOLERANCE = 5_000.0
_CENT_TOLERANCE = 0.005

#: A rendered dollars-and-cents figure, e.g. "-$1,234.56", "$4,999", "$1.00MM".
#: Written from the rendered characters. Nothing in this section imports
#: creditmemo.money or calls it to build an expectation: R8's rule is that a
#: gate which re-implements the transformation it checks shares its blind spot,
#: and the gate this replaces asserted "$0.00MM" — the violation's own output.
_RENDERED_MONEY = re.compile(
    r"^(?P<sign>-?)\$(?P<digits>\d{1,3}(?:,\d{3})*|\d+)"
    r"(?:\.(?P<cents>\d{2}))?(?P<mm>MM)?$")


def _recover(rendered):
    """
    Read a value back out of a rendered money string.

    Returns ``(low, high)``: the closed interval the rendering asserts the
    value lies in, given the precision its own characters claim. A bound form
    (``<$0.01``) asserts an open-ended interval on one side of zero.
    """
    if rendered == "<$0.01":
        return (0.0, 0.01)
    if rendered == ">-$0.01":
        return (-0.01, 0.0)
    match = _RENDERED_MONEY.match(rendered)
    assert match, f"not a money rendering this gate can read: {rendered!r}"
    text = match.group("digits").replace(",", "")
    value = float(text)
    if match.group("cents") is not None:
        value += float(match.group("cents")) / 100.0
    if match.group("mm"):
        value *= 1_000_000.0
        tolerance = _MM_TOLERANCE
    else:
        tolerance = _CENT_TOLERANCE
    if match.group("sign"):
        value = -value
    return (value - tolerance, value + tolerance)


@pytest.mark.parametrize("magnitude", MONEY_SWEEP, ids=lambda v: repr(v))
@pytest.mark.parametrize("sign", [1, -1], ids=["positive", "negative"])
def test_g14_no_non_zero_figure_renders_as_a_stated_zero(magnitude, sign):
    """
    G14. Across $1 to $100,000,000, positive and negative, no non-zero dollar
    figure renders as the string a *stated* zero renders as, and every value is
    recoverable from its rendering to the precision that rendering claims.

    Both halves are needed and neither implies the other. A formatter that
    printed every figure as "$1" would pass the first and fail the second; one
    that printed "$0.00MM" for everything below $5,000 — which is what shipped
    — passes the second only if you accept a $5,000 tolerance at $4,999, which
    is the whole defect stated as an excuse.

    Red-proof (must fail): in creditmemo/money.py, replace the body of `money`
    with the unconditional divide it replaced —

        def money(value) -> str:
            if value is None:
                return NOT_SUPPLIED
            return f"${value/1e6:,.2f}MM"

    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc $HOME/probeenv/bin/python -m pytest tests/ -q
    Observed: 66 failed, 361 passed. 30 of the 66 are this gate's own
    parameters — the 30 of its 60 that fall below the crossover, in both signs;
    the figures already large enough for the $MM form still render correctly,
    which is the point.
    """
    from creditmemo import money as money_module

    value = magnitude * sign
    rendered = money_module.money(value)

    assert rendered != money_module.ZERO, (
        f"{value!r} renders as {rendered!r}, which is what a stated zero "
        f"renders as. An Investment Committee cannot tell the two apart.")

    low, high = _recover(rendered)
    assert low <= value <= high, (
        f"{value!r} renders as {rendered!r}, which claims a value in "
        f"[{low!r}, {high!r}]")


def test_g14_a_stated_zero_still_renders():
    """
    R6's ruling stands: a supplied zero reaches the memo. G14 above is a
    one-sided property — a formatter that raised on every value would pass it —
    so the other side is stated here.
    """
    from creditmemo import money as money_module

    assert money_module.money(0) == money_module.ZERO
    assert money_module.money(0.0) == money_module.ZERO
    assert money_module.money(-0.0) == money_module.ZERO
    assert money_module.dollars(0) == money_module.ZERO
    assert money_module.money_with_mm(0) == money_module.ZERO
    assert money_module.money(None) == "N/A"


def test_g14_the_sweep_covers_the_range_it_claims():
    """
    Guard the guard. The gate above is parametrised, so a truncated list would
    shrink it silently and it would still be green.
    """
    assert min(MONEY_SWEEP) < 1, "the sweep does not reach below a dollar"
    assert 1 in MONEY_SWEEP, "the sweep does not include $1"
    assert max(MONEY_SWEEP) >= 100_000_000, "the sweep stops short of $100MM"
    below = [v for v in MONEY_SWEEP if v < 5_000]
    assert len(below) >= 6, (
        "the sweep barely covers the band the $MM form destroyed, which is "
        "the band this gate exists for")
    assert any(v >= 1_000_000 for v in MONEY_SWEEP)


#: Every dollar-denominated field on the schema, as (holder, field). "Holder"
#: is the keyword `_deal_with_dollars` builds. This is the reviewed surface: a
#: new dollar field cannot be added without a line here or in the exempt set
#: below, because `test_g14_covers_every_dollar_field` reds until there is one.
DOLLAR_FIELDS = [
    ("borrower",       "total_assets"),
    ("borrower",       "annual_revenue"),
    ("loan_terms",     "amount"),
    ("financial_data", "revenue_y1"),
    ("financial_data", "revenue_y2"),
    ("financial_data", "revenue_y3"),
    ("financial_data", "net_income_y1"),
    ("financial_data", "net_income_y2"),
    ("financial_data", "net_income_y3"),
    ("financial_data", "ebitda_y1"),
    ("financial_data", "ebitda_y2"),
    ("financial_data", "ebitda_y3"),
    ("financial_data", "total_assets"),
    ("financial_data", "total_liabilities"),
    ("financial_data", "net_assets_equity"),
    ("financial_data", "cash"),
    ("financial_data", "projected_revenue_y1"),
    ("nmtc_terms",     "nmtc_allocation"),
]

#: Numeric fields that are not dollar magnitudes, with what they are instead.
#: Named so that a new one has to be classified rather than quietly skipped.
NON_DOLLAR_NUMERIC = {
    "year_founded": "a calendar year",
    "interest_rate": "a fraction", "term_years": "whole years",
    "amortization_years": "whole years", "io_periods": "whole months",
    "min_dscr_covenant": "a multiple", "max_ltv": "a fraction",
    "origination_fee_pct": "a fraction",
    "dscr": "a multiple", "current_ratio": "a multiple",
    "debt_to_equity": "a multiple", "ltv": "percentage points",
    "projected_dscr_y1": "a multiple", "projected_dscr_y2": "a multiple",
    "projected_dscr_y3": "a multiple",
    "credit_price": "dollars per $1 of credit — a price, not a magnitude; it "
                    "does not go through creditmemo.money and still carries "
                    "R24's property at two decimals. Reported, 0.3.0.",
    "leverage_loan_rate": "a fraction", "qlici_a_rate": "a fraction",
    "qlici_b_rate": "a fraction", "cde_fee_rate": "a fraction",
    "compliance_years": "whole years",
    "jobs_created": "a count", "jobs_retained": "a count",
    "affordable_units": "a count", "sq_ft_community_space": "square feet",
    "patients_served": "a count", "students_served": "a count",
    "businesses_supported": "a count",
}

#: Magnitudes every dollar field is rendered at. All four collapsed to one
#: string at 3acaf7b: $1, $4,999 and $49,000 to "$0.00MM" or "$0.0MM", and
#: $999,999 to "$1.00MM" — the last indistinguishable from a stated $1,000,000.
DOLLAR_FIELD_MAGNITUDES = [1, 4_999, 49_000, 999_999]


def _deal_with_dollars(holder, field, value):
    """A deal whose only unusual input is `holder.field = value`."""
    if holder == "borrower":
        kw = dict(name="Test Borrower", borrower_type="nonprofit",
                  sector="microenterprise", state="IL", city="Chicago")
        kw[field] = value
        return _deal(borrower=BorrowerProfile(**kw))
    if holder == "loan_terms":
        kw = dict(deal_type="loan", amount=2_500_000)
        kw[field] = value
        return _deal(loan_terms=LoanTerms(**kw))
    if holder == "financial_data":
        return _deal(financials=FinancialData(**{field: value}))
    if holder == "nmtc_terms":
        kw = dict(nmtc_allocation=10_000_000, credit_price=0.83,
                  leverage_loan_rate=0.045, qlici_a_rate=0.045,
                  qlici_b_rate=0.0, cde_fee_rate=0.02)
        kw[field] = value
        return _deal(nmtc_terms=NMTCTerms(**kw))
    raise AssertionError(holder)


@pytest.mark.parametrize("holder,field", DOLLAR_FIELDS,
                         ids=[f"{h}.{f}" for h, f in DOLLAR_FIELDS])
def test_g14_every_dollar_field_renders_its_own_magnitude(holder, field):
    """
    G14, the half that is about the memo rather than the formatter.

    The formatter sweep above cannot see a section that does not call the
    formatter, and "one shared formatter" is a claim about the sections, not
    about creditmemo/money.py. So this asks the rendered memo directly: four
    different figures in the band the `$MM` divide destroyed must produce four
    different memos, and each figure's digits must appear in its own.

    Nothing here calls creditmemo.money. The renderings are compared with each
    other; the ground truth is the digits the caller supplied.

    Red-proof (must fail): in creditmemo/money.py, replace the body of `money`
    with the unconditional divide (see the sweep gate above).
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc $HOME/probeenv/bin/python -m pytest tests/ -q
    Observed: 66 failed, 361 passed; 17 of the 18 parameters here.
    `loan_terms.amount` is the one that survives, because the Amount row prints
    the exact dollars beside the $MM form and always did — which is why the
    formatter sweep alone is not enough, and why this gate reads the memo.
    """
    rendered = {}
    for magnitude in DOLLAR_FIELD_MAGNITUDES:
        md = CreditMemo(_deal_with_dollars(holder, field, magnitude)).to_markdown()
        assert f"{magnitude:,}" in md, (
            f"{holder}.{field}={magnitude!r}: the figure's own digits "
            f"({magnitude:,}) appear nowhere in the memo")
        for seen, other in rendered.items():
            assert md != other, (
                f"{holder}.{field}: ${magnitude:,} and ${seen:,} render the "
                f"same memo — the reader cannot tell which figure was supplied")
        rendered[magnitude] = md


def test_g14_covers_every_dollar_field():
    """
    Guard the guard, in G9's shape. Every numeric field on every schema
    dataclass is either swept by G14 as a dollar magnitude or named in
    NON_DOLLAR_NUMERIC with what it is instead. A dollar field added to the
    schema without a decision here reds.
    """
    import dataclasses
    import typing

    from creditmemo.data import schema as schema_module

    numeric = set()
    for name in dir(schema_module):
        obj = getattr(schema_module, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        hints = typing.get_type_hints(obj)
        for f in dataclasses.fields(obj):
            t = hints[f.name]
            args = set(typing.get_args(t)) or {t}
            if args & {int, float}:
                numeric.add(f.name)

    assert numeric, "no numeric fields found — this gate would pass vacuously"
    covered = {field for _, field in DOLLAR_FIELDS}
    missing = numeric - covered - set(NON_DOLLAR_NUMERIC)
    assert not missing, f"numeric fields with no dollar/not-dollar decision: {sorted(missing)}"
    stale = (covered | set(NON_DOLLAR_NUMERIC)) - numeric
    assert not stale, f"named here but no longer a numeric schema field: {sorted(stale)}"


def test_g14_the_revenue_table_and_the_revenue_trend_agree():
    """
    R24's corollary, measured rather than assumed.

    `FinancialData.revenue_trend` is computed on the raw values and was always
    right; the table's *rendering* was the lossy part, so a memo could say

        | Revenue | $0.00MM | $0.00MM | $0.00MM |
        **Revenue Trend:** Increasing — revenue has been increasing ...

    — three identical figures under a sentence asserting they differ. The
    prediction was that fixing the formatter resolves this with no change to
    the trend. It does, and this is what holds it: whenever the memo claims a
    direction, the rendered endpoints must show one.

    Red-proof (must fail): the unconditional `$MM` divide in
    creditmemo/money.py — with it, the y1=$1,000 / y3=$4,999 case below renders
    two identical cells under "increasing".
    Observed: 66 failed, 361 passed; this gate is 1 of the 66.
    """
    cases = [(1_000, 4_999, "increasing"), (4_999, 1_000, "decreasing"),
             (1_000, 1_000, "stable"), (0, 4_999, "increasing"),
             (4_999, 0, "decreasing")]
    for y1, y3, direction in cases:
        md = CreditMemo(_deal(financials=FinancialData(
            revenue_y1=y1, revenue_y3=y3))).to_markdown()
        assert f"revenue has been {direction}" in md, (
            f"revenue_y1={y1}, revenue_y3={y3}: the memo does not state "
            f"{direction!r}")
        row = [line for line in md.split("\n") if line.startswith("| Revenue |")]
        assert len(row) == 1, row
        first, last = row[0].split("|")[2].strip(), row[0].split("|")[4].strip()
        if direction == "stable":
            assert first == last, f"'stable' over cells that differ: {row[0]!r}"
        else:
            assert first != last, (
                f"the memo says revenue has been {direction} and renders the "
                f"two endpoints identically: {row[0]!r}")


# ── G14b — an element of a list field is a caller-supplied string ────────────

def test_g14b_an_empty_list_element_is_absence():
    """
    F11. R18 moved `closing_date`/`maturity_date` onto `fields.is_supplied` so
    an empty string could not render `| Anticipated Closing |  |`. The rule was
    never extended to the elements *inside* a `List[str]`, and
    `conditions=["Real condition", "", "   "]` rendered

        - Real condition          <- Executive Summary
        -
        -
        1. Real condition         <- Conditions of Approval
        2.
        3.

    An empty numbered condition in an IC memo is the same object as the empty
    table row, and worse: the number is a label the package supplied, so it
    reads as a condition of approval the reader's copy has lost.

    THE PROPERTY: a list whose empty and whitespace elements are removed must
    render byte-identically to the same list written without them. Compared
    against rendered output, not against `fields.supplied_items`, so a section
    that reaches its own conclusion about `""` is caught whichever mechanism
    it used.

    Red-proof (must fail): revert either site to `deal.conditions` —
    creditmemo/sections/executive.py or creditmemo/sections/recommendation.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc $HOME/probeenv/bin/python -m pytest tests/ -q
    Observed: 1 failed, 426 passed for each site reverted, and 1 failed,
    426 passed with both reverted — this gate is the only one that sees it,
    which is why it compares whole renderings rather than one section's.
    """
    padded = CreditMemo(_deal(conditions=[
        "Receipt of final appraisal", "", "   ", "\t", "Environmental review",
    ])).to_markdown()
    clean = CreditMemo(_deal(conditions=[
        "Receipt of final appraisal", "Environmental review",
    ])).to_markdown()
    assert padded == clean, (
        "an empty condition renders as something.\nOnly in the padded "
        f"rendering: {sorted(set(padded.split(chr(10))) - set(clean.split(chr(10))))}")

    # Not vacuous: the surviving conditions must actually reach both sections,
    # numbered from 1, or the gate above would pass on a package that dropped
    # every condition.
    assert "- Receipt of final appraisal" in clean
    assert "1. Receipt of final appraisal" in clean
    assert "2. Environmental review" in clean

    # A list with nothing in it but empties is an empty list, so neither the
    # Executive Summary preamble nor the Conditions heading is emitted over
    # nothing — R4's bare-heading defect, in the shape F11 reaches it.
    empties = CreditMemo(_deal(conditions=["", "  "])).to_markdown()
    none_at_all = CreditMemo(_deal(conditions=[])).to_markdown()
    assert empties == none_at_all
    assert "### Conditions of Approval" not in empties
    assert "**Subject to the following conditions:**" not in empties


def test_g14b_whitespace_is_absence_for_an_optional_string_too():
    """
    F11's other half. `fields.is_supplied` tested `bool(value)`, so `""` was
    absence and `"   "` was a statement — and `mission="   "` rendered
    `### Mission` above a blank line, which is R4's bare heading arriving by a
    different route. One rule now covers both.

    Red-proof (must fail): restore `return bool(value)` in
    creditmemo/fields.py.
    Command: as above.
    Observed: 2 failed, 425 passed — this gate and its list half.
    `test_g9_the_optional_string_rule_is_stated` stays green, because it
    exercises `""` and never `"   "`: that is the hole this closes.
    """
    from creditmemo import fields as fields_module

    assert fields_module.is_supplied("   ") is False
    assert fields_module.is_supplied("\t\n") is False
    assert fields_module.is_supplied(" x ") is True

    for cls_name, field in _optional_str_fields():
        blank = CreditMemo(_deal_with_string(cls_name, field, "   ")).to_markdown()
        absent = CreditMemo(_deal_with_string(cls_name, field, None)).to_markdown()
        assert blank == absent, (
            f"{cls_name}.{field}: a whitespace-only string renders differently "
            f"from an absent one.\nOnly in the blank rendering: "
            f"{sorted(set(blank.split(chr(10))) - set(absent.split(chr(10))))}")


# ── F16 — section_count is a fact about the memo, not about its text ─────────

def test_the_section_count_is_not_moved_by_caller_prose():
    """
    F16. `section_count()` counted occurrences of `"\\n## "` in the rendered
    Markdown. The memo reproduces caller prose verbatim — that is the whole
    point of the input-fidelity work — so a caller who wrote a `## ` line into
    `deal_summary`, a mission or an impact narrative was counted as a section:
    a seven-section memo reported eight.

    Red-proof (must fail): restore
    `return self.to_markdown().count("\\n## ")` in creditmemo/memo.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc $HOME/probeenv/bin/python -m pytest tests/ -q
    Observed: 1 failed, 426 passed — "a '## ' line in deal_summary moved the
    section count from 7 to 8".
    """
    from creditmemo.renderers import markdown as markdown_module

    plain = CreditMemo(_deal()).section_count()
    assert plain == 7, f"the memo has seven sections and reports {plain}"

    for field, value in [
        ("deal_summary", "Background\n\n## Market Overview\n\nThe borrower."),
        ("deal_summary", "## A\n\n## B\n\n## C"),
    ]:
        inflated = CreditMemo(_deal(**{field: value})).section_count()
        assert inflated == plain, (
            f"a '## ' line in {field} moved the section count from {plain} to "
            f"{inflated}")

    # And the number is the renderer's own list, not a second copy of it that
    # can drift: every section in that tuple emits exactly one `## ` heading.
    md = CreditMemo(_deal()).to_markdown()
    assert md.count("\n## ") == len(markdown_module.SECTIONS)


# ── F10 — the memo does not name a section it does not contain ───────────────

def test_the_memo_does_not_point_at_a_section_it_does_not_contain():
    """
    F10. The Deal Summary row was
    `lt.use_of_proceeds or 'See Transaction Structure'`, so an unsupplied field
    printed

        | Use of Proceeds | See Transaction Structure |

    while `### Use of Proceeds` appeared nowhere in the memo — sections/
    transaction.py gates that heading on the same field. The memo referred an
    Investment Committee to a section it did not contain, and the referral was
    produced by the field's *absence*, so it appeared on exactly the deals where
    it was wrong.

    Two properties, because the narrow one alone would let the fallback come
    back under another name: the row and the heading appear together or not at
    all, and no table cell in the memo refers to a heading the memo lacks.

    Red-proof (must fail): restore the `or 'See Transaction Structure'`
    fallback in creditmemo/sections/executive.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc $HOME/probeenv/bin/python -m pytest tests/ -q
    Observed: 2 failed, 425 passed — this gate, and
    test_g14b_whitespace_is_absence_for_an_optional_string_too, which sees the
    same fallback from the other side.
    """
    for supplied in [None, "", "   ", "Acquisition and renovation"]:
        md = CreditMemo(_deal(loan_terms=LoanTerms(
            deal_type="loan", amount=2_500_000,
            use_of_proceeds=supplied))).to_markdown()
        row = "| Use of Proceeds |" in md
        heading = "### Use of Proceeds" in md
        assert row == heading, (
            f"use_of_proceeds={supplied!r}: Deal Summary row present={row}, "
            f"section heading present={heading}")

    headings = set()
    referrals = []
    for supplied in [None, "Acquisition and renovation"]:
        md = CreditMemo(_deal(loan_terms=LoanTerms(
            deal_type="loan", amount=2_500_000,
            use_of_proceeds=supplied))).to_markdown()
        headings = {line.lstrip("#").strip() for line in md.split("\n")
                    if line.startswith("#")}
        for line in md.split("\n"):
            if not line.startswith("|"):
                continue
            for cell in line.split("|"):
                cell = cell.strip()
                if cell.startswith("See "):
                    referrals.append((cell, cell[len("See "):], sorted(headings)))
    unmet = [(cell, target) for cell, target, hs in referrals if target not in hs]
    assert not unmet, (
        f"table cells referring an IC to a section the memo does not have: "
        f"{unmet}")


# ── F12 — what the .docx adds that the Markdown does not have ───────────────

def test_the_only_thing_the_docx_adds_is_an_empty_paragraph(tmp_path):
    """
    F12. README.md said the .docx adds "nothing that has no line behind it"
    while `render`'s own docstring said, correctly, "nothing *carrying text*".
    The renderer appends an empty spacer paragraph after every table — Word runs
    a table into the next heading without one — and emits each section rule as
    an empty paragraph with a bottom border. Measured on the quickstart deal:
    6 tables, 13 empty paragraphs, of which 7 are rules and 6 are spacers.

    The README now carries the qualifier and those figures. This gates the
    property behind them, which the README cannot: every empty paragraph in the
    document is a rule or a table spacer, and there are exactly as many of each
    as the Markdown has rules and tables.

    Red-proof (must fail): add a second `doc.add_paragraph()` to `_add_table`
    in creditmemo/renderers/docx.py.
    Command:
      rm -rf $HOME/pyc && mkdir -p $HOME/pyc && CREDITMEMO_REQUIRE_DOCX=1 \
      PYTHONPYCACHEPREFIX=$HOME/pyc $HOME/probeenv/bin/python -m pytest tests/ -q
    Observed: 1 failed, 426 passed — "31 empty paragraphs: 7 rules + 24
    spacers, for 12 Markdown tables".
    """
    pytest.importorskip("docx")
    import docx as _docx

    deal = _fully_populated_deal()
    md = CreditMemo(deal).to_markdown()
    path = str(tmp_path / "spacers.docx")
    CreditMemo(deal).save_docx(path)
    document = _docx.Document(path)

    md_rules = sum(1 for line in md.split("\n") if line.strip() == "---")
    md_tables = len(_table_headings(md))

    border = ("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
              "pBdr")
    empties = [p for p in document.paragraphs if not p.text.strip()]
    rules = [p for p in empties if p._p.find(f".//{border}") is not None]
    spacers = [p for p in empties if p not in rules]

    assert len(rules) == md_rules, (
        f"{len(rules)} bordered empty paragraphs for {md_rules} Markdown rules")
    assert len(spacers) == md_tables, (
        f"{len(empties)} empty paragraphs: {len(rules)} rules + "
        f"{len(spacers)} spacers, for {md_tables} Markdown tables")
    assert len(empties) == md_rules + md_tables, (
        f"the .docx has {len(empties)} empty paragraphs and the Markdown "
        f"accounts for {md_rules + md_tables}")
