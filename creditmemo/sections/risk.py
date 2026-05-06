"""Risk Assessment section generator."""
from creditmemo.data.schema import DealProfile


def generate(deal: DealProfile) -> str:
    lines = [
        "## Risk Assessment",
        "",
    ]

    if not deal.risks:
        lines += [
            "No specific risks identified beyond standard credit considerations.",
            "",
        ]
        return "\n".join(lines)

    # Group by severity
    for severity in ["High", "Medium", "Low"]:
        risks = [r for r in deal.risks if r.severity == severity]
        if not risks:
            continue

        lines.append(f"### {severity} Risk Factors")
        lines.append("")
        lines.append("| Risk | Description | Mitigant |")
        lines.append("|------|-------------|----------|")

        for risk in risks:
            lines.append(
                f"| {risk.category} | {risk.description} | {risk.mitigant} |"
            )
        lines.append("")

    return "\n".join(lines)
