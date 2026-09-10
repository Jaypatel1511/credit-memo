# credit-memo 📝

**Generate IC credit memos from structured deal inputs.**

Takes borrower profile, loan terms, financial data, impact metrics, and risk factors
as structured Python inputs and generates a formatted Investment Committee credit
memo in Markdown or Word (.docx) format.

---

## Why credit-memo?

Every CDFI analyst, IC committee, and private credit team writes credit memos from
scratch in Word. credit-memo standardizes the process — define your deal inputs once,
generate a professional IC memo instantly.

---

## Installation

    pip install credit-memo

    # For Word .docx output
    pip install credit-memo[docx]

credit-memo imports nothing outside the standard library. Only the optional
`[docx]` extra adds a dependency (`python-docx`).

---

## Quickstart

    from creditmemo import (
        CreditMemo, DealProfile, BorrowerProfile,
        LoanTerms, FinancialData, ImpactData, RiskFactor,
    )

    borrower = BorrowerProfile(
        name="Southside Community Health Center",
        borrower_type="nonprofit",
        sector="healthcare",
        state="IL",
        city="Chicago",
        year_founded=2005,
        ceo_name="Dr. Maria Johnson",
        mission="To provide quality healthcare to underserved communities.",
        is_cdfi_certified=False,
    )

    loan = LoanTerms(
        deal_type="loan",
        amount=2_500_000,
        interest_rate=0.045,
        term_years=10,
        amortization_years=20,
        io_periods=12,
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
        jobs_created=18, jobs_retained=32,
        patients_served=8500,
        is_low_income_area=True,
        is_nmtc_eligible=True,
        is_minority_borrower=True,
    )

    deal = DealProfile(
        deal_name="Southside Health Center — $2.5MM Term Loan",
        borrower=borrower,
        loan_terms=loan,
        financial_data=financials,
        impact_data=impact,
        recommendation="approve_conditions",
        prepared_by="Jay Patel",
        prepared_date="2026-05-06",
        fund_name="NCIF Community Lending Fund",
        conditions=[
            "Receipt of final appraisal satisfactory to lender",
            "Evidence of $500k matching funds from borrower",
        ],
    )

    memo = CreditMemo(deal)
    print(memo.to_markdown())
    memo.save_markdown("southside_health_memo.md")
    memo.save_docx("southside_health_memo.docx")   # requires pip install credit-memo[docx]

---

## Word (.docx) Output

`save_docx()` writes headings, paragraphs, bulleted lists, section rules and
**every table in the memo as a real Word table** — deal summary, proposed terms,
NMTC structure, historical financials, balance sheet summary, credit metrics,
projections, impact metrics, high risk factors, medium risk factors,
low risk factors and the IC signature block: twelve in a memo with all of them
populated.
Risk factors are one table per severity, so a memo carrying only `High` risks
renders ten. Tables use the built-in `Table Grid` style with a bold header row,
and the rules between sections are paragraph borders rather than rows of
underscores.

**Numbered lists keep their numbers as text.** Conditions of Approval and any
ordered list you write into a text field arrive as ordinary paragraphs whose
text still begins with `1.`, `2.`, `3.` — not as Word list items. This is
deliberate. Word does not restart a numbered list on its own, so styling them
made the Conditions of Approval in a memo that also had an ordered list earlier
print as **3, 4, 5**. A number in this memo is a value an underwriter wrote; the
package will lose a list's indentation before it will let Word choose a
different number. Unordered lists do use Word's `List Bullet` style, because a
bullet glyph says exactly what the `-` in the Markdown said.

`save_docx()` refuses text containing control characters — a vertical tab or
form feed, which is what a paste out of a PDF often leaves behind — and names
the character and the memo line in the error. They are not valid in a `.docx`
and nothing is silently stripped. `save_markdown()` accepts them.

The .docx is a pure function of the Markdown the same deal produces: every
heading, paragraph, list item, rule and table in the Word file comes from a line
of that Markdown, and **nothing carrying text** is added that has no line behind
it. Empty paragraphs are added: one after each table, as the spacer Word needs
to keep a table off the next heading, and one per section rule. On the quickstart
deal above that is 6 tables and 13 empty paragraphs — 7 rules and 6 spacers. The
qualifier used to be missing here and present in `render`'s own docstring, which
is the direction that matters least and reads worst. It does not apply column
widths, merged cells, number alignment, or a firm template.

