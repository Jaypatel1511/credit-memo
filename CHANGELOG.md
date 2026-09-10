# Changelog

All notable changes to credit-memo are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.2.1] — 2026-09-08

Everything in this entry was measured on the code in this repository with the
README quickstart deal, on Python 3.12 with python-docx 1.2.0. CI runs the suite
on 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14 -- the matrix used to stop at 3.12 while
this line claimed six versions and `requires-python` admitted all six; the
matrix moved. The suite goes from **86 tests to 340**. Every gate below was
watched to fail against a deliberate mutation before being trusted; the
mutations are recorded in the gates' own docstrings, with the exact command and
the count that reddened.

### Fixed

**The .docx printed the memo's front matter twice.**

The renderer built a cover block by hand — a `Title` paragraph, an `H1` of the
deal name, and a four-row Fund / Prepared By / Date / IC Date table read
straight off the `DealProfile` — and *then* parsed the generated Markdown,
which carries all three of those things itself. Measured on the quickstart deal
against 0.2.0:

- the Markdown had **22 headings**; the .docx had **24 heading paragraphs**
- `Southside Health Center — $2.5MM Term Loan` appeared **twice** as a heading
- `INVESTMENT COMMITTEE MEMORANDUM` appeared in the .docx and **in no line of
  the Markdown** — the renderer's own upper-cased copy of the memo title
- each metadata value appeared once more in the .docx than in the Markdown:
  `Fund:` 1 → 2, `Prepared By:` 2 → 3, `Date:` 3 → 4, `IC Date:` 2 → 3
- the Markdown produced **6 tables / 36 rows**; the .docx **7 tables / 40 rows /
  101 cells**

Every .docx gate in 0.2.0 was written to subtract `doc.tables[0]`, so the whole
suite measured *around* the duplicate rather than at it.

The hand-built block is gone. The .docx is now a pure function of the Markdown:
the first `#` heading takes Word's `Title` style, and nothing is emitted that
has no Markdown line behind it. The same deal now produces **6 tables / 36 rows
/ 93 cells**, and **23 headings** with none duplicated — 23 rather than the 22
the 0.2.0 Markdown had, because 0.2.1 adds the `### Certifications &
Designations` heading described three paragraphs below.

**The .docx's entire non-table half was ungated.** Deleting the title, every
heading, every narrative paragraph, every bullet and every rule from the
renderer left 0.2.0's suite at **86 passed**. Three gates now hold it: a content
multiset over paragraphs and cells together, a prose-only variant of the same,
and a heading multiset.

**A `datetime.date` in `prepared_date` crashed `save_docx`.** It rendered
correctly in Markdown and raised `TypeError: 'datetime.date' object is not
iterable` in Word, because the hand-built header table wrote the raw
`DealProfile` value into a Word cell while the Markdown path interpolated it
into an f-string. Removing that table removes the only place the two paths
could disagree about types; a gate now says so.

**Bullet list items carried literal `**` into Word.** Only the plain-paragraph
branch stripped Markdown emphasis, so `- **Total Assets:** $8.0MM` reached the
Word document as the characters `**Total Assets:** $8.0MM` — raw Markdown
syntax in the file handed to an Investment Committee. Every text branch now
strips emphasis.

**A lone `*` was deleted from prose and kept in table cells.** The .docx
paragraph path stripped every `*` unconditionally; the table-cell splitter
stripped only `**`. The same character therefore survived in a Word table cell
and vanished from a paragraph of the same document:

    markdown : 'EBITDA margin improved 5 * 3 basis points.'
    docx     : 'EBITDA margin improved 5  3 basis points.'

A lone asterisk in underwriter prose is content — multiplication, a footnote
mark, a redaction — and deleting it changes the number the Investment Committee
reads. Both paths now go through one helper, `creditmemo.text.strip_emphasis`,
which removes only markers that pair (under CommonMark's flanking rule, so
`5 * 3` and `5 ** 3` are arithmetic) and leaves an unpaired `*` alone. Where the
pairing is ambiguous it preserves the characters rather than guessing: the worst
case is a literal `*` in the Word file, not a missing digit.

**Underwriter prose beginning with `|` was silently turned into a table.** A
leading pipe alone made a line a table row, so
`deal_summary="| we structured this as a leveraged loan"` left the Markdown as
written and arrived in the .docx as a one-cell Word table with the pipe eaten.
A run of pipe lines is now a table only if it carries a delimiter rule where GFM
requires one — immediately under the header — which every table this package
emits does.

**Underwriter prose beginning with `---` was deleted outright.** The horizontal
rule branch matched `startswith("---")`, so `"--- see appendix B for the full
rent roll"` was replaced by a rule and the sentence was gone from the Word
document. Nothing raised; the file saved and reported success. The rule line is
now matched exactly, which is the only form the Markdown renderer emits.

**A supplied `0` was discarded as if the field were empty.** Optional financial
figures were tested for truthiness. Two consequences, both silent:

- `FinancialData(cash=450_000)` rendered **no Balance Sheet section at all** —
  the section was gated on three *other* fields, and `cash` was consulted only
  after they had already decided the section did not exist
- a supplied `0` — no cash on hand, no net income, a fully depreciated asset
  base — was indistinguishable from a field nobody filled in

