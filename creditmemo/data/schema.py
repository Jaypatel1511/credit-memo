"""
Core dataclasses for credit memo inputs.
Covers CDFI loans, NMTC deals, equity investments, and grants.
"""
from dataclasses import dataclass, field
from typing import Optional


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
    amount: float
    interest_rate: Optional[float] = None
    term_years: Optional[int] = None
    amortization_years: Optional[int] = None
    io_periods: int = 0
    collateral: Optional[str] = None
    guarantor: Optional[str] = None
    use_of_proceeds: Optional[str] = None
    closing_date: Optional[str] = None
    maturity_date: Optional[str] = None
    min_dscr_covenant: Optional[float] = None
    max_ltv: Optional[float] = None
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
    dscr: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    ltv: Optional[float] = None

    # Projections
    projected_revenue_y1: Optional[float] = None
    projected_dscr_y1: Optional[float] = None
    projected_dscr_y2: Optional[float] = None
    projected_dscr_y3: Optional[float] = None

    @property
    def revenue_trend(self) -> Optional[str]:
        if self.revenue_y1 and self.revenue_y3:
            if self.revenue_y3 > self.revenue_y1:
                return "increasing"
            elif self.revenue_y3 < self.revenue_y1:
                return "decreasing"
            return "stable"
        return None


@dataclass
class NMTCTerms:
    """NMTC-specific deal terms (optional)."""
    nmtc_allocation: float
    credit_price: float
    leverage_loan_rate: float
    qlici_a_rate: float
    qlici_b_rate: float
    cde_fee_rate: float
    cde_name: Optional[str] = None
    investor_name: Optional[str] = None
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
    risks: list = field(default_factory=list)
    conditions: list = field(default_factory=list)
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
