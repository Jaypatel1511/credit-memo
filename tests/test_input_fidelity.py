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
    RiskFactor, SEVERITIES,
)
from creditmemo.memo import CreditMemo
from creditmemo.sections import risk as risk_section

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "creditmemo"


def _package_sources():
    """Every shipped .py file. tests/ is deliberately not among them."""
    return sorted(PACKAGE.rglob("*.py"))


def _deal(borrower=None, impact=None, risks=None, financials=None, **kw):
    return DealProfile(
        deal_name="Test Deal",
        borrower=borrower or BorrowerProfile(
            name="Test Borrower", borrower_type="nonprofit",
            sector="healthcare", state="IL", city="Chicago"),
        loan_terms=LoanTerms(deal_type="loan", amount=2_500_000,
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
    contradicts itself, and whose bolded run in the Word document reads "CDFI
    Certified" directly beneath the borrower's name. `Minority Depository
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


# ── Packaging ────────────────────────────────────────────────────────────────

def _declared_runtime_dependencies():
    text = io.open(ROOT / "pyproject.toml", encoding="utf-8").read()
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
    assert block, "no [project].dependencies in pyproject.toml"
    return re.findall(r'"([^"]+)"', block.group(1))


def test_every_declared_runtime_dependency_is_actually_imported():
    """
    0.1.0 and 0.2.0 declared `pandas>=1.4.0` as a hard runtime dependency. No
    module in the package imports pandas, or anything else outside the standard
    library — so every install pulled pandas and numpy, and inherited their
    platform and Python-version constraints, to build strings.
    """
    source = "\n".join(io.open(p, encoding="utf-8").read() for p in _package_sources())
    for dep in _declared_runtime_dependencies():
        module = re.split(r"[<>=!~\[; ]", dep)[0].replace("-", "_")
        assert re.search(rf"^\s*(?:import|from)\s+{re.escape(module)}\b",
                         source, re.M), (
            f"{dep!r} is declared as a runtime dependency but never imported")


def test_the_package_renders_a_memo_with_no_third_party_import():
    """
    Derived from behaviour, not from the declaration: block every third-party
    import and render a full memo anyway.

    Red-proof (must fail): add `import pandas` to any module in creditmemo/.
    Observed: 1 failed.
    """
    program = textwrap.dedent("""
        import sys
        BLOCKED = ("pandas", "numpy", "docx")
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
        print("ok")
    """)
    result = subprocess.run([sys.executable, "-c", program],
                            capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
