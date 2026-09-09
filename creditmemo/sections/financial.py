"""Financial Analysis section generator."""
from creditmemo.data.schema import DealProfile, _reject_fractional_ltv


def _fmt(val, prefix="$", suffix="", divisor=1e6, decimals=2) -> str:
    if val is None:
        return "N/A"
    return f"{prefix}{val/divisor:,.{decimals}f}{suffix}MM"


def _fmt_ratio(val, suffix="x", decimals=2) -> str:
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
        f"| Revenue | {_fmt(f.revenue_y1)} | {_fmt(f.revenue_y2)} | {_fmt(f.revenue_y3)} |",
        f"| Net Income | {_fmt(f.net_income_y1)} | {_fmt(f.net_income_y2)} | {_fmt(f.net_income_y3)} |",
        f"| EBITDA | {_fmt(f.ebitda_y1)} | {_fmt(f.ebitda_y2)} | {_fmt(f.ebitda_y3)} |",
        "",
    ]

    if f.revenue_trend is not None:
        lines.append(
            f"**Revenue Trend:** {f.revenue_trend.title()} — "
            f"revenue has been {f.revenue_trend} over the historical period."
        )
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
            lines.append(f"| Total Assets | {_fmt(f.total_assets)} |")
        if f.total_liabilities is not None:
            lines.append(f"| Total Liabilities | {_fmt(f.total_liabilities)} |")
        if f.net_assets_equity is not None:
            lines.append(f"| Net Assets / Equity | {_fmt(f.net_assets_equity)} |")
        if f.cash is not None:
            lines.append(f"| Cash & Equivalents | {_fmt(f.cash)} |")
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
                f"| Revenue | {_fmt(f.projected_revenue_y1)} | — | — |"
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