Every `Optional` field on every dataclass is now consulted through
`creditmemo.fields.is_supplied`, or with a literal `is not None`, and never for
truthiness. `is_supplied` treats a supplied `0`, `0.0` or `False` as the
statement it is; the single exception it makes is `Optional[str]`, where the
falsy value is `""`, which states nothing and whose rendering would be a section
heading over an empty body. That exception is a behaviour, gated by
`test_g9_the_optional_string_rule_is_stated`, rather than an accident of which
sites were visited.

**Three of those sites were still truthiness tests when the entry above was
first written**, and the sentence claiming otherwise shipped ahead of the fix:

- `interest_rate` and `term_years` in the Executive Summary, and `interest_rate`
  in the Transaction Structure. With `interest_rate=0.0, term_years=0` the memo
  read `| Interest Rate | N/A |` and `| Term | N/A |` in the Executive Summary
  while the Transaction Structure, four lines further down the same document,
  read `| Loan Term | 0 years |`. A 0% forgivable loan, an EQ2 note and a 0%
  QLICI B tranche are routine instruments for this package's callers, and "N/A"
  tells an Investment Committee the rate is unknown when the caller stated it is
  zero. Both fields now render through one shared formatter, so the two sections
  cannot disagree again.
- `FinancialData.revenue_trend` was gated on
  `if self.revenue_y1 and self.revenue_y3`. Revenue falling from $5MM to zero is
  the most alarming thing that field can express, and it was the one case the
  memo would not report; so was a recovery from zero. Now `is not None`.
  Its `decreasing` and `stable` branches also had no test coverage at all — the
  memo's only automated analytical claim had both of its adverse branches
  ungated. All three are gated now.

**The Financial Projections DSCR row gated all three years on
`projected_dscr_y1`.** `FinancialData(projected_dscr_y2=1.42)` rendered the
`### Financial Projections` heading and a table with nothing in it but the
header row; the one figure supplied appeared nowhere in the memo. This is the
`has_balance`/`cash` defect above, still live in the block next door, and it was
found by a gate's coverage check rather than by reading. The row is now gated on
any of the three years.

**`RiskFactor.severity` accepted anything and rendered only three spellings.**
The Risk Assessment section groups by exact match on `"High"`, `"Medium"`,
`"Low"`. Measured against 0.2.0, `"Critical"`, `"high"`, `"HIGH"`, `"medium"`,
`"Med"`, `"severe"` and `""` all constructed without complaint, stayed on
`deal.risks`, and then vanished from the memo — the section rendered empty,
with no warning on any stream. `severity` is now validated on construction
against `SEVERITIES`, matched case-insensitively and normalised to title case;
anything else raises `ValueError` naming the allowed values.

The vocabulary stays at three levels. Whether the scale should carry a level
above `High` is a design question, not a patch-release decision.

**The validated string fields disagreed about case.** `borrower_type`,
`sector`, `deal_type` and `recommendation` compared with `in` against
lowercase-keyed dicts, so `"Nonprofit"` raised while `"nonprofit"` passed;
`severity` was not validated at all. All five now match case-insensitively
through one shared normaliser. This is strictly wider than the old behaviour:
nothing accepted before is rejected now.

**A fractional `ltv` produced two different percentages for one number, in one
memo.** `LoanTerms.max_ltv` is a fraction — `transaction.py` renders
`max_ltv*100` — as are `interest_rate`, `cde_fee_rate` and
`origination_fee_pct`. `FinancialData.ltv` alone is rendered unscaled, and
nothing said so: not the declaration, not `README.md`. A caller who followed
the package's own dominant convention and passed `0.75` to both fields got

    - Maximum LTV of 75%              <- Transaction Structure
    | Loan to Value | 0.8% | <= 80% | <- Financial Analysis

on one deal, in **both** the Markdown and the Word document — a 75% LTV
reaching an Investment Committee as 0.8% against an 80% benchmark, reading as
extraordinarily overcollateralised.

`FinancialData.ltv` now raises `ValueError` for a value in `(0.0, 1.0]`, in the
shape `borrower_type`'s error already uses:

    ltv must be in percentage points, not a fraction: got 0.75, which renders
    as 0.8%. A 75% LTV is ltv=75.0. (LoanTerms.max_ltv is the fraction; the two
    fields are on opposite scales until they are unified in 0.3.0.)

No value is auto-interpreted. A rule like "`<= 1.0` means a fraction" would be
a silent guess and a 100% LTV is real; guessing is the class of defect this
release closes. The band is chosen so that **what it rejects is worth the
price**: `max_ltv` is a covenant cap written as a fraction, so `[0.0, 1.0]` is
the range a caller might send to both fields, and read as percentage points
anything in it but zero claims an LTV of one percent or less — under a cent of
debt per dollar of collateral. `0.0` is exempt: it is the single value the two
conventions render identically, and a supplied zero must still reach the memo.

It is not costless, and an earlier draft of this entry said it was — "rejects
nothing legitimate", two sentences before the same paragraph rejected a looser
threshold on the grounds that it would refuse a genuine 1-5% LTV "with no way
to express it". `ltv=0.8` is that instrument, and this band refuses it too. The
difference is one of degree, and it is why the band stops where it does: at
`1.0` the two readings are 1% and 100%, and every value below it is an LTV no
lender writes, where a looser threshold would take in values that are merely
unusual. An 0.8% LTV is not expressible in 0.2.1; a caller who has one should
state it in prose on the memo until the scales are unified in 0.3.0. The
threshold stays where it is.

