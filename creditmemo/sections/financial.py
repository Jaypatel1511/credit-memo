"""Financial Analysis section generator."""
from typing import Optional

from creditmemo.data.schema import DealProfile, _reject_fractional_ltv
from creditmemo.money import money

#: How the Historical Financial Summary heads its three revenue columns, in
#: document order.
#:
#: **Read off the rendered table, not off the field names.** ``revenue_y1`` is
#: the *earliest* column and ``revenue_y3`` the latest — an ordering the
#: package's own records flagged as undocumented, and one a reader cannot
#: recover from a field called ``y1``. The sentence below names these column
#: headings rather than the attributes, so a reader checks the claim against
#: the row immediately above it. If the table's headings ever change, they
#: change here and in one place; gated by
#: ``test_g10b_the_sentence_names_the_columns_the_table_uses``.
REVENUE_FIRST_COLUMN = "Year -2"
REVENUE_MIDDLE_COLUMN = "Year -1"
REVENUE_LAST_COLUMN = "Most Recent"

#: The label for each outcome of the endpoint comparison, and the verb that
#: states it.
#:
#: Deliberately **not** ``Increasing`` / ``Decreasing`` / ``Stable``. Those
#: words describe a series, and nothing here computes anything about a series:
#: it compares two numbers and never reads ``revenue_y2``. Measured on the
#: published 0.2.1 wheel, ``revenue_y2`` at ``0``, ``1``, ``$50MM`` and
#: ``-$10MM`` all produced a byte-identical sentence, and
#:
#:     | Revenue | $1.00MM | $9.00MM | $1.10MM |
#:     **Revenue Trend:** Increasing — revenue has been increasing over the
#:     historical period.
#:
#: reported an 88% collapse in the most recent year as an increase, while
#:
#:     | Revenue | $3.00MM | $500,000 | $3.00MM |
#:     **Revenue Trend:** Stable — revenue has been stable over the historical
#:     period.
#:
#: told an Investment Committee that revenue down 83% and recovered had been
#: stable. ``Stable`` was the worst of the three, because equality of two
#: endpoints is not a volatility finding and the word claims one; the equality
#: label here says only that the two figures match.
#:
#: A real classifier — all supplied points plus a volatility term — is 0.3.0
#: work with its own methodology question. This release makes the sentence say
#: what the code computes, and nothing more.
ENDPOINT_HIGHER = ("Higher", "is higher than")
ENDPOINT_LOWER = ("Lower", "is lower than")
ENDPOINT_UNCHANGED = ("Unchanged", "equals")

#: The clause that closes every endpoint sentence. The middle column is named,
#: so a reader who can see a dip or a spike in it knows the sentence did not
#: look at it rather than concluding the sentence is wrong about it.
ENDPOINT_SCOPE_CLAUSE = (
    "This compares those two columns only; {middle} is not read."
)


def revenue_endpoint_line(f) -> Optional[str]:
    """
    The one sentence the memo states about revenue, or ``None``.

    **When it is stated.** Only when both ``revenue_y1`` and ``revenue_y3`` are
    supplied — the same condition 0.2.1 rendered under, unchanged. Measured on
    the published 0.2.1 wheel: ``revenue_y2`` alone, ``revenue_y2`` + ``y3``,
    and ``revenue_y1`` + ``y2`` each produced **no sentence at all**, and they
    still do. Widening the comparison to whichever two of the three are
    outermost would put a sentence in memos that have never carried one, which
    is a rendering change this release did not take; silence asserts nothing,
    so nothing about it can mislead.

    **What it claims.** That the *supplied* Most Recent figure is higher than,
    lower than, or equal to the *supplied* Year -2 figure. Both figures are
    quoted through :func:`creditmemo.money.money`, so the two dollar strings in
    the sentence are byte-identical to the two cells in the row above it and a
    reader can check the claim without leaving the page.

    **The one case where quoting the cells would make the sentence false.**
    Above the ``$MM`` crossover a real difference can be smaller than the
    rendered unit shows: ``revenue_y1=1_000_000, revenue_y3=1_004_999`` renders
    ``| Revenue | $1.00MM | N/A | $1.00MM |``, two identical cells, under a
    comparison whose sign is real. Naming them as different figures there would
    hand the reader a sentence they can disprove from the row above. That case
    gets its own wording, which states the direction, states that the row
    cannot show it, and quotes the single string both endpoints render as.
    Gated by ``test_g10b_a_sub_precision_difference_is_not_claimed_as_two``.
    """
    first, last = f.revenue_y1, f.revenue_y3
    if first is None or last is None:
        return None

    if last > first:
        label, relation = ENDPOINT_HIGHER
    elif last < first:
        label, relation = ENDPOINT_LOWER
    else:
        label, relation = ENDPOINT_UNCHANGED

    first_text, last_text = money(first), money(last)
    scope = ENDPOINT_SCOPE_CLAUSE.format(middle=REVENUE_MIDDLE_COLUMN)

    if first != last and first_text == last_text:
        body = (
            f"{REVENUE_LAST_COLUMN} revenue {relation} {REVENUE_FIRST_COLUMN} "
            f"revenue by less than the row above can show; both are written "
            f"{last_text}."
        )
    else:
        body = (
            f"{REVENUE_LAST_COLUMN} revenue of {last_text} {relation} "
            f"{REVENUE_FIRST_COLUMN} revenue of {first_text}."
        )

    return (
        f"**Revenue, {REVENUE_FIRST_COLUMN} vs {REVENUE_LAST_COLUMN}:** "
        f"{label} — {body} {scope}"
    )