> **credit-memo 0.2.0 and 0.1.0 printed the memo's front matter twice** in every
> Word file — the title, the deal name and the whole Fund / Prepared By / Date /
> IC Date block appeared once as a hand-built cover block and again from the
> Markdown, in a different shape. **0.1.0 additionally dropped every table.** If
> you generated Word memos with either release, regenerate them. See the
> [changelog](https://github.com/Jaypatel1511/credit-memo/blob/main/CHANGELOG.md).

---

## How Dollar Figures Are Written

A figure is written in the `$MM` unit only where that unit is precise enough to
describe it. Two decimals of `$MM` resolve to $10,000, so the crossover is
**$1,000,000** — the point where $10,000 is one percent of the figure. At or
above it you get `$2.50MM`; below it you get exact dollars and cents, `$4,999`
or `$4,999.60`, with the cents suppressed when they are zero. A supplied zero is
`$0`. Negative figures lead with the sign: `-$4,000`, `-$100.00MM`.

Below half a cent there is no honest cent figure to print, and rounding to `$0`
would put a non-zero figure behind the string a stated zero uses — the defect
this section exists to describe. So a sub-cent magnitude is written as a
**bound** rather than a value: `<$0.01`, or `>-$0.01` below zero. Each is a
true inequality about the number, and it keeps three things apart that would
otherwise read the same:

    | Net Income | $0 | <$0.01 | >-$0.01 |
    | Origination Fee | 0.00% (<$0.01) |

A stated zero, a positive sub-cent figure and a negative one are three
different strings. Those are all the forms a single figure takes: `$0`,
`<$0.01`, `>-$0.01`, the cents form, the `$MM` form, and `N/A` for a figure you
did not supply. The loan amount is the only place two of them appear together —
see below.

This also means one table can mix the two units — `| Revenue | $900,000 |`
above `| EBITDA | $1.10MM |`. That is deliberate. Through 0.2.0 the units were
kept consistent by dividing everything by a million at two decimals, which
meant **every figure below $5,000 printed as `$0.00MM`** — the same characters a
stated zero prints. A $4,999 cash balance and a zero cash balance reached the
Investment Committee as one string. The borrower snapshot was worse: one
decimal, so `total_assets=49_000` printed `$0.0MM`. If you generated memos for
microenterprise or small-business deals with 0.1.0 or 0.2.0, **the small figures
in them are wrong** — regenerate them. 0.2.1 is the release that fixes this.

The loan amount is the one figure written twice: `$2,500,000 ($2.50MM)`, or just
`$250,000` below the crossover, where the parenthesised form would only be a
coarser copy of the number beside it.

### Two known costs of writing figures in the unit that fits them

**A table can switch units inside the comparison it exists for.** Every cell
below is true, and the switch lands between the two figures a reader is meant
to compare:

    | Total Assets        | $999,999 |
    | Total Liabilities   | $1.00MM  |
    | Net Assets / Equity | -$1      |

    | Revenue | $999,999 | $1.00MM | $1.00MM |

The second is the same thing inside one metric's own time series. **The planned
direction for 0.3.0 is unit consistency within a table: if any figure in a
table falls below the crossover, the whole table renders in dollars.** The
dollars form is exact at every magnitude, so that buys consistency by rendering
the large figures more precisely — never by collapsing a small one, which is
what 0.2.0 did.

**A change smaller than the rendered unit's granularity is invisible in the
table and still visible to the revenue trend.** Above the crossover:

    revenue_y1=1_000_000, revenue_y3=1_004_999

    | Revenue | $1.00MM | N/A | $1.00MM |
    **Revenue Trend:** Increasing — revenue has been increasing over the
    historical period.

Both cells are honest roundings of their inputs, and the trend is computed on
the raw values you supplied, so nothing here is wrong — the table is coarser
than the comparison. This is inherent to rounding at any precision and is not
fixed by moving the crossover: at exact cents the same pair would be a fraction
of a cent apart. The trend is computed on raw values on purpose; computing it on
the rendered figures would make the memo's one analytical claim a function of
the formatter and would report "stable" for a real change.

---

## Memo Sections Generated

1. Executive Summary — deal overview, recommendation, key terms table
2. Borrower Profile — organization description, mission, certifications
3. Transaction Structure — loan terms, collateral, covenants, NMTC structure
4. Financial Analysis — historical financials, key ratios, projections
5. Impact Analysis — jobs, units, demographics, eligibility flags
6. Risk Assessment — risk factors by severity with mitigants
7. IC Recommendation — formal recommendation with conditions and signature block

---

## Stating What You Know, and What You Don't

The eligibility and certification flags are **three-state**:

| value | rendering |
|---|---|
| `True` | the affirmative line — `✅ Low-Income Area` |
| `False` | an explicit negative — `❌ Not a Low-Income Area` |
| `None` *(default)* | omitted entirely |

`is_cdfi_certified`, `is_mdi`, `is_low_income_area`, `is_nmtc_eligible`,
`is_opportunity_zone`, `is_minority_borrower` and `is_women_borrower` all work
this way. Passing `False` says "we checked, and the answer is no"; leaving the
field alone says nothing at all. Before 0.2.1 these were plain booleans
defaulting to `False`, so the two were the same value and both rendered as
silence.

The same principle applies to figures. Every `Optional` field is consulted with
`is not None` — never for truthiness — so a supplied `0` is rendered as the
number the caller stated: no cash on hand as `$0`, a 0% `interest_rate` — a
forgivable loan, an EQ2 note, a QLICI B tranche — as `0.00%`, and a revenue
collapse from $5MM to zero as `Revenue Trend: Decreasing` rather than as no
line at all. A field a caller never filled in is `None`, and only that renders
as `N/A`.

`NMTCTerms.qlici_b_rate` is *not* an example of this, and an earlier version of
this section used it as one. It is a required `float`, not an `Optional`, and it
reaches neither rendering at any value — see [the NMTC known
limitation](#known-limitation-four-nmtc-inputs-do-not-reach-the-memo). The
`0.00%` above is `LoanTerms.interest_rate`, which does render.

The one exception is `Optional[str]`, where the falsy value is the empty string
— and any string that is only whitespace, which states exactly as much. **An
empty string states nothing, so there is nothing of yours for the memo to
reproduce, and whatever it prints in its place is the package's own output
standing in for your content.**

There are 16 `Optional[str]` fields. For 15 of them what the package would
print is a label it supplies — a heading, a table row label, a bold prefix —
left standing with nothing after it: `| Anticipated Closing |  |`, or
`### Mission` above a blank line, or a numbered condition that is just `2.`.
Six render as a heading over a body (`description`, `mission`, `collateral`,
`guarantor`, `use_of_proceeds`, `impact_narrative`), five as a table row label
(`closing_date`, `maturity_date`, `cde_name`, `investor_name`, and
`use_of_proceeds` again, which is a Deal Summary row as well as a heading), and
five as an inline bold label (`ceo_name`, `website`, `census_tract`,
`fund_name`, `ic_date` — the last two render `N/A` and `TBD`, which is what an
absent value renders too).

The sixteenth is **`deal_summary`**, and it is the exception to the label: it is
reproduced as bare prose in the Executive Summary, with no heading, no row and
no prefix of its own. An earlier version of this section said an optional string
is *always* rendered behind a label, over a count of 16, and that sentence was
false for this field. There is no label to orphan here and an empty string costs
only a blank line; the field is inside the rule because the rule is uniform, and
uniformity is what is guaranteed: for all 16, `""` and `"   "` produce a memo
byte-identical to the one you get by leaving the field alone.

The same rule governs the elements inside `conditions`, so an empty condition is
dropped and the rest are renumbered.

And a deal with no `risks` says so as a fact about its inputs. It does not
claim the deal has no risks; the package has no way to know that.

---

## Risk Severities

`RiskFactor.severity` must be one of `High`, `Medium` or `Low`, matched
case-insensitively — `"high"`, `"HIGH"` and `"High"` are all accepted and
normalise to `High`. Anything else raises `ValueError`. All the validated string
fields (`borrower_type`, `sector`, `deal_type`, `recommendation`, `severity`)
behave this way.

---

## Deal Types Supported

- loan — Direct loan or line of credit
- nmtc — New Markets Tax Credit investment
- equity — Equity investment
- grant — Grant or forgivable loan
- guarantee — Loan guarantee

---

## NMTC Deals

    from creditmemo import NMTCTerms

    nmtc = NMTCTerms(
        nmtc_allocation=10_000_000,
        credit_price=0.83,
        leverage_loan_rate=0.045,
        qlici_a_rate=0.045,
        qlici_b_rate=0.010,
        cde_fee_rate=0.02,
        cde_name="Chicago Development Fund",
        investor_name="US Bancorp CDC",
    )

    deal = DealProfile(..., nmtc_terms=nmtc, ...)

All rates above are **fractions, not percentage points** — 4.5% is `0.045`. So
is `LoanTerms.max_ltv`. The one exception in the package is
`FinancialData.ltv`, which is in percentage points (a 75% LTV is `75.0`); it
raises if you pass it a fraction rather than render a false number. Unifying
the two scales is the second item for 0.3.0.

### Known limitation: four NMTC inputs do not reach the memo

**As of 0.2.1, `leverage_loan_rate`, `qlici_a_rate`, `qlici_b_rate` and
`compliance_years` appear nowhere in the generated memo** — not in the
Markdown, not in the Word document. The first three are *required* arguments:
you cannot construct `NMTCTerms` without supplying them, and the package then
discards them silently.

Measured by perturbing each field on `NMTCTerms` one at a time and diffing both
renderings. Of the nine inputs:

| Input | Reaches the memo? |
|-------|-------------------|
| `nmtc_allocation` | yes — *QEI (NMTC Allocation)*, and the three derived figures |
| `credit_price` | yes — *Credit Price*, and *Investor Equity* |
| `cde_fee_rate` | yes — *CDE Fee*, and *Estimated Net Subsidy* |
| `cde_name` | yes — *CDE* |
| `investor_name` | yes — *Tax Credit Investor* |
| `leverage_loan_rate` | **no** (required argument) |
| `qlici_a_rate` | **no** (required argument) |
| `qlici_b_rate` | **no** (required argument) |
| `compliance_years` | **no** (defaults to 7) |

For an NMTC deal the QLICI A and B rates and the seven-year compliance period
are core structural terms. **If you are using this package for an NMTC
transaction, add them to your memo by hand until this is fixed.** Adding rows
changes the .docx table shape and needs the gate coverage that goes with it,
which is why 0.2.1 discloses it rather than patching it. **This is the top item
for 0.3.0.**

---

## Known Limitations in 0.2.1

Four things this release does not do, disclosed here because you would
otherwise find them in a memo. Two more are in
[How Dollar Figures Are Written](#two-known-costs-of-writing-figures-in-the-unit-that-fits-them)
— one of which 0.3.0 removes and one of which is inherent to rounding and will
not be removed — and one is in
[NMTC Deals](#known-limitation-four-nmtc-inputs-do-not-reach-the-memo).

**Ratios, rates and the credit price still round a small non-zero to zero.**
0.2.1's rounding work covers dollar figures only. The other formatters were not
swept, and each renders a small supplied value as the characters a stated zero
produces:

| Field | Supplied | Renders |
|---|---|---|
| `dscr`, `current_ratio`, `debt_to_equity`, the three projected DSCRs | `0.001` | `0.00x` |
| `interest_rate` | `0.00001` | `0.00%` |
| `ltv` | `0.0001` | `0.0%` |
| `min_dscr_covenant` | `0.001` | `Minimum DSCR of 0.00x` |
| `max_ltv` | `0.0001` | `Maximum LTV of 0.0%` |
| `origination_fee_pct` | `0.00001` | `0.00%` |
| `cde_fee_rate` | `0.0001` | `0.0%` |
| `credit_price` | `0.001` | `$0.00/$1` |

The DSCR is the figure an IC reads first. Fixing this means changing numbers
across seven sites and needs the same gate coverage the money formatter got, so
0.2.1 discloses it. The one that bites on an ordinary deal rather than an
unusual input is `cde_fee_rate` at one decimal, which cannot tell 2.04% from
2.0%.

**Required strings are not checked, and `None` reaches the memo as the word
`None`.** The empty-string rule above governs the 16 `Optional[str]` fields.
`deal_name`, `prepared_by`, `prepared_date` and the required `BorrowerProfile`
strings are not optional, so the package takes them as given. With
`deal_name=None`, `prepared_date=None`, `prepared_by="   "` and
`borrower.name="  "` you get, with nothing raised:

    # None
    **Prepared By:**
    **Date:** None
    | Borrower |    |

`fund_name`, which is optional, correctly reads `N/A` three lines above. Until
0.3.0 decides between validating these at construction and giving them a
placeholder, supply them. Assembling a `DealProfile` field by field is the
route that hits this.

**Non-`Optional` counters still treat `0` as absent.** On `ImpactData`:
`affordable_units`, `sq_ft_community_space`, `patients_served`,
`students_served`, `businesses_supported`. On `LoanTerms`: `io_periods` and
`origination_fee_pct`. None of them is `Optional`, so the row is suppressed on
`0` and you cannot say "I checked, and it is zero" the way you can with the
seven tri-state flags.

**The Historical Financial Summary maps `revenue_y1` to the column headed
`Year -2`** — oldest first — and nothing in the memo or the field names says so.
The stated `Revenue Trend` depends on that mapping. Renaming the fields or the
columns is a breaking change to the input contract, so 0.2.1 documents it.

---

## Running Tests

    pip install -e ".[docx]" pytest
    pytest tests/ -v

The `.docx` gates skip if `python-docx` is not installed. Set
`CREDITMEMO_REQUIRE_DOCX=1` to make a missing `python-docx` an error instead —
CI does this so the gates can never pass by being skipped.

---

## Who This Is For

- CDFI analysts drafting IC memos for loan committee
- Private credit teams standardizing deal documentation
- CDEs preparing NMTC investment memos
- Impact investors documenting community development deals
- Anyone replacing manual Word memo templates with structured Python inputs

---

## License

MIT 2026 Jaypatel1511