The unit is now documented on `ltv` and on every sibling that has one:
`interest_rate`, `max_ltv`, `origination_fee_pct`, `min_dscr_covenant`, `dscr`,
`current_ratio`, `debt_to_equity`, the three projected DSCRs, `credit_price`,
`leverage_loan_rate`, `qlici_a_rate`, `qlici_b_rate` and `cde_fee_rate`. An
undocumented unit is what produced this, so G12 gates the documentation as well
as the validation, and a second gate checks that list against the schema so it
cannot drift.

### Changed

**`nonprofit` no longer claims 501(c)(3) status.** `BORROWER_TYPES["nonprofit"]`
rendered as `Nonprofit organization (501c3)`. `nonprofit` is the only value
available for a 501(c)(4) advocacy organisation, a 501(c)(6) trade association,
a 501(c)(12) rural cooperative, a church or a tribal nonprofit, so the
parenthetical asserted a specific, checkable legal fact the caller never
supplied — one that bears on charitable purpose, grant eligibility and UBIT
treatment. It now renders `Nonprofit organization`. There is no `tax_status`
input in 0.2.1; adding one is a feature.

**The empty-risk sentence describes the inputs, not the deal.** With no risks
supplied the section read as an affirmative analytical finding — that the deal
had been examined and nothing of concern turned up — produced by nothing more
than an empty list. It now reads:

> **No risk factors were provided.** This section reflects the risk factors
> supplied with this deal; it is not an assessment that no material risks exist.

A gate forbids that shape of sentence anywhere in the shipped package.

**The seven eligibility and certification flags are three-state.**
`is_cdfi_certified`, `is_mdi`, `is_low_income_area`, `is_nmtc_eligible`,
`is_opportunity_zone`, `is_minority_borrower` and `is_women_borrower` change
from `bool = False` to `Optional[bool] = None`. `True` renders the affirmative
line as before, `False` renders an explicit negative, `None` renders nothing.

**Each negative line negates itself.** The borrower certification block first
rendered its negatives by reusing the affirmative label list under a negating
header, so `is_cdfi_certified=False` produced

    **Not certified:** CDFI Certified

— a line that contradicts itself, and that reaches the Word document as the
sentence `Not certified: CDFI Certified`. `Minority Depository Institution
(MDI)` read acceptably under the same header only because it is a bare noun
phrase; the construction was wrong for any label carrying a past participle,
and one of the two did. Each certification flag now carries its own negative
string and renders as a bullet, the same shape the impact section already
used:

    - ❌ Not CDFI certified
    - ❌ Not a Minority Depository Institution (MDI)

That also puts the certification block and the eligibility block two sections
down into one visual language for what is the identical three-state idea. The
block gains a `### Certifications & Designations` heading, which the bullets
need and which the eligibility block already had.

G6 did not catch this: it asserts the three renderings are **distinct**, which
a self-contradicting sentence satisfies. G8 is the gate that reads the sentence
the negative branch produces — for each of the seven flags it takes the
affirmative claim from the flag's own `True` rendering and requires every run
of the `False` rendering that asserts that claim to negate it in the same run.
The property is run-level self-containment, not substring absence: the impact
negatives contain their affirmative label as a substring and are correct,
because the negation sits in the run with the label.

**This is output-neutral for every existing caller who omits these fields**:
they move from `False`-rendered-as-nothing to `None`-rendered-as-nothing, and a
gate asserts that equivalence for all seven. It changes output **only** for a
caller who passed an explicit `False` — precisely the case that was silent
before, because `False` and "never touched" were the same value and the package
could not represent "we checked, and the answer is no".

A section whose flags are all `None` now says so rather than rendering a bare
heading with nothing under it. Through 0.2.0, `ImpactData()` produced
`### Target Market & Eligibility` followed immediately by the section rule.

**Ordered lists keep their numbers as text, and Word is never asked to supply
one.** An intermediate build of 0.2.1 restyled them into Word's `List Number`
style, so Word saw a real list -- and drew the wrong numbers on it. Word does
not restart a numbered list on its own: every `List Number` paragraph
python-docx creates resolves to one continuous numbering definition (`numId=5`,
taken from the style, with no paragraph-level `w:numPr` to override it).
Measured on a deal with a two-item ordered list in `deal_summary` and three
`conditions`, the Markdown reads

    1. Execute the loan agreement          <- deal_summary
    2. Fund the escrow
    1. Receipt of final appraisal          <- Conditions of Approval
    2. Evidence of matching funds
    3. Environmental review

and the .docx held five `List Number` paragraphs with the numbers stripped from
their text, so Word printed the Conditions of Approval as **3, 4, 5**. The same
restyling deleted a caller's own number outright where a condition carried an
embedded newline: `"Payoff of the 2019 note\n3. Third-party report"` lost its
literal `3.` on the way into Word.

Ordered items are therefore plain paragraphs whose text carries the number
exactly as the Markdown has it -- which is what 0.2.0 did, and it was right by
construction. Per-paragraph `w:numPr` with `w:startOverride` would also work and
was rejected: it is raw OOXML surgery needing an audit of its own, against a
principle that already says worst case a list loses its styling, no case loses a
number the caller wrote. `List Bullet` stays, because a bullet glyph carries no
information. Gated by **G13**, which reads the numbering definition each
paragraph resolves to out of the saved file and requires it to draw a bullet or
nothing.

