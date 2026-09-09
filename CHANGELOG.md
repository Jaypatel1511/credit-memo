# Changelog

All notable changes to credit-memo are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.2.1] — 2026-09-08

Everything in this entry was measured on the code in this repository with the
README quickstart deal, on Python 3.12 with python-docx 1.2.0, and the suite was
re-run on 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14. The suite goes from **86 tests
to 143**. Every gate below was watched to fail against a deliberate mutation
before being trusted; the mutations are recorded in the gates' own docstrings.

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
/ 93 cells**, and 22 headings with none duplicated.

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

Every `Optional` figure in the Borrower Profile, Transaction Structure and
Financial Analysis sections is now tested with `is not None`.

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

**This is output-neutral for every existing caller who omits these fields**:
they move from `False`-rendered-as-nothing to `None`-rendered-as-nothing, and a
gate asserts that equivalence for all seven. It changes output **only** for a
caller who passed an explicit `False` — precisely the case that was silent
before, because `False` and "never touched" were the same value and the package
could not represent "we checked, and the answer is no".

A section whose flags are all `None` now says so rather than rendering a bare
heading with nothing under it. Through 0.2.0, `ImpactData()` produced
`### Target Market & Eligibility` followed immediately by the section rule.

**Conditions of Approval use Word's `List Number` style.** They were ordinary
paragraphs whose text began with a literal `"1. "`, so Word saw no list: no
renumbering, no indent, and the numbers were part of the sentence.

**Section rules are Word paragraph borders.** They were paragraphs containing
sixty literal underscores — selectable text that does not span the column, does
not follow the page margins, and lands in every copy-paste of the memo.

**One amount format.** The Deal Summary table showed `$2.50MM` where Proposed
Terms showed `$2,500,000 ($2.50MM)`. Both now show the full form.

### Removed

**`pandas` is no longer a runtime dependency.** 0.1.0 and 0.2.0 declared
`pandas>=1.4.0`, and no module in the package imports pandas or anything else
outside the standard library — so every install pulled pandas and numpy, and
inherited their platform and Python-version constraints, to build strings. Two
gates hold this: one checks every declared dependency is actually imported, the
other renders a full memo in a subprocess with third-party imports blocked.
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
- **Prose beginning with `# ` or `- ` is still restyled** as a heading or a
  bullet in the .docx. Unlike the `|` and `---` cases, neither loses or
  relocates content, and matching them exactly is not possible the way it is
  for a rule. A structured intermediate representation would end the whole
  class; that is not a patch.
- **Non-`Optional` counters still treat `0` as absent** — `affordable_units`,
  `patients_served` and the other `int = 0` fields on `ImpactData`. They cannot
  distinguish a supplied zero from a default without the same
  `Optional` change made to the seven flags.

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
