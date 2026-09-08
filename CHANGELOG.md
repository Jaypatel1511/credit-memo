# Changelog

All notable changes to credit-memo are documented here.
This project follows [Semantic Versioning](https://semver.org/).

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
- Test suite grew from **29 tests (0.1.0) to 85 (0.2.0)**. The load-bearing
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