No gate that existed before this fix could see it. At the commit that carried
the defect the suite was 284 passed, and the one test that named the style
asserted its **presence**. `tests/test_docx.py`'s multiset gates were blind for
the reason G11 exists: they normalised the Markdown with a `_MD_NUMBER` regex
copied from the renderer, and so subtracted the number from the Markdown side
exactly as the renderer subtracted it from the Word side. That normaliser is
gone, and with it the last of the three re-implementations that comment warned
about.

**An empty `closing_date` or `maturity_date` rendered an empty table row.**
`sections/transaction.py` tested those two with a bare `is not None`, while
`README.md`, `creditmemo.fields.is_supplied`, this changelog and the gate's own
exemption list all stated that for a string the falsy value is `""` and `""` is
absence. So `closing_date=""` produced

    | Anticipated Closing |  |

-- a labelled row of the Proposed Terms table, in an IC memo, with nothing in
it -- while `mission=""` next door correctly rendered nothing at all. Four
documents were right and two lines of code were wrong; the code moved. Both
fields now go through `fields.is_supplied`.

The gate that was supposed to cover this exercised `mission`, which was one of
the fields that was already right. It now covers **every `Optional[str]` field
on every dataclass**, discovered from the annotations rather than listed, and
the property it checks is mechanism-independent: a field set to `""` must
produce a memo byte-identical to the same field left `None`. A section that
reaches its own conclusion about `""` is caught whichever way it reached it.

**The `ltv` scale check was construction-only.** `FinancialData` is not frozen,
so

    f = FinancialData()
    f.ltv = 0.75            # read off a spreadsheet, field by field

raised nothing and rendered `| Loan to Value | 0.8% |` -- the defect above,
verbatim, by the route an incremental build takes, and the route a caller who
had just hit the constructor's error message would most naturally fall back to.
The check now also runs at the render boundary, in
`sections/financial.py`, where the number is about to be printed. The
constructor check stays: it fires earlier and its traceback points at the
caller's own line. Freezing the dataclass would also close it and is a breaking
change, deferred to 0.3.0.

**`max_ltv` rendered at zero decimal places.** `max_ltv=0.795` printed as
`Maximum LTV of 80%` -- a covenant reported looser than the borrower agreed to,
at a value plausible enough that nobody would query it. It now renders `.1f`,
the same precision as the `FinancialData.ltv` it caps; the two describe the same
quantity and are read against each other.

**`save_docx` raised an unnamed error on control characters.** A vertical tab,
form feed or NUL -- routine in text pasted out of a PDF -- reached lxml, which
raised

    ValueError: All strings must be XML compatible: Unicode or ASCII,
    no NULL bytes or control characters

naming no field, no line, no character and no file, after `save_markdown` had
already accepted the same deal and reported success. The renderer now checks
before it builds anything and names the codepoint and the memo line. Nothing is
sanitised: deleting or substituting a character is the silent alteration this
release exists to remove. The character class was measured against python-docx,
not read off the XML spec -- `\t`, `\n`, `\r` and `\x7f` are accepted, and
every codepoint the renderer refuses was fed through `add_paragraph` and `save`
and observed to fail.

**A dead clause in the `ltv` check, and a gate that could not fail on it.**
`_reject_fractional_ltv` began `if value is None or value == 0: return`, above a
band written `0 < value <= 1.0` that already excluded zero. The clause could
never fire, and the docstring named it as the thing keeping zero out. Measured
both ways at 340 tests: with the clause and without it the suite is 340 passed,
and `test_g12_zero_is_the_one_number_both_conventions_agree_on` passes either
way. It is gone and that test stays -- the property is real, the clause was not
producing it.

**The README enumerated nine tables and the memo renders ten.** Balance Sheet
Summary was missing from the Word-output section, and it is the one an IC reads
for the borrower's cash position. Nothing was wrong with the code; a reader
counting tables against the README would have concluded one had been dropped.
Now gated: a fully populated memo's table headings, the count of real Word
tables in the saved file, and the README's phrase for each are checked against
one declared list.

**G11's coverage guard special-cased a field by name.** Its docstring claimed to
cover "every list-of-string field" and its code read
`if is_text or f.name == "conditions"`. Adding
`covenants: list = field(default_factory=list)` to `DealProfile` left the suite
green and the field reached neither rendering. List fields are now classified by
what they hold: `List[str]` needs a sentinel, a list of anything else is covered
through that thing's own fields, and a bare `list` is undecided and reds until
someone decides. `DealProfile.risks` and `DealProfile.conditions` carry their
element types for this reason.

**Section rules are Word paragraph borders.** They were paragraphs containing
sixty literal underscores — selectable text that does not span the column, does
not follow the page margins, and lands in every copy-paste of the memo.

**One amount format.** The Deal Summary table showed `$2.50MM` where Proposed
Terms showed `$2,500,000 ($2.50MM)`. Both now show the full form. The gate on
this claim was `assert "$2.50MM" in result or "2,500,000" in result` — an `or`
over the two formats, which is the negation of the claim and would have passed
on a memo that used a different one in each section. It asserts the row.