def _fmt_ratio(val, suffix="x", decimals=2) -> str:
    """
    A multiple or a percentage, as the memo prints it.

    NOT fixed here, and reported rather than patched: this carries R24's
    property in the non-money half of the formatter surface. Two decimals mean
    ``_fmt_ratio(0.001)`` is ``0.00x`` — the same characters a stated DSCR of
    zero produces — and one decimal means ``_fmt_ratio(0.04, "%", 1)`` is
    ``0.0%``. ``creditmemo.fields.rate`` has it too. R24 ruled on dollar
    magnitudes; the formatter sweep that covers ratios and rates is 0.3.0, and
    doing it here would be an ungated change to numbers an IC reads.
    """
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}{suffix}"


def generate(deal: DealProfile) -> str:
    """
    Every optional figure below is tested with ``is not None``, never for
    truthiness. A supplied 0 — no cash on hand, no net income, a fully
    depreciated asset base — is one of the most material numbers an underwriter
    can report, and truthiness discarded it. ``FinancialData(cash=450_000)``
    used to render no Balance Sheet section at all, because ``cash`` was only
    consulted after three *other* fields had passed a truthiness test.
    """
    f = deal.financial_data

    # R20. `FinancialData.__post_init__` checks this too, and that check is the
    # better one: it fires at the caller's own line. It is not sufficient. A
    # dataclass is not frozen, so
    #
    #     f = FinancialData()
    #     f.ltv = 0.75            # read off a spreadsheet, field by field
    #
    # constructs without complaint and rendered `| Loan to Value | 0.8% |` —
    # R14's defect verbatim, by the route an incremental build takes. Freezing
    # the dataclass would close it and is a breaking change; validating where
    # the number is about to be rendered closes it here. The Word renderer is a
    # pure function of this Markdown, so one call covers both outputs.
    _reject_fractional_ltv(f.ltv)

    lines = [
        "## Financial Analysis",
        "",
        "### Historical Financial Summary",
        "",
        "| Metric | Year -2 | Year -1 | Most Recent |",
        "|--------|---------|---------|-------------|",
        f"| Revenue | {money(f.revenue_y1)} | {money(f.revenue_y2)} | {money(f.revenue_y3)} |",
        f"| Net Income | {money(f.net_income_y1)} | {money(f.net_income_y2)} | {money(f.net_income_y3)} |",
        f"| EBITDA | {money(f.ebitda_y1)} | {money(f.ebitda_y2)} | {money(f.ebitda_y3)} |",
        "",
    ]

    # Not `f.revenue_trend`. That property's words describe a series and it
    # computes a two-point comparison; 0.2.2 keeps the property for callers and
    # stops rendering its vocabulary. See `revenue_endpoint_line` above.
    endpoint_line = revenue_endpoint_line(f)
    if endpoint_line is not None:
        lines.append(endpoint_line)
        lines.append("")

    has_balance = any(v is not None for v in
                      (f.total_assets, f.total_liabilities,
                       f.net_assets_equity, f.cash))
    if has_balance:
        lines += [
            "### Balance Sheet Summary (Most Recent)",
            "",
            "| Item | Amount |",
            "|------|--------|",
        ]
        if f.total_assets is not None:
            lines.append(f"| Total Assets | {money(f.total_assets)} |")
        if f.total_liabilities is not None:
            lines.append(f"| Total Liabilities | {money(f.total_liabilities)} |")
        if f.net_assets_equity is not None:
            lines.append(f"| Net Assets / Equity | {money(f.net_assets_equity)} |")
        if f.cash is not None:
            lines.append(f"| Cash & Equivalents | {money(f.cash)} |")
        lines.append("")

    lines += [
        "### Key Credit Metrics",
        "",
        "| Metric | Value | Benchmark |",
        "|--------|-------|-----------|",
        f"| Debt Service Coverage Ratio | {_fmt_ratio(f.dscr)} | >= 1.25x |",
        f"| Current Ratio | {_fmt_ratio(f.current_ratio)} | >= 1.0x |",
        f"| Debt to Equity | {_fmt_ratio(f.debt_to_equity)} | < 3.0x |",
        f"| Loan to Value | {_fmt_ratio(f.ltv, suffix='%', decimals=1) if f.ltv is not None else 'N/A'} | <= 80% |",
        "",
    ]

    has_proj = any(v is not None for v in
                   (f.projected_revenue_y1, f.projected_dscr_y1,
                    f.projected_dscr_y2, f.projected_dscr_y3))
    if has_proj:
        lines += [
            "### Financial Projections",
            "",
            "| Metric | Year 1 | Year 2 | Year 3 |",
            "|--------|--------|--------|--------|",
        ]
        if f.projected_revenue_y1 is not None:
            lines.append(
                f"| Revenue | {money(f.projected_revenue_y1)} | — | — |"
            )
        # Any of the three years, not just Year 1. Gating all three on
        # `projected_dscr_y1` is the `has_balance`/`cash` defect of 0.2.0 in
        # the block next door: `FinancialData(projected_dscr_y2=1.42)`
        # rendered the heading and a header-only table, and the one figure
        # supplied appeared nowhere in the memo.
        if any(v is not None for v in (f.projected_dscr_y1,
                                       f.projected_dscr_y2,
                                       f.projected_dscr_y3)):
            lines.append(
                f"| DSCR | {_fmt_ratio(f.projected_dscr_y1)} | "
                f"{_fmt_ratio(f.projected_dscr_y2)} | "
                f"{_fmt_ratio(f.projected_dscr_y3)} |"
            )
        lines.append("")

    return "\n".join(lines)
