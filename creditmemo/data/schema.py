"""
Core dataclasses for credit memo inputs.
Covers CDFI loans, NMTC deals, equity investments, and grants.
"""
from dataclasses import dataclass, field
from typing import List, Optional


# ── Deal Types ────────────────────────────────────────────────────────────────
DEAL_TYPES = {
    "loan":     "Direct loan or line of credit",
    "nmtc":     "New Markets Tax Credit investment",
    "equity":   "Equity investment",
    "grant":    "Grant or forgivable loan",
    "guarantee": "Loan guarantee",
}

# ── Recommendation Options ────────────────────────────────────────────────────
RECOMMENDATIONS = {
    "approve":              "Approve as presented",
    "approve_conditions":   "Approve subject to conditions",
    "table":                "Table pending additional information",
    "decline":              "Decline",
}

# ── Borrower Types ────────────────────────────────────────────────────────────
BORROWER_TYPES = {
    "nonprofit":    "Nonprofit organization",
    "for_profit":   "For-profit business",
    "cdfi":         "Community Development Financial Institution",
    "government":   "Government entity",
    "cooperative":  "Cooperative",
    "individual":   "Individual borrower",
}

# ── Risk Severities ───────────────────────────────────────────────────────────
#: The severity levels the Risk Assessment section groups by. Declared here, and
#: validated on construction, for the same reason DEAL_TYPES and BORROWER_TYPES
#: are: a severity outside this vocabulary used to construct without complaint
#: and then vanish from the memo, because the renderer groups by exact match.
SEVERITIES = ("High", "Medium", "Low")

# ── Sectors ───────────────────────────────────────────────────────────────────
SECTORS = {
    "affordable_housing":   "Affordable Housing",
    "small_business":       "Small Business",
    "community_facility":   "Community Facility",
    "healthcare":           "Healthcare",
    "education":            "Education",
    "food_access":          "Food Access",
    "childcare":            "Childcare",
    "mixed_use":            "Mixed-Use Development",
    "microenterprise":      "Microenterprise",
    "other":                "Other",
}


#: The largest `FinancialData.ltv` that can only have been meant as a fraction.
#:
#: `LoanTerms.max_ltv` is a covenant cap written as a fraction, so the numbers a
#: caller might send to both fields are the fractions in [0.0, 1.0] — a cap
#: above 100% is not a credit control. `ltv` is rendered unscaled, so anything
#: in that band except zero reaches the memo as an LTV of one percent or less:
#: under a cent of debt per dollar of collateral. Nothing legitimate lives
#: there, so refusing the band costs no real input.
#:
#: F17: the band is where the *fraction reading* stops being the only coherent
#: one, and it is not a claim that 1.0% is the frontier of the absurd on the
#: rendered side. `ltv = 1.0000001` is above the band, is accepted, and renders
#: `1.0%` — the same reading the band exists to refuse. That is deliberate and
#: it is the direction to fail in: above 1.0 the two readings both produce
#: coherent numbers, and choosing between them would be the silent
#: interpretation this release exists to remove, so the value is rendered as
#: written. What the band buys is the range where no such choice exists.
LTV_FRACTION_BAND_MAX = 1.0


def _reject_fractional_ltv(value: Optional[float]) -> None:
    """
    Raise if ``ltv`` was supplied on the package's *other* scale.

    ``FinancialData.ltv`` is in percentage points and ``LoanTerms.max_ltv`` is a
    fraction, and through 0.2.1 neither said so. A caller who followed the
    dominant convention and passed ``0.75`` to both got ``Maximum LTV of 75%``
    beside ``| Loan to Value | 0.8% |`` in one memo — a 75% LTV reaching an
    Investment Committee as 0.8% against a ``<= 80%`` benchmark, in both the
    Markdown and the Word document.

    Unifying the scales is the right end state and a breaking change, so 0.2.1
    fails loudly instead. No interpretation is applied: ``<= 1.0 means a
    fraction`` would be a silent guess, and a 100% LTV is real. ``0.0`` is
    exempt because it is the one value the two conventions render identically,
    and R6 requires a supplied zero to reach the memo — the band below is open
    at the bottom (``0 < value``), which is that exemption, expressed once.

    R22: through 0.2.1 the exemption was *also* written as a ``value == 0``
    early return above the band. It could never fire, because the band already
    excluded zero, and the docstring described it as the thing keeping zero out.
    Measured both ways: with the clause and without it the suite is 340 passed,
    and the gate on zero passes either way. It was not producing the property.

    Called from two places, and both are load-bearing (R20). ``__post_init__``
    catches the mistake at construction, where the traceback points at the
    caller's own line. :func:`creditmemo.sections.financial.generate` catches it
    at the render boundary, where a ``FinancialData`` assembled field by field
    — the shape you get reading a spreadsheet row into an object — reaches the
    memo. Gated by G12.
    """
    if value is None:
        return
    if 0 < value <= LTV_FRACTION_BAND_MAX:
        raise ValueError(
            f"ltv must be in percentage points, not a fraction: got {value!r}, "
            f"which renders as {value:.1f}%. A {value*100:.0f}% LTV is "
            f"ltv={value*100:.1f}. (LoanTerms.max_ltv is the fraction; the two "
            f"fields are on opposite scales until they are unified in 0.3.0.)"
        )