**Every dollar figure below $5,000 printed as `$0.00MM` — the same characters a
stated zero prints.** Each section formatted its own money: `sections/financial`
divided by `1e6` at two decimals, `sections/borrower` at *one*,
`sections/transaction` inlined the same divide four more times. Two decimals of
`$MM` resolve to $10,000, so measured on this branch:

    supplied         0 -> | Revenue | $0.00MM |  | Cash & Equivalents | $0.00MM |
    supplied     4,999 -> | Revenue | $0.00MM |  | Cash & Equivalents | $0.00MM |
    supplied    49,000 -> | Revenue | $0.05MM |
    total_assets=49,000 -> - **Total Assets:** $0.0MM

A $4,999 cash balance and a zero cash balance reached an Investment Committee as
one string, with nothing to tell a reader which they were looking at — and R6
requires a *stated* zero to reach the memo, so both readings were live.
`microenterprise` is a declared `SECTORS` value and $5k-$50k is that product's
normal size. The memo also contradicted itself two lines apart, because the
revenue trend is computed on the raw values and was right all along:

    | Revenue | $0.00MM | $0.00MM | $0.00MM |
    **Revenue Trend:** Increasing — revenue has been increasing ...

`creditmemo/money.py` is now the only place a dollar figure becomes text. The
`$MM` unit is used only from **$1,000,000** up — the magnitude at which two
decimals of `$MM` ($10,000 of resolution) is one percent of the figure. Below
it, exact dollars and cents: `$4,999`, `$4,999.60`, `$0`. Negatives lead with
the sign; `_fmt(-4_000)` printed `$-0.00MM` and now reads `-$4,000`. Tables may
mix the two units, which is the accepted cost of not printing a false figure.
The borrower snapshot's one-decimal form is gone with the rest. **Memos
generated by 0.2.0 or 0.2.1 for microenterprise or small-business deals contain
wrong figures; regenerate them.**

The gate that was supposed to catch this asserted `"$0.00MM"` for a supplied
zero — which is what a supplied $4,999 also produced — so the gate for the
ruling could not distinguish the property from its breach. It now measures three
renderings per field: absent, zero, and a small non-zero that must differ.

**An empty condition rendered as a bare number.** `conditions=["Real condition",
"", "   "]` printed `- ` twice in the Executive Summary and `2. ` / `3.    `
under Conditions of Approval — the package's own numbering over nothing, in the
section an IC reads as the terms of approval. The `""`-is-absence rule was
extended to the elements inside a `List[str]`, and to whitespace-only strings
everywhere, which also closes `mission="   "` rendering `### Mission` above a
blank line.

**The Deal Summary pointed at a section the memo did not contain.** With
`use_of_proceeds` unset, the row read `| Use of Proceeds | See Transaction
Structure |` while `### Use of Proceeds` appeared nowhere, because the heading
is gated on the same field. The row is omitted instead.

**The front matter's `or`-fallbacks disagreed with the rest of the package.**
`deal.fund_name or 'N/A'` and `deal.ic_date or 'TBD'` decided for themselves
what absence means; they agreed on `None` and `""` and disagreed on whitespace,
so `fund_name="   "` printed `**Fund:**` with nothing after it, three lines into
the memo. Both go through `fields.or_placeholder` now. Found by the gate written
for the empty-condition fix, named by nothing before it.

**`section_count()` was a fact about the memo's text, not its structure.** It
counted `"\n## "` in the rendered Markdown, and the memo reproduces caller prose
verbatim by design — so a `## ` line in `deal_summary`, a mission or an impact
narrative was counted as a section, and a seven-section memo reported eight. It
is the length of the renderer's own section tuple.

**The table-count gate carried one risk severity, so two tables were outside
it.** `_fully_populated_deal()` held a single `High` risk, so
`### Medium Risk Factors` and `### Low Risk Factors` were in neither
`DOCUMENTED_TABLES` nor the assertion — and the gate's
`len(doc.tables) == len(DOCUMENTED_TABLES)` would have *failed* on a deal with
all three, which is the ordinary case. Measured: twelve tables. README.md said
ten and now says twelve, and names the three severity tables separately.

**Two README claims that outran what the code does.** The Word-output section
said "nothing is added that has no line behind it"; `render`'s own docstring
correctly said "nothing *carrying text* is added", and the renderer appends a
spacer paragraph after every table. Measured on the quickstart deal: 6 tables,
13 empty paragraphs — 7 rules and 6 spacers. And the `""`-is-absence rule was
justified, in the README and in `fields.is_supplied`, by saying the fields that
hold an optional string "each render as a section heading with the string
beneath it". There are 16 such fields and that is true of six; it is not true of
`closing_date` and `maturity_date`, the two fields the rule was extended to. The
rule is right, the reason was not. Both now say what it is: an optional string is
rendered behind a label the package supplies, and a string that says nothing
leaves that label with nothing after it.

### Added

- `creditmemo/text.py` — the one rule for what is a Markdown emphasis marker and
  what is content, shared by the .docx paragraph path and the table-cell
  splitter, which had two different answers.
- `creditmemo/fields.py` — the one answer to "did the caller supply this?" and
  the one formatter for `interest_rate` and `term_years`, which two sections
  formatted separately and disagreed about.
