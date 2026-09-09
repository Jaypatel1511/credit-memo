"""
Shared rendering rules for optional deal inputs.

Two questions live here, and both were previously answered separately in each
section that asked them.

**"Did the caller supply this?"** ``None`` means no. A supplied ``0``, ``0.0``
or ``False`` means yes, and is often the most material figure in the file: a 0%
forgivable loan, an EQ2 note, a 0% QLICI B tranche, a zero cash balance, a
fully depreciated asset base. Testing those for truthiness discards them and
prints ``N/A``, which tells an Investment Committee the figure is unknown when
the caller stated it is zero.

**"How does this field read?"** ``interest_rate`` was formatted by two separate
f-strings in two sections, which is how the Executive Summary came to say
``N/A`` for a rate the Transaction Structure printed. One field, one formatter.
"""
from typing import Optional

__all__ = ["NOT_SUPPLIED", "is_supplied", "rate", "term", "or_not_supplied"]

#: What the memo prints in a row it must show for a value it was not given.
NOT_SUPPLIED = "N/A"


def is_supplied(value) -> bool:
    """
    True if the caller stated this field.

    ``None`` is absence. A supplied ``0``, ``0.0`` or ``False`` is a statement.

    The one exception is ``str``, where the falsy value is ``""``. An empty
    string is not a figure a caller stated, and the fields that hold one — a
    mission, a collateral description, an impact narrative — each render as a
    section heading with the string beneath it, so treating ``""`` as supplied
    would put a heading over an empty body. That is the defect the tri-state
    flag blocks closed in 0.2.1, and it is not worth reopening to represent a
    value that says nothing. Gated by ``test_g9_the_optional_string_rule_is_stated``.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    return True


def rate(value) -> Optional[str]:
    """An interest rate as the memo prints it, or ``None`` if not supplied."""
    return None if value is None else f"{value * 100:.2f}%"


def term(value) -> Optional[str]:
    """A number of years as the memo prints it, or ``None`` if not supplied."""
    return None if value is None else f"{value} years"


def or_not_supplied(text: Optional[str]) -> str:
    """``text``, or :data:`NOT_SUPPLIED` for a field the caller did not fill in."""
    return NOT_SUPPLIED if text is None else text
