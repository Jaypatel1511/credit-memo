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
this package's tests. Package discovery is now an explicit
`include = ["creditmemo*"]`, and CI fails the build if any top-level package
other than `creditmemo` appears in the wheel.

**Build backend floor raised to `setuptools>=61`.** 0.1.0 declared
`setuptools>=42` alongside a PEP 621 `[project]` table. setuptools below 61
cannot read `[project]`: it does not error, it builds a wheel whose `Summary`,
`Home-page` and `License` are `UNKNOWN` and which carries **no
`Requires-Python`**, so pip would install it on unsupported interpreters. This
was measured against the 0.1.0 source with setuptools 59.6.0. Because
`[build-system].requires` is baked into a release, the old floor stays wrong in
0.1.0 forever; the fix takes effect from 0.2.0 onward.

**Three version strings, nothing keeping them in step.** 0.1.0 declared its
version in `pyproject.toml`, `setup.py` and `creditmemo/__init__.py`.
`setup.py` is now a shim that declares nothing, `pyproject.toml` is the single
source of truth, and a test asserts `creditmemo.__version__` matches it.

### Added

- `creditmemo/tables.py` — shared Markdown-table helpers (escaping, row
  splitting, separator detection, block grouping) used by both renderers, so
  the two sides cannot drift.
- Test suite grew from **29 tests (0.1.0) to 64 (0.2.0)**, including gates that
  count table rows and cells out of the actual Markdown string and the actual
  saved .docx and compare them, rather than asserting a written-down total.
- `.github/workflows/ci.yml` — the project had no CI at all. Runs the suite on
  Python 3.9–3.12, builds the wheel and checks its contents and metadata, then
  installs that wheel into a clean environment and renders the README deal,
  failing if the tables did not survive. Action versions are pinned by commit
  SHA.
- `scripts/check_wheel.py` and `scripts/smoke_installed_wheel.py`, runnable
  locally as well as in CI.

### Known limitations

- The .docx renderer still works by parsing the Markdown it just generated
  rather than building from the `DealProfile` directly. Everything a memo needs
  survives that round trip today, but any Word-specific formatting (column
  widths, merged cells, number alignment) has nowhere to come from. Rebuilding
  the .docx path directly from the deal object is deferred to a later release.
- A free-text field (`use_of_proceeds`, `mission`, `impact_narrative`,
  `deal_summary`) whose own text contains a line beginning with `|` is now
  rendered as a table in the .docx. Markdown does the same thing with such
  input, so the two outputs agree; neither escapes pipes inside multi-line
  narrative blocks.

## [0.1.0] — 2026-05-06

- Initial release: IC credit memo generation from structured deal inputs
  (borrower profile, loan terms, financial data, impact metrics, risk factors),
  with Markdown and Word output and NMTC deal support.