- **G11, the input-fidelity gate** (`tests/test_input_fidelity.py`). It asserts
  that every free-text string a caller puts on a `DealProfile` appears, intact
  and as many times, in both renderings — comparing against the strings on the
  deal, never against a re-parse or re-normalisation of the generated Markdown.

  This exists because the .docx gates did the opposite. `tests/test_docx.py`
  normalised the Markdown with a `_MD_NUMBER = r"^\d+\.\s+(.*)$"` — character
  for character the renderer's own `_ORDERED_ITEM`, since removed — and with a
  `_strip_emphasis` that replicated the renderer's `.replace("*", "")`. They
  removed, on the Markdown side, exactly what the renderer destroyed on the Word
  side, so both G1 variants stayed green while content was being deleted.

  > **A gate that re-implements the transformation it is checking shares its
  > blind spot.** For a rendering-fidelity gate the only safe ground truth is
  > the string the caller supplied.

  Restoring either renderer defect reddens G11 — 7 tests for the ordered-item
  one, 26 for the asterisk one — and leaves every gate in `tests/test_docx.py`
  green. Those gates keep their job, which is duplication; they are no longer
  the fidelity gate, and their module now says so.
- **G9** — every `Optional` field: a supplied `0`/`0.0` renders as the value in
  every section that shows it, never as `N/A` and never as an omitted row. Its
  coverage check enumerates the schema, so a new `Optional` field cannot be
  added without a decision recorded against it.
- **G10** — `revenue_trend` returns a direction for every supplied pair
  including zeros, all three branches execute, and the property is checked not
  to divide by either endpoint.
- **G8 addendum** — each rendered flag negative is pinned to that flag's
  declared constant, and each constant to a literal in the test file, so the
  fourteen strings become a reviewed surface and any change to one shows as a
  diff. The gate's docstring states the residual limit in plain words: no gate
  can decide whether a declared negative actually negates its affirmative.
  `- ❌ No longer relevant: CDFI Certified` still passes. That class is
  narrowed, not closed.

### Removed

**`pandas` is no longer a runtime dependency.** 0.1.0 and 0.2.0 declared
`pandas>=1.4.0`, and no module in the package imports pandas or anything else
outside the standard library — so every install pulled pandas and numpy, and
inherited their platform and Python-version constraints, to build strings. Two
gates hold this: one checks every declared dependency is actually imported, the
other renders a full memo in a subprocess with third-party imports blocked. The
second used to block a hardcoded `("pandas", "numpy", "docx")` — so `import
pytest` in a shipped module passed both — and now derives the blocked set from
the distributions installed in that subprocess's own environment. That also
makes its red-proof reproducible here: the old one was "add `import pandas`",
and pandas is not installed, so it produced a conftest `ImportError` and zero
tests run rather than one failure. The first gate is vacuous by design with
`dependencies = []`, and now carries the would-pass-vacuously guard the rest of
the suite has.
`python-docx` remains, under the optional `[docx]` extra.

**`creditmemo.renderers.docx.header_rows_data` is gone**, with the hand-built
header table it constructed. It existed so the .docx gates could compare the
document against the renderer's own construction — which certifies consistency,
not truth. The metadata is now anchored against the `DealProfile` fields
instead.

### Known, not fixed in 0.2.1

- **`tribal` is not a `borrower_type`.** Tribal entities are a core CDFI and
  NMTC borrower class and `nonprofit` is a poor substitute. This is a feature.
- **The Historical Financial Summary maps `revenue_y1` to the column headed
  `Year -2`** — oldest-first — and nothing in the memo or the field names says
  so. The stated `Revenue Trend` conclusion depends on it. Documenting or
  renaming this is a breaking change to the input contract.
- **Prose beginning with `# `, `- `, `* ` or `1. ` is still restyled** as a
  heading, a bullet or a numbered item in the .docx. Each of those replaces a
  Markdown marker with the Word equivalent of the same marker, so the reader
  sees the structure the caller wrote; matching them exactly is not possible the
  way it is for a rule.

  An earlier version of this entry named only `# ` and `- ` and said "neither
  loses or relocates content". That was true of those two and **false of the
  third case it omitted**: a line beginning with any *other* number —
  `2019. The borrower refinanced its senior debt at 4.2%.` — matched the same
  ordered-item pattern, and the renderer emitted only the text after the number
  and let Word supply its own `1.`. A chronology written as 2019/2024 reached
  the Investment Committee as 1./2. That is the only defect in this class that
  both destroyed content and substituted a false value in its place, and it is
  **fixed**, not deferred -- twice over, and the second fix supersedes the
  first. The first was a rule that restyled a line into a Word `List Number`
  item only if it belonged to a contiguous run starting at 1 and incrementing by
  1. It protected the 2019/2024 chronology and left the ordinary case broken, in
  a way it could not protect against: Word renumbers any list it is given. So no
  line is restyled at all now. Ordered items are plain paragraphs carrying their
  own numbers, the whole class is closed rather than narrowed, and the cost is
  that a genuine ordered list loses its Word list styling. See **G13** above.

  A structured intermediate representation — building the .docx from the
  `DealProfile` rather than by re-parsing Markdown — would end the whole class.
  That is a redesign, not a patch.
- **Non-`Optional` counters still treat `0` as absent.** On `ImpactData`:
  `affordable_units`, `sq_ft_community_space`, `patients_served`,
  `students_served` and `businesses_supported`. On `LoanTerms`: `io_periods`
  (`int = 0`) and `origination_fee_pct` (`float = 0.0`), which the entry
  naming only `ImpactData` left out. None of them is `Optional`, so suppressing
  the row on `0` is defensible — the caller genuinely cannot say "I checked, and
  it is zero" — but the price is that they cannot distinguish a supplied zero
  from a default without the same `Optional` change made to the seven flags.
