"""Risk Assessment section generator."""
from creditmemo.data.schema import DealProfile, SEVERITIES
from creditmemo.tables import escape_cell

#: What the section says when ``deal.risks`` is empty.
#:
#: Through 0.2.0 this was an affirmative analytical finding — a sentence saying
#: the deal had been looked at and nothing of concern turned up — produced by
#: nothing more than an empty list. (The exact wording is quoted in CHANGELOG.md;
#: it is deliberately not repeated here, because tests/test_input_fidelity.py
#: forbids that shape of sentence anywhere in the shipped package.) The package
#: has no evidence for such a claim; the only thing it can speak to is what it
#: was handed. Stated as a fact about the inputs instead, because an Investment
#: Committee reading a generated memo cannot tell the two apart.
NO_RISKS_TEXT = (
    "**No risk factors were provided.** This section reflects the risk factors "
    "supplied with this deal; it is not an assessment that no material risks "
    "exist."
)


def generate(deal: DealProfile) -> str:
    lines = [
        "## Risk Assessment",
        "",
    ]

    if not deal.risks:
        lines += [NO_RISKS_TEXT, ""]
        return "\n".join(lines)

    # Group by severity. RiskFactor validates and title-cases severity on
    # construction, so an exact match here cannot silently drop a factor the
    # way it did before 0.2.1.
    for severity in SEVERITIES:
        risks = [r for r in deal.risks if r.severity == severity]
        if not risks:
            continue

        lines.append(f"### {severity} Risk Factors")
        lines.append("")
        lines.append("| Risk | Description | Mitigant |")
        lines.append("|------|-------------|----------|")

        for risk in risks:
            lines.append(
                f"| {escape_cell(risk.category)} | {escape_cell(risk.description)} "
                f"| {escape_cell(risk.mitigant)} |"
            )
        lines.append("")

    return "\n".join(lines)
