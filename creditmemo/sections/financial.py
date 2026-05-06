"""Financial Analysis section generator."""
from creditmemo.data.schema import DealProfile


def _fmt(val, prefix="$", suffix="", divisor=1e6, decimals=2) -> str:
    if val is None:
        return "N/A"
    return f"{prefix}{val/divisor:,.{decimals}f}{suffix}MM"


def _fmt_ratio(val, suffix="x", decimals=2) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}{suffix}"


def generate(deal: DealProfile) -> str:
    f = deal.financial_data

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

    if f.revenue_trend:
        lines.append(
            f"**Revenue Trend:** {f.revenue_trend.title()} — "
            f"revenue has been {f.revenue_trend} over the historical period."
        )
        lines.append("")

    has_balance = any([f.total_assets, f.total_liabilities, f.net_assets_equity])
    if has_balance:
        lines += [
            "### Balance Sheet Summary (Most Recent)",
            "",
            "| Item | Amount |",
            "|------|--------|",
        ]
        if f.total_assets:
            lines.append(f"| Total Assets | {_fmt(f.total_assets)} |")
        if f.total_liabilities:
            lines.append(f"| Total Liabilities | {_fmt(f.total_liabilities)} |")
        if f.net_assets_equity:
            lines.append(f"| Net Assets / Equity | {_fmt(f.net_assets_equity)} |")
        if f.cash:
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
        f"| Loan to Value | {_fmt_ratio(f.ltv, suffix='%', decimals=1) if f.ltv else 'N/A'} | <= 80% |",
        "",
    ]

    has_proj = any([f.projected_revenue_y1, f.projected_dscr_y1])
    if has_proj:
        lines += [
            "### Financial Projections",
            "",
            "| Metric | Year 1 | Year 2 | Year 3 |",
            "|--------|--------|--------|--------|",
        ]
        if f.projected_revenue_y1:
            lines.append(
                f"| Revenue | {_fmt(f.projected_revenue_y1)} | — | — |"
            )
        if f.projected_dscr_y1:
            lines.append(
                f"| DSCR | {_fmt_ratio(f.projected_dscr_y1)} | "
                f"{_fmt_ratio(f.projected_dscr_y2)} | "
                f"{_fmt_ratio(f.projected_dscr_y3)} |"
            )
        lines.append("")

    return "\n".join(lines)