- **Four `NMTCTerms` inputs never reach the memo. This is the top item for
  0.3.0, and it is disclosed in README.md as well as here** — someone deciding
  whether to use this package for an NMTC deal should see it before they rely
  on it, not after.

  Measured, not counted by eye: each of the nine `NMTCTerms` inputs was
  perturbed one at a time and both renderings diffed. Substring searching gives
  false positives here — `0.0317` formatted to zero decimals is `0`, which
  occurs throughout the memo — so the diff is the instrument.

  | Input | Reaches Markdown | Reaches .docx |
  |-------|------------------|---------------|
  | `nmtc_allocation` | yes | yes |
  | `credit_price` | yes | yes |
  | `cde_fee_rate` | yes | yes |
  | `cde_name` | yes | yes |
  | `investor_name` | yes | yes |
  | `leverage_loan_rate` | **no** | **no** |
  | `qlici_a_rate` | **no** | **no** |
  | `qlici_b_rate` | **no** | **no** |
  | `compliance_years` | **no** | **no** |

  `leverage_loan_rate`, `qlici_a_rate` and `qlici_b_rate` are *required*
  positional arguments — a caller cannot construct `NMTCTerms` without
  supplying all three — and `compliance_years` defaults to 7. The NMTC
  Structure table shows the QEI, the credits, the credit price, the investor
  equity, the CDE fee and the net subsidy, and stops. For an NMTC deal the
  QLICI A and B rates and the seven-year compliance period are core structural
  terms, and this is the same class as everything above: caller-supplied input
  that vanishes, silently. Requiring an input is an implicit promise that it
  matters.

  It ships disclosed rather than fixed because adding rows changes the .docx
  table shape and belongs with the audit that covers it. An omission is at
  least visible to a reader in a way a false number is not — which is the
  distinction that sends the `ltv` scale out fixed and this one documented.
- **`FinancialData.ltv` and `LoanTerms.max_ltv` are still on opposite scales.**
  0.2.1 makes the ambiguity loud rather than silent (see *A fractional `ltv`
  now raises* above), but it does not unify them: `max_ltv` remains a fraction
  and `ltv` remains percentage points. A caller still has to hold two
  conventions in their head for two fields with almost the same name. Unifying
  them is a breaking change to the input contract — the same reason the
  `Year -2` mapping above is deferred — and is the second item for 0.3.0.
- **`max_ltv` is not validated in the other direction.** The refusal added in
  0.2.1 is on `FinancialData.ltv` only. A caller who makes the mirror-image
  mistake and passes `max_ltv=75.0`, meaning 75%, gets
  `Maximum LTV of 7500%` — measured. It is louder than a 0.8% LTV and far less
  likely to be believed, which is why it is disclosed rather than fixed here,
  but it is the same family and the scale unification closes both.
- **The `ltv` refusal cannot catch a fraction above par.** `ltv=1.15`, meant as
  a 115% LTV on an underwater loan, is outside the refused band and still
  renders as `1.2%`. Closing that needs the scale unification, not a wider
  band: widening it to cover 1.15 would start rejecting real low-LTV positions
  (a nearly repaid loan against appreciated collateral) with no way to express
  them. The residual requires both the fraction convention *and* an LTV over
  100%, in a memo whose benchmark line reads `<= 80%`.

## [0.2.0] — 2026-09-08

### Fixed

**Word (.docx) output dropped every table in the memo.**

In 0.1.0 the .docx renderer parsed the generated Markdown line by line and
explicitly discarded every table row:

    elif line.startswith("| ") and "|" in line[1:]:
        # Table row — skip (already rendered in markdown)
        pass

The justifying comment was wrong. "Already rendered in markdown" referred to
the Markdown *string being consumed to build the .docx* — nothing carried those
rows into the Word document.

Measured on the published 0.1.0 wheel with the README quickstart deal
("Southside Community Health Center"):

- the Markdown memo contained 42 table lines — 6 separator rules and
  **36 rows of content**
- the saved .docx contained **exactly 1 table with 4 rows**: the header block
  (Fund / Prepared By / Date / IC Date) that the renderer builds by hand from
  the `DealProfile`
- **all 36 content rows — 42 of 42 table lines — were dropped**, taking with
  them the Deal Summary, Proposed Terms, Historical Financial Summary, Key
  Credit Metrics, Financial Projections, Community Impact Metrics, Risk Factors
  and IC signature-block tables
- concretely absent from the Word file: the DSCR (`1.35x`), the interest rate
  (`4.50%`) and the impact figure (`8,500` patients served)
- the file **saved successfully and printed `Credit memo saved to {path}`**, so
  nothing signalled the loss. The failure was silent, and every 0.1.0 Word memo
  is affected.

Anyone who circulated a 0.1.0 .docx to an investment committee circulated a
memo with no financial-data, loan-terms or impact tables in it. The Markdown
output (`to_markdown()` / `save_markdown()`) was never affected.

0.2.0 renders each contiguous run of Markdown table lines as a real Word table
(`Table Grid` style, bold header row, separator rule dropped, bold markers
stripped from cells). The same deal now produces 7 tables and 40 rows.

**Table cells containing a literal `|` corrupted the row.** A pipe in an
underwriter-supplied string — a risk description, a use-of-proceeds line, a
borrower name — opened a new cell and shifted every value to its right into the
wrong column. Cell values are now escaped when the Markdown is generated and
unescaped when the .docx is built.