def _normalise_choice(value, allowed, field_name: str) -> str:
    """
    Match ``value`` against ``allowed`` case-insensitively and return the
    canonical spelling, or raise ``ValueError`` naming the allowed values.

    Every string enum in this module goes through here. Before 0.2.1 the four
    validated fields compared with ``in`` against a dict of lowercase keys, so
    ``"Nonprofit"`` was rejected, while ``RiskFactor.severity`` was not
    validated at all and ``"high"`` was accepted by the constructor and then
    silently dropped by the renderer. Case-insensitive matching is strictly
    wider than the old exact match: nothing that was accepted before is
    rejected now.
    """
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be one of {list(allowed)}, got {value!r}"
        )
    for candidate in allowed:
        if value.strip().lower() == candidate.lower():
            return candidate
    raise ValueError(f"{field_name} must be one of {list(allowed)}")


@dataclass
class BorrowerProfile:
    """Borrower/organization information."""
    name: str
    borrower_type: str
    sector: str
    state: str
    city: str
    year_founded: Optional[int] = None
    ceo_name: Optional[str] = None
    total_assets: Optional[float] = None
    annual_revenue: Optional[float] = None
    description: Optional[str] = None
    mission: Optional[str] = None
    website: Optional[str] = None
    #: Tri-state. ``True`` renders the affirmative line, ``False`` renders an
    #: explicit negative, ``None`` (the default) renders nothing at all. Before
    #: 0.2.1 these were ``bool = False``, so a caller who had actually checked
    #: and recorded "no" was indistinguishable from one who never touched the
    #: field, and both rendered as silence.
    is_cdfi_certified: Optional[bool] = None
    is_mdi: Optional[bool] = None

    def __post_init__(self):
        self.borrower_type = _normalise_choice(
            self.borrower_type, BORROWER_TYPES, "borrower_type"
        )
        self.sector = _normalise_choice(self.sector, SECTORS, "sector")


@dataclass
class LoanTerms:
    """Loan or investment terms."""
    deal_type: str
    #: Dollars.
    amount: float
    #: A fraction, not percentage points: 4.5% is ``0.045``. Rendered ``*100``.
    interest_rate: Optional[float] = None
    term_years: Optional[int] = None
    amortization_years: Optional[int] = None
    io_periods: int = 0
    collateral: Optional[str] = None
    guarantor: Optional[str] = None
    use_of_proceeds: Optional[str] = None
    closing_date: Optional[str] = None
    maturity_date: Optional[str] = None
    #: A multiple, rendered as written: a 1.20x covenant is ``1.20``.
    min_dscr_covenant: Optional[float] = None
    #: A fraction, not percentage points: a 75% cap is ``0.75``. Rendered
    #: ``*100``. Note that ``FinancialData.ltv`` is on the *opposite* scale —
    #: see ``_reject_fractional_ltv``. Unifying them is 0.3.0 work.
    max_ltv: Optional[float] = None
    #: A fraction, not percentage points: a 1% fee is ``0.01``. Rendered
    #: ``*100``, and multiplied by ``amount`` for ``origination_fee``.
    origination_fee_pct: float = 0.0

    def __post_init__(self):
        self.deal_type = _normalise_choice(self.deal_type, DEAL_TYPES, "deal_type")
        if self.amount <= 0:
            raise ValueError("amount must be positive")

    @property
    def amount_mm(self) -> float:
        return self.amount / 1_000_000

    @property
    def origination_fee(self) -> float:
        return self.amount * self.origination_fee_pct


