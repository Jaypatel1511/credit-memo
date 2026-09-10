"""
The one place a dollar figure becomes text.

R24. Every money site used to format its own. ``sections/financial._fmt``
divided by ``1e6`` at two decimals; ``sections/borrower`` inlined the same
divide at *one*; ``sections/transaction`` inlined it four more times for the
NMTC block. Two decimals of the ``$MM`` unit resolve to $10,000, so every
figure below $5,000 rendered as ``$0.00MM`` — the same characters a *stated*
zero produces, which R6 requires the memo to show:

    supplied         0 -> | Cash & Equivalents | $0.00MM |
    supplied     4,999 -> | Cash & Equivalents | $0.00MM |

A $4,999 cash balance and a zero cash balance reached an Investment Committee
as one string, with nothing to tell the reader which one they were looking at.
``microenterprise`` is a declared ``SECTORS`` value and $5k-$50k is that
product's normal size. The borrower snapshot's one decimal resolved to $100,000
and lost ten times as much: ``total_assets=49_000`` rendered ``$0.0MM``. And the
memo contradicted itself in adjacent lines, because the revenue *trend* is
computed on the raw values and was right all along::

    | Revenue | $0.00MM | $0.00MM | $0.00MM |
    **Revenue Trend:** Increasing — revenue has been increasing ...

THE RULE. A figure is rendered in the ``$MM`` unit only where that unit's own
granularity is at most one percent of the figure. Two decimals of ``$MM`` is
$10,000, so the crossover is $1,000,000 exactly — :data:`MM_MIN` is derived,
not chosen by taste. Below it a figure is rendered in dollars and cents,
*exactly*, with the cents suppressed when they are zero. At and above it the
``$MM`` form is accurate to 0.5% or better.

Mixed units inside one table are the accepted cost of this: a memo may print

    | Revenue | $900,000 |
    | EBITDA  | $1.10MM  |

in adjacent rows. Both are true. The alternative — the one that shipped in
0.2.0 and 0.2.1 — kept the units consistent by making the small figure false.

NOTHING NON-ZERO RENDERS AS A STATED ZERO, AT ANY MAGNITUDE. Zero is the single
string :data:`ZERO`. Any magnitude at or above half a cent carries a non-zero
digit in the dollars-and-cents form; any magnitude at or above :data:`MM_MIN`
carries one in the ``$MM`` form. Below half a cent there is no honest cent
figure to print, so the magnitude is stated as a *bound* — ``<$0.01``, or
``>-$0.01`` below zero, each a true inequality about the value — rather than
rounded into the zero rendering. Gated by G14.

NEGATIVES. ``_fmt(-4_000)`` used to print ``$-0.00MM``: a minus sign wedged
between the currency symbol and a magnitude that had already been rounded away.
The sign now leads — ``-$4,000``, ``-$100.00MM``. The other accountancy
convention, ``($4,000)``, is not used here because parentheses already mean
something else in this package's money text: ``| Amount | $2,500,000 ($2.50MM)
|`` and ``| Origination Fee | 1.00% ($25,000) |`` both carry a parenthesised
figure that is not a negative.

WHAT IS NOT HERE. ``credit_price`` renders as ``$0.83/$1`` from
``sections/transaction``. It is dollars *per dollar of credit* — a price quoted
in the unit the NMTC market quotes it in, not a magnitude in a column of
magnitudes — so it does not go through this module. It has the same latent
property at two decimals (a credit price under half a cent would print
``$0.00/$1``); that is reported, not fixed here, because it belongs to the
formatter sweep 0.3.0 does.
"""
from creditmemo.fields import NOT_SUPPLIED

__all__ = ["MM_MIN", "ZERO", "SUB_CENT", "SUB_CENT_NEGATIVE",
           "dollars", "money", "money_with_mm"]

#: The magnitude at or above which the ``$MM`` unit is used.
#:
#: Two decimals of ``$MM`` resolve to $10,000, and $10,000 is one percent of
#: $1,000,000. Below this the unit is coarser than one percent of the figure it
#: describes, which is the weak form of the defect R24 closed: at $50,000 the
#: ``$MM`` form is ``$0.05MM``, plus or minus ten percent.
MM_MIN = 1_000_000.0

#: What a *stated* zero renders as — one string, in place of both units. R6
#: requires a supplied zero to reach the memo; this is what it says.
ZERO = "$0"

#: A positive magnitude below half a cent, stated as the true inequality
#: ``value < $0.01`` rather than rounded to :data:`ZERO`.
SUB_CENT = "<$0.01"

#: The same for a negative magnitude: the true inequality ``value > -$0.01``.
SUB_CENT_NEGATIVE = ">-$0.01"

#: Half of the smallest unit the cents form can express. Below this there is no
#: non-zero cent figure to print.
_HALF_CENT = 0.005


def dollars(value) -> str:
    """
    ``value`` in exact dollars and cents, whatever its magnitude.

    Cents are suppressed when they are zero, so $4,999.00 is ``$4,999`` and
    $4,999.60 is ``$4,999.60``. Used where the exact figure is the point and
    the ``$MM`` unit would only coarsen it: an origination fee, a cost per job,
    and the dollar half of :func:`money_with_mm`.
    """
    if value is None:
        return NOT_SUPPLIED
    if value == 0:
        return ZERO
    magnitude = abs(value)
    sign = "-" if value < 0 else ""
    if magnitude < _HALF_CENT:
        return SUB_CENT_NEGATIVE if value < 0 else SUB_CENT
    cents = f"{magnitude:,.2f}"
    if cents.endswith(".00"):
        cents = cents[:-3]
    return f"{sign}${cents}"


def money(value) -> str:
    """
    ``value`` as the memo prints a dollar figure, or ``N/A`` if not supplied.

    ``$MM`` at two decimals from :data:`MM_MIN` up, exact dollars and cents
    below it. See the module docstring for why the crossover is where it is.
    """
    if value is None:
        return NOT_SUPPLIED
    if value == 0:
        return ZERO
    magnitude = abs(value)
    if magnitude >= MM_MIN:
        sign = "-" if value < 0 else ""
        return f"{sign}${magnitude / MM_MIN:,.2f}MM"
    return dollars(value)


def money_with_mm(value) -> str:
    """
    Exact dollars, with the ``$MM`` form alongside where that form says
    something: ``$2,500,000 ($2.50MM)``, but ``$250,000`` on its own.

    The loan amount is the one figure the memo shows twice, in both units, in
    the Executive Summary and again in the Proposed Terms table. The
    parenthesised half is dropped below :data:`MM_MIN` because that is where it
    stops being a summary and starts being a worse copy of the number beside
    it — and, at the bottom of the range, a false one: ``LoanTerms.amount``
    only has to be positive, so a $4,999 microenterprise loan printed
    ``| Amount | $4,999 ($0.00MM) |``, the true figure and the zero string in
    one cell.
    """
    if value is None:
        return NOT_SUPPLIED
    exact = dollars(value)
    if value == 0 or abs(value) < MM_MIN:
        return exact
    return f"{exact} ({money(value)})"
