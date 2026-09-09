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
    assert "| Cash & Equivalents | $0.45MM |" in md

    # A supplied zero is a number, not an absence — in either position.
    md = CreditMemo(_deal(financials=FinancialData(cash=0))).to_markdown()
    assert "| Cash & Equivalents | $0.00MM |" in md, "a supplied zero was dropped"

    md = CreditMemo(_deal(financials=FinancialData(
        total_assets=0, total_liabilities=3_500_000))).to_markdown()
    assert "| Total Assets | $0.00MM |" in md, "a supplied zero was dropped"


def test_a_borrower_zero_is_not_discarded_either():
    borrower = BorrowerProfile(
        name="N", borrower_type="nonprofit", sector="healthcare", state="IL",
        city="Chicago", total_assets=0.0)
    md = CreditMemo(_deal(borrower=borrower)).to_markdown()
    assert "Financial Snapshot" in md
    assert "**Total Assets:** $0.0MM" in md


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
    `- **Total Assets:** $8.0MM` reached Word as the literal characters
    `**Total Assets:** $8.0MM` — raw Markdown in the IC's document.

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
    assert "Total Assets: $8.0MM" in texts


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


def test_conditions_use_words_list_number_style(tmp_path):
    """
    Conditions of Approval arrived as ordinary paragraphs whose text began with
    a literal "1. ", so Word saw no list: no renumbering, no indent, and the
    numbers were part of the sentence.
    """
    docx = pytest.importorskip("docx")
    deal = _deal(conditions=["Receipt of final appraisal", "Evidence of match"])
    path = str(tmp_path / "conditions.docx")
    CreditMemo(deal).save_docx(path)
    doc = docx.Document(path)
    numbered = [p for p in doc.paragraphs if p.style.name == "List Number"]
    assert [p.text for p in numbered] == ["Receipt of final appraisal",
                                          "Evidence of match"]
    assert not any(p.text.startswith("1. ") for p in doc.paragraphs)


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
ZERO_RENDERINGS = [
    # (holder, field, the zero supplied, the text the memo must show)
    ("loan_terms",     "interest_rate",        0.0, "0.00%"),
    ("loan_terms",     "term_years",           0,   "0 years"),
    ("loan_terms",     "amortization_years",   0,   "0 years"),
    ("loan_terms",     "min_dscr_covenant",    0.0, "Minimum DSCR of 0.00x"),
    ("loan_terms",     "max_ltv",              0.0, "Maximum LTV of 0%"),
    ("borrower",       "year_founded",         0,   "**Year Founded:** 0"),
    ("borrower",       "total_assets",         0.0, "**Total Assets:** $0.0MM"),
    ("borrower",       "annual_revenue",       0.0, "**Annual Revenue:** $0.0MM"),
    ("financial_data", "revenue_y1",           0.0, "$0.00MM"),
    ("financial_data", "revenue_y2",           0.0, "$0.00MM"),
    ("financial_data", "revenue_y3",           0.0, "$0.00MM"),
    ("financial_data", "net_income_y1",        0.0, "$0.00MM"),
    ("financial_data", "net_income_y2",        0.0, "$0.00MM"),
    ("financial_data", "net_income_y3",        0.0, "$0.00MM"),
    ("financial_data", "ebitda_y1",            0.0, "$0.00MM"),
    ("financial_data", "ebitda_y2",            0.0, "$0.00MM"),
    ("financial_data", "ebitda_y3",            0.0, "$0.00MM"),
    ("financial_data", "total_assets",         0.0, "| Total Assets | $0.00MM |"),
    ("financial_data", "total_liabilities",    0.0, "| Total Liabilities | $0.00MM |"),
    ("financial_data", "net_assets_equity",    0.0, "| Net Assets / Equity | $0.00MM |"),
    ("financial_data", "cash",                 0.0, "| Cash & Equivalents | $0.00MM |"),
    ("financial_data", "dscr",                 0.0, "0.00x"),
    ("financial_data", "current_ratio",        0.0, "0.00x"),
    ("financial_data", "debt_to_equity",       0.0, "0.00x"),
    ("financial_data", "ltv",                  0.0, "0.0%"),
    ("financial_data", "projected_revenue_y1", 0.0, "| Revenue | $0.00MM |"),
    # The Projections DSCR row gated all three years on `projected_dscr_y1`,
    # so a supplied Year-2 or Year-3 figure was dropped and the section
    # rendered a header-only table — the `has_balance`/`cash` defect of
    # 0.2.0, still live in the block next door. Found by this gate's
    # coverage check, not by any list.
    ("financial_data", "projected_dscr_y1",    0.0, "| DSCR | 0.00x | N/A | N/A |"),
    ("financial_data", "projected_dscr_y2",    0.0, "| DSCR | N/A | 0.00x | N/A |"),
    ("financial_data", "projected_dscr_y3",    0.0, "| DSCR | N/A | N/A | 0.00x |"),
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


@pytest.mark.parametrize("holder,field,zero,expected", ZERO_RENDERINGS,
                         ids=lambda v: v if isinstance(v, str) else None)
def test_g9_a_supplied_zero_renders_as_the_value(holder, field, zero, expected):
    """
    G9. A supplied `0` / `0.0` renders as the value — never as "N/A", never as
    an omitted row.

    The unset rendering is measured too, so the gate cannot pass because some
    *other* field happens to produce the same text: `expected` must be absent
    when the field is `None` and present when it is zero.

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

    covered = {field for _, field, _, _ in ZERO_RENDERINGS}
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
#: It also does not *begin* with "#", "- ", "* " or "1. ". A line that begins
#: with a real Markdown block marker is restyled into the Word equivalent of
#: that marker — a heading, a bullet, a numbered item — which is the deferral
#: CHANGELOG.md discloses. That class replaces a marker with its equivalent;
#: "2019." was replaced with a different number, which is why it is here.
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
            if is_text or f.name == "conditions":
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