@dataclass
class FinancialData:
    """Key financial metrics for underwriting analysis."""
    # Income Statement
    revenue_y1: Optional[float] = None
    revenue_y2: Optional[float] = None
    revenue_y3: Optional[float] = None
    net_income_y1: Optional[float] = None
    net_income_y2: Optional[float] = None
    net_income_y3: Optional[float] = None
    ebitda_y1: Optional[float] = None
    ebitda_y2: Optional[float] = None
    ebitda_y3: Optional[float] = None

    # Balance Sheet
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    net_assets_equity: Optional[float] = None
    cash: Optional[float] = None

    # Key Ratios
    #: A multiple, rendered as written: 1.35x is ``1.35``.
    dscr: Optional[float] = None
    #: A multiple, rendered as written: 1.8x is ``1.8``.
    current_ratio: Optional[float] = None
    #: A multiple, rendered as written: 3.0x is ``3.0``.
    debt_to_equity: Optional[float] = None
    #: **Percentage points, not a fraction: a 75% LTV is ``75.0``.** This is
    #: the one field in the package on this scale — ``LoanTerms.max_ltv``,
    #: ``interest_rate``, ``cde_fee_rate`` and ``origination_fee_pct`` are all
    #: fractions. A value in ``(0, 1.0]`` raises rather than render a false
    #: number; see ``_reject_fractional_ltv``.
    ltv: Optional[float] = None

    # Projections
    projected_revenue_y1: Optional[float] = None
    #: A multiple, rendered as written — the same scale as ``dscr``.
    projected_dscr_y1: Optional[float] = None
    #: A multiple, rendered as written — the same scale as ``dscr``.
    projected_dscr_y2: Optional[float] = None
    #: A multiple, rendered as written — the same scale as ``dscr``.
    projected_dscr_y3: Optional[float] = None

    def __post_init__(self):
        _reject_fractional_ltv(self.ltv)

    @property
    def revenue_trend(self) -> Optional[str]:
        """
        The direction of revenue over the historical period, or ``None`` if
        either endpoint was not supplied.

        ``is not None``, not truthiness. Through 0.2.1 this was gated on
        ``if self.revenue_y1 and self.revenue_y3``, so revenue collapsing
        from $5MM to zero — the most alarming thing this field can express —
        was the one case the memo would not report, and a recovery from zero
        was the other. Both branches below are bare comparisons of the two
        endpoints; nothing divides by either, so no zero needs guarding for
        any reason but this one. Gated by G10.
        """
        if self.revenue_y1 is not None and self.revenue_y3 is not None:
            if self.revenue_y3 > self.revenue_y1:
                return "increasing"
            elif self.revenue_y3 < self.revenue_y1:
                return "decreasing"
            return "stable"
        return None


@dataclass
class NMTCTerms:
    """NMTC-specific deal terms (optional)."""
    #: Dollars.
    nmtc_allocation: float
    #: Dollars of investor equity per $1 of credit: $0.81 is ``0.81``.
    credit_price: float
    #: A fraction, not percentage points: 3.17% is ``0.0317``.
    #: Reaches neither rendering — see the 0.2.1 disclosure in CHANGELOG.md.
    leverage_loan_rate: float
    #: A fraction, not percentage points. Reaches neither rendering.
    qlici_a_rate: float
    #: A fraction, not percentage points. Reaches neither rendering.
    qlici_b_rate: float
    #: A fraction, not percentage points: a 6% fee is ``0.06``. Rendered
    #: ``*100``, and multiplied by ``nmtc_allocation`` for ``net_subsidy``.
    cde_fee_rate: float
    cde_name: Optional[str] = None
    investor_name: Optional[str] = None
    #: Whole years — the NMTC compliance period, 7 by statute.
    #: Reaches neither rendering — see the 0.2.1 disclosure in CHANGELOG.md.
    compliance_years: int = 7

    @property
    def total_nmtcs(self) -> float:
        return self.nmtc_allocation * 0.39

    @property
    def investor_equity(self) -> float:
        return self.total_nmtcs * self.credit_price

    @property
    def net_subsidy(self) -> float:
        return self.investor_equity - (self.nmtc_allocation * self.cde_fee_rate)


@dataclass
class ImpactData:
    """Social impact metrics for the deal."""
    jobs_created: int = 0
    jobs_retained: int = 0
    affordable_units: int = 0
    sq_ft_community_space: float = 0.0
    patients_served: int = 0
    students_served: int = 0
    businesses_supported: int = 0
    #: Tri-state, for the reason given on BorrowerProfile.is_cdfi_certified:
    #: ``True`` affirms, ``False`` denies, ``None`` (the default) is silent.
    is_low_income_area: Optional[bool] = None
    is_nmtc_eligible: Optional[bool] = None
    is_opportunity_zone: Optional[bool] = None
    is_minority_borrower: Optional[bool] = None
    is_women_borrower: Optional[bool] = None
    census_tract: Optional[str] = None
    impact_narrative: Optional[str] = None


@dataclass
class RiskFactor:
    """A single identified risk with its mitigant."""
    category: str       # e.g. "Credit", "Market", "Operational"
    description: str
    severity: str       # one of SEVERITIES, matched case-insensitively
    mitigant: str

    def __post_init__(self):
        self.severity = _normalise_choice(self.severity, SEVERITIES, "severity")


@dataclass
class DealProfile:
    """
    Master input object for credit memo generation.
    Combines all deal components into a single input contract.
    """
    deal_name: str
    borrower: BorrowerProfile
    loan_terms: LoanTerms
    financial_data: FinancialData
    impact_data: ImpactData
    recommendation: str
    prepared_by: str
    prepared_date: str
    nmtc_terms: Optional[NMTCTerms] = None
    #: The element type is stated, and it is load-bearing rather than
    #: decorative: G11's coverage guard classifies a list field by what it
    #: holds. A bare `list` is unclassified and reds there until someone
    #: decides whether its contents are caller-supplied text that has to
    #: survive into both renderings. See R19.
    risks: List[RiskFactor] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    fund_name: Optional[str] = None
    ic_date: Optional[str] = None
    deal_summary: Optional[str] = None

    def __post_init__(self):
        self.recommendation = _normalise_choice(
            self.recommendation, RECOMMENDATIONS, "recommendation"
        )

    @property
    def recommendation_text(self) -> str:
        return RECOMMENDATIONS[self.recommendation]