**The package installed a top-level `tests` package into site-packages.**
`find_packages()` in `setup.py` swept the test suite into the distribution, so
with credit-memo 0.1.0 installed, `import tests` in *any* project resolved to
this package's tests. Unlike the build-backend floor above, this one **did**
ship: the published 0.1.0 wheel contains a top-level `tests/` directory and
declares `top_level.txt = creditmemo\ntests`. Package discovery is now an explicit
`include = ["creditmemo*"]`, and CI fails the build if any top-level package
other than `creditmemo` appears in the wheel.

**Build backend floor raised to `setuptools>=61`.** 0.1.0 declared
`setuptools>=42` alongside a PEP 621 `[project]` table. setuptools below 61
cannot read `[project]`: it does not error, it builds a correctly named wheel
containing every module, but with `Summary: UNKNOWN`, `License: UNKNOWN` and
**no `Requires-Python`** — so pip would install it on an unsupported
interpreter. Measured against the 0.1.0 source with setuptools 59.6.0.

**No published artifact carries this defect.** `python -m build` resolves
`setuptools>=42` to a current setuptools under build isolation, so the 0.1.0
wheel on PyPI has `Metadata-Version: 2.4`, the real `Summary`, `License: MIT`
and `Requires-Python: >=3.9`. Nothing needs regenerating and nothing installed
from PyPI is affected. The wrong floor was a latent hazard for anyone building
0.1.0 from its sdist without build isolation, not a defect in what shipped.
Because `[build-system].requires` is baked into a release, the old floor stays
wrong in the 0.1.0 sdist forever; the fix takes effect from 0.2.0 onward.

**Three version strings, nothing keeping them in step.** 0.1.0 declared its
version in `pyproject.toml`, `setup.py` and `creditmemo/__init__.py`.
`setup.py` is now a shim that declares nothing, `pyproject.toml` is the single
source of truth, and a test asserts `creditmemo.__version__` matches it.

### Added

- `creditmemo/tables.py` — shared Markdown-table helpers: escaping, row
  splitting, block grouping (`iter_segments`, which the .docx renderer walks
  the whole memo with) and row extraction (`content_rows`, the one definition
  of what counts as a table row, used by the gates and by the installed-wheel
  smoke check). One rule, one place, both sides.
- Test suite grew from **29 tests (0.1.0) to 86 (0.2.0)**. The load-bearing
  .docx gate is positional — table for table, row for row, cell for cell,
  against the Markdown the same deal produces — because counting alone cannot
  tell a correct memo from one with every value in the wrong cell. The header
  table, which has no Markdown counterpart, is anchored to its documented label
  set and to the `DealProfile` fields its values come from. The `Table Grid`
  style and the bold header row the README promises are gated against the saved
  document, and against the README sentence itself.
- `.github/workflows/ci.yml` — the project had no CI at all. Runs the suite on
  Python 3.9–3.12; builds the sdist and wheel, checks their contents and
  metadata, then installs **that same wheel** into a clean environment and
  renders a deal with adversarial risk rows, failing if the tables did not
  survive. Action versions are pinned by commit SHA.
- `scripts/check_wheel.py` and `scripts/smoke_installed_wheel.py`, runnable
  locally as well as in CI. `check_wheel.py` also gates the sdist: without
  `MANIFEST.in` the tarball loses `tests/conftest.py`, `tests/__init__.py`,
  `scripts/` and the workflow, and its test suite cannot run.

### Known limitations

- The .docx renderer still works by parsing the Markdown it just generated
  rather than building from the `DealProfile` directly. Everything a memo needs
  survives that round trip today, but any Word-specific formatting (column
  widths, merged cells, number alignment) has nowhere to come from. Rebuilding
  the .docx path directly from the deal object is deferred to a later release.
- A free-text field (`use_of_proceeds`, `mission`, `impact_narrative`,
  `deal_summary`) whose own text contains a line beginning with `|` is rendered
  as a table in the .docx — and **the two outputs do not agree about it.** GFM
  requires a delimiter row under the header before it will read pipe lines as a
  table, so a lone pipe line inside a narrative stays a paragraph in Markdown:

      >>> markdown.markdown("Intro line.\n| smuggled | row |\nOutro line.\n",
      ...                   extensions=["tables"])
      '<p>Intro line.\n| smuggled | row |\nOutro line.</p>'

  while the .docx renderer groups any run of pipe-prefixed lines into a table
  and turns the same input into a one-row Word table. Pipes *are* escaped in
  every value the section generators interpolate into a table cell; they are
  not escaped inside multi-line narrative blocks, and that is where the two
  renderers part company. A memo whose narrative text contains pipe-prefixed
  lines will not look the same in Word as in Markdown.
- The `.docx` renderer treats the **second line** of a table block as the
  delimiter rule and nothing else, so a memo row made only of `-` and `:` is
  content and survives. The cost of that rule is the converse: a stray
  `|---|---|` in narrative text, with no header line above it, becomes a
  one-row Word table rather than being silently swallowed. Not guessing is the
  right failure mode here — `-` is the commonest not-applicable placeholder an
  underwriter types, and guessing dropped those rows.

## [0.1.0] — 2026-05-06

- Initial release: IC credit memo generation from structured deal inputs
  (borrower profile, loan terms, financial data, impact metrics, risk factors),
  with Markdown and Word output and NMTC deal support.
