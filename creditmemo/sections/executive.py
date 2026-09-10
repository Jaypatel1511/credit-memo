"""Executive Summary section generator."""
from creditmemo import fields
from creditmemo.data.schema import DealProfile, DEAL_TYPES, SECTORS
from creditmemo.money import money_with_mm
from creditmemo.tables import escape_cell


def generate(deal: DealProfile) -> str:
    b = deal.borrower
    lt = deal.loan_terms
    # `creditmemo.fields`, not a local f-string and not a truthiness test.
    # Both fields are Optional, so a supplied 0 is a value the caller stated;
    # and both are also shown by the Transaction Structure section, which
    # formatted them separately and therefore printed "0 years" for a term
    # this section called "N/A" on the same deal.
    rate_str = fields.or_not_supplied(fields.rate(lt.interest_rate))
    term_str = fields.or_not_supplied(fields.term(lt.term_years))

    lines = [
        "## Executive Summary",
        "",
        f"**Deal Name:** {deal.deal_name}",
        f"**Prepared By:** {deal.prepared_by}",
        f"**Date:** {deal.prepared_date}",
        f"**IC Date:** {fields.or_placeholder(deal.ic_date, 'TBD')}",
        "",
        "### Recommendation",
        "",
        f"**{deal.recommendation_text.upper()}**",
        "",
    ]

    conditions = fields.supplied_items(deal.conditions)
    if conditions:
        lines.append("**Subject to the following conditions:**")
        for cond in conditions:
            lines.append(f"- {cond}")
        lines.append("")

    lines += [
        "### Deal Summary",
        "",
        f"| Item | Details |",
        f"|------|---------|",
        f"| Borrower | {escape_cell(b.name)} |",
        f"| Borrower Type | {escape_cell(b.borrower_type.replace('_', ' ').title())} |",
        f"| Sector | {escape_cell(SECTORS.get(b.sector, b.sector))} |",
        f"| Location | {escape_cell(b.city)}, {escape_cell(b.state)} |",
        f"| Deal Type | {escape_cell(DEAL_TYPES.get(lt.deal_type, lt.deal_type))} |",
        f"| Amount | {money_with_mm(lt.amount)} |",
        f"| Interest Rate | {rate_str} |",
        f"| Term | {term_str} |",
    ]

    # F10. This row was `lt.use_of_proceeds or 'See Transaction Structure'`, so
    # an unsupplied field printed `| Use of Proceeds | See Transaction
    # Structure |` while `### Use of Proceeds` — the section that fallback
    # names — appeared nowhere in the memo, because sections/transaction.py
    # gates that heading on the same field. The memo pointed an Investment
    # Committee at a section it did not contain.
    #
    # The row is omitted instead, which is R18's ruling applied where R18 was
    # not looking: a label with no value behind it does not go in the table.
    # `fields.is_supplied`, so `""` is absence here exactly as it is at the
    # heading, and the row and the section appear and disappear together.
    if fields.is_supplied(lt.use_of_proceeds):
        lines.append(f"| Use of Proceeds | {escape_cell(lt.use_of_proceeds)} |")
    lines.append("")

    if fields.is_supplied(deal.deal_summary):
        lines += [deal.deal_summary, ""]

    return "\n".join(lines)
