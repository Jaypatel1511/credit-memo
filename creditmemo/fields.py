"""
Shared rendering rules for optional deal inputs.

Two questions live here, and both were previously answered separately in each
section that asked them.

**"Did the caller supply this?"** ``None`` means no. A supplied ``0``, ``0.0``
or ``False`` means yes, and is often the most material figure in the file: a 0%
``interest_rate`` on a forgivable loan or an EQ2 note, a zero cash balance, a
fully depreciated asset base, revenue that fell to zero. Testing those for
truthiness discards them and prints ``N/A``, which tells an Investment
Committee the figure is unknown when the caller stated it is zero.

This list used to name "a 0% QLICI B tranche" as well. That is not an example
of anything this module governs: ``NMTCTerms.qlici_b_rate`` is a required
``float``, so :func:`is_supplied` is never asked about it, and it reaches
neither rendering at any value — one of the four inputs the 0.2.1 CHANGELOG
discloses as discarded.

**"How does this field read?"** ``interest_rate`` was formatted by two separate
f-strings in two sections, which is how the Executive Summary came to say
``N/A`` for a rate the Transaction Structure printed. One field, one formatter.
"""
from typing import Optional

__all__ = ["NOT_SUPPLIED", "is_supplied", "supplied_items", "rate", "term",
           "or_not_supplied", "or_placeholder"]

#: What the memo prints in a row it must show for a value it was not given.
NOT_SUPPLIED = "N/A"


def is_supplied(value) -> bool:
    """
    True if the caller stated this field.

    ``None`` is absence. A supplied ``0``, ``0.0`` or ``False`` is a statement.

    The one exception is ``str``, where the falsy value is ``""`` — and, F11,
    any string that is only whitespace, which states exactly as much.

    **The reason, corrected — and the enumeration completed.** Both this
    docstring and README.md once justified the rule by saying the fields that
    hold an optional string "each render as a section heading with the string
    beneath it", so an empty one would put a heading over an empty body. R24's
    round replaced that with "an optional string is *always* rendered behind a
    label the package supplies". Neither is true of all of them, and the second
    was quantified over 16 fields while listing 15.

    There are 16 ``Optional[str]`` fields in the schema. Derived from the
    annotations and from what each one actually renders — not counted by eye:

    * a heading over a body (6): ``description`` (``### Organization
      Description``), ``mission``, ``collateral``, ``guarantor``,
      ``use_of_proceeds`` and ``impact_narrative``
    * a table row label (5, one of them a repeat): ``closing_date``
      (``| Anticipated Closing |``) and ``maturity_date``, the two fields R18
      moved; ``cde_name`` (``| CDE |``) and ``investor_name`` in the NMTC
      table; and ``use_of_proceeds`` again, which is *also* a Deal Summary row
    * an inline bold label (5): ``ceo_name``, ``website``, ``census_tract``,
      ``fund_name`` and ``ic_date`` — the last two through
      :func:`or_placeholder`, so ``""`` renders ``N/A``/``TBD`` exactly as
      ``None`` does rather than rendering nothing
    * **no label at all (1): ``deal_summary``.** It is reproduced as bare prose
      in the Executive Summary — ``lines += [deal.deal_summary, ""]``, no
      heading, no row, no prefix. This is the field the "always behind a label"
      sentence omitted, and the sentence is false for it.

    The reason that holds for all 16 is one step further back: an empty or
    whitespace-only string states nothing, so there is nothing of the caller's
    for the memo to reproduce, and whatever appears in its place is the
    package's own output presented as the caller's. For 15 of the 16 that is a
    label left standing with nothing after it —

        | Anticipated Closing |  |        <- R18, the Proposed Terms table
        ### Mission                       <- R4, a heading over an empty body
        - 2.                              <- F11, a numbered condition

    — which is the harm the rule was written for. For ``deal_summary`` there is
    no label to orphan and the cost of an empty string is only a blank line; it
    is inside the rule because the rule is uniform, and uniformity is the
    property gated: ``""`` and ``"   "`` must render byte-identically to
    ``None`` for every one of the 16, whatever shape that field takes.

    Gated by ``test_g9_the_optional_string_rule_is_stated`` (the predicate and
    the ``### Mission`` case), by
    ``test_g9_an_empty_optional_string_renders_as_absence`` for ``""`` and by
    ``test_g14b_whitespace_is_absence_for_an_optional_string_too`` for
    ``"   "``. The last two discover the 16 fields from the annotations rather
    than listing them, so a seventeenth is covered the moment it is declared —
    which is why the enumeration above is documentation and not the gate.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def supplied_items(values) -> list:
    """
    The elements of a caller-supplied ``List[str]`` that state something.

    F11. R18 moved ``closing_date``/``maturity_date`` onto :func:`is_supplied`
    so an empty string could not render ``| Anticipated Closing |  |``. The
    rule was never extended to the elements *inside* a list field, and
    ``conditions=["Real condition", "", "   "]`` rendered

        - Real condition                  <- Executive Summary
        -
        -
        1. Real condition                 <- Conditions of Approval
        2.
        3.

    An empty numbered condition in an IC memo is the same object as the empty
    table row: a label the package supplied with nothing behind it, and here
    the label is a number, which reads as a condition of approval that the
    reader's copy has lost. The surviving items are renumbered, because these
    numbers are generated by :mod:`creditmemo.sections.recommendation` and are
    not values an underwriter wrote — R17's rule governs the numbers a caller
    puts *inside* a string, and is untouched by this.

    Gated by ``test_g14b_an_empty_list_element_is_absence``.
    """
    return [v for v in values if is_supplied(v)]


def rate(value) -> Optional[str]:
    """An interest rate as the memo prints it, or ``None`` if not supplied."""
    return None if value is None else f"{value * 100:.2f}%"


def term(value) -> Optional[str]:
    """A number of years as the memo prints it, or ``None`` if not supplied."""
    return None if value is None else f"{value} years"


def or_not_supplied(text: Optional[str]) -> str:
    """``text``, or :data:`NOT_SUPPLIED` for a field the caller did not fill in."""
    return text if is_supplied(text) else NOT_SUPPLIED


def or_placeholder(text: Optional[str], placeholder: str) -> str:
    """
    ``text``, or ``placeholder`` for a field the caller did not fill in.

    F19 — found by G14b, named by no prior round. The memo's front matter and
    the Executive Summary wrote this as ``deal.fund_name or 'N/A'`` and
    ``deal.ic_date or 'TBD'``: an ``or``-fallback, deciding for itself what
    absence means instead of asking :func:`is_supplied`. It is the same
    mechanism as F10's ``lt.use_of_proceeds or 'See Transaction Structure'``,
    and it agreed with the rest of the package on ``None`` and ``""`` and
    disagreed on whitespace, so ``fund_name="   "`` printed

        **Fund:**

    — the package's own label with nothing after it, three lines into an IC
    memo. Gated by ``test_g14b_whitespace_is_absence_for_an_optional_string_too``.
    """
    return text if is_supplied(text) else placeholder
