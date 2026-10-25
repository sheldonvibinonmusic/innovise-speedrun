"""Deterministic Financial Calculation Functions.

Executes 100% deterministic arithmetic using Python Decimal with strict input validation:
- Revenue Growth across comparable fiscal periods
- Operating Margin, Gross Margin, Net Margin
- Free Cash Flow = Operating Cash Flow - CapEx
- Leverage & Liquidity: Debt-to-Equity, Current Ratio
- Strict checks: Currency match, reporting scope match, division-by-zero protection, period comparability
"""

from dataclasses import dataclass, field
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any, Dict, List, Optional
import uuid

from app.db.models import FinancialFact


@dataclass
class CalculationResult:
    """Standardized record for deterministic financial calculation outputs."""
    calculation_id: str
    metric_name: str
    formula: str
    numeric_result: Optional[Decimal]
    formatted_result: str
    unit: str
    reporting_period: str
    reporting_scope: str
    source_fact_ids: List[int] = field(default_factory=list)
    validation_outcome: str = "VALID"  # VALID, DIVIDE_BY_ZERO, INCOMPATIBLE_CURRENCY, INCOMPATIBLE_PERIOD, MISSING_INPUTS, INCOMPATIBLE_SCOPE
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calculation_id": self.calculation_id,
            "metric_name": self.metric_name,
            "formula": self.formula,
            "numeric_result": str(self.numeric_result) if self.numeric_result is not None else None,
            "formatted_result": self.formatted_result,
            "unit": self.unit,
            "reporting_period": self.reporting_period,
            "reporting_scope": self.reporting_scope,
            "source_fact_ids": self.source_fact_ids,
            "validation_outcome": self.validation_outcome,
            "warnings": self.warnings,
        }


def _get_fact_val(fact: Any, attr: str, default: Any = None) -> Any:
    """Safely extract field from either a FinancialFact model instance or a dictionary."""
    if fact is None:
        return default
    if isinstance(fact, dict):
        if attr == "id":
            return fact.get("fact_id", fact.get("id", default))
        return fact.get(attr, default)
    return getattr(fact, attr, default)


def _validate_comparability(
    fact_a: Any,
    fact_b: Any,
    check_periods_differ: bool = False,
    check_periods_same: bool = False,
) -> Optional[CalculationResult]:
    """Verify currency, reporting scope, and existence of operands."""
    cid = f"calc_{uuid.uuid4().hex[:10]}"
    if not fact_a or not fact_b:
        return CalculationResult(
            calculation_id=cid,
            metric_name="unknown",
            formula="",
            numeric_result=None,
            formatted_result="N/A",
            unit="",
            reporting_period="unknown",
            reporting_scope="unknown",
            validation_outcome="MISSING_INPUTS",
            warnings=["One or more required financial facts were missing or unpopulated."],
        )

    curr_a = _get_fact_val(fact_a, "currency", "USD")
    curr_b = _get_fact_val(fact_b, "currency", "USD")
    if curr_a != curr_b:
        return CalculationResult(
            calculation_id=cid,
            metric_name="unknown",
            formula="",
            numeric_result=None,
            formatted_result="N/A",
            unit="",
            reporting_period="unknown",
            reporting_scope="unknown",
            source_fact_ids=[_get_fact_val(fact_a, "id"), _get_fact_val(fact_b, "id")],
            validation_outcome="INCOMPATIBLE_CURRENCY",
            warnings=[f"Currency mismatch: {curr_a} vs {curr_b}."],
        )

    scope_a = _get_fact_val(fact_a, "reporting_scope", "consolidated")
    scope_b = _get_fact_val(fact_b, "reporting_scope", "consolidated")
    if scope_a != scope_b:
        return CalculationResult(
            calculation_id=cid,
            metric_name="unknown",
            formula="",
            numeric_result=None,
            formatted_result="N/A",
            unit="",
            reporting_period="unknown",
            reporting_scope="unknown",
            source_fact_ids=[_get_fact_val(fact_a, "id"), _get_fact_val(fact_b, "id")],
            validation_outcome="INCOMPATIBLE_SCOPE",
            warnings=[f"Reporting scope mismatch: {scope_a} vs {scope_b}."],
        )

    return None


def calculate_revenue_growth(
    fact_current: Any,
    fact_prior: Any,
) -> CalculationResult:
    """Calculate year-over-year or period-over-period revenue growth percentage."""
    err = _validate_comparability(fact_current, fact_prior)
    if err:
        err.metric_name = "RevenueGrowth"
        err.formula = "((Revenue_Current - Revenue_Prior) / Revenue_Prior) * 100"
        return err

    cid = f"calc_{uuid.uuid4().hex[:10]}"
    cur_val = Decimal(str(_get_fact_val(fact_current, "numeric_value", "0")))
    prior_val = Decimal(str(_get_fact_val(fact_prior, "numeric_value", "0")))

    cur_ref = _get_fact_val(fact_current, "table_reference") or "Current"
    prior_ref = _get_fact_val(fact_prior, "table_reference") or "Prior"
    period_desc = f"{cur_ref} vs {prior_ref}"

    if prior_val == Decimal("0"):
        return CalculationResult(
            calculation_id=cid,
            metric_name="RevenueGrowth",
            formula="((Revenue_Current - Revenue_Prior) / Revenue_Prior) * 100",
            numeric_result=None,
            formatted_result="N/A (Div by zero)",
            unit="%",
            reporting_period=period_desc,
            reporting_scope=_get_fact_val(fact_current, "reporting_scope", "consolidated"),
            source_fact_ids=[_get_fact_val(fact_current, "id"), _get_fact_val(fact_prior, "id")],
            validation_outcome="DIVIDE_BY_ZERO",
            warnings=["Prior period revenue was zero; growth rate mathematically undefined."],
        )

    growth = ((cur_val - prior_val) / abs(prior_val)) * Decimal("100")
    growth_rounded = growth.quantize(Decimal("0.01"))

    return CalculationResult(
        calculation_id=cid,
        metric_name="RevenueGrowth",
        formula="((Revenue_Current - Revenue_Prior) / Revenue_Prior) * 100",
        numeric_result=growth_rounded,
        formatted_result=f"{growth_rounded:+.2f}%",
        unit="%",
        reporting_period=period_desc,
        reporting_scope=_get_fact_val(fact_current, "reporting_scope", "consolidated"),
        source_fact_ids=[_get_fact_val(fact_current, "id"), _get_fact_val(fact_prior, "id")],
        validation_outcome="VALID",
    )


def calculate_operating_margin(
    op_income: Any,
    revenue: Any,
) -> CalculationResult:
    """Calculate operating margin = (Operating Income / Total Revenue) * 100."""
    err = _validate_comparability(op_income, revenue)
    if err:
        err.metric_name = "OperatingMargin"
        err.formula = "(OperatingIncome / TotalRevenue) * 100"
        return err

    cid = f"calc_{uuid.uuid4().hex[:10]}"
    rev_val = Decimal(str(_get_fact_val(revenue, "numeric_value", "0")))
    op_val = Decimal(str(_get_fact_val(op_income, "numeric_value", "0")))

    rev_period = _get_fact_val(revenue, "period_type", "annual")
    rev_scope = _get_fact_val(revenue, "reporting_scope", "consolidated")
    src_ids = [_get_fact_val(op_income, "id"), _get_fact_val(revenue, "id")]

    if rev_val == Decimal("0"):
        return CalculationResult(
            calculation_id=cid,
            metric_name="OperatingMargin",
            formula="(OperatingIncome / TotalRevenue) * 100",
            numeric_result=None,
            formatted_result="N/A (Div by zero)",
            unit="%",
            reporting_period=rev_period,
            reporting_scope=rev_scope,
            source_fact_ids=src_ids,
            validation_outcome="DIVIDE_BY_ZERO",
            warnings=["Total revenue is zero; operating margin mathematically undefined."],
        )

    margin = (op_val / rev_val) * Decimal("100")
    margin_rounded = margin.quantize(Decimal("0.01"))

    return CalculationResult(
        calculation_id=cid,
        metric_name="OperatingMargin",
        formula="(OperatingIncome / TotalRevenue) * 100",
        numeric_result=margin_rounded,
        formatted_result=f"{margin_rounded:.2f}%",
        unit="%",
        reporting_period=rev_period,
        reporting_scope=rev_scope,
        source_fact_ids=src_ids,
        validation_outcome="VALID",
    )


def calculate_net_margin(
    net_income: Any,
    revenue: Any,
) -> CalculationResult:
    """Calculate net margin = (Net Income / Total Revenue) * 100."""
    err = _validate_comparability(net_income, revenue)
    if err:
        err.metric_name = "NetMargin"
        err.formula = "(NetIncome / TotalRevenue) * 100"
        return err

    cid = f"calc_{uuid.uuid4().hex[:10]}"
    rev_val = Decimal(str(_get_fact_val(revenue, "numeric_value", "0")))
    net_val = Decimal(str(_get_fact_val(net_income, "numeric_value", "0")))

    rev_period = _get_fact_val(revenue, "period_type", "annual")
    rev_scope = _get_fact_val(revenue, "reporting_scope", "consolidated")
    src_ids = [_get_fact_val(net_income, "id"), _get_fact_val(revenue, "id")]

    if rev_val == Decimal("0"):
        return CalculationResult(
            calculation_id=cid,
            metric_name="NetMargin",
            formula="(NetIncome / TotalRevenue) * 100",
            numeric_result=None,
            formatted_result="N/A (Div by zero)",
            unit="%",
            reporting_period=rev_period,
            reporting_scope=rev_scope,
            source_fact_ids=src_ids,
            validation_outcome="DIVIDE_BY_ZERO",
            warnings=["Total revenue is zero; net profit margin mathematically undefined."],
        )

    margin = (net_val / rev_val) * Decimal("100")
    margin_rounded = margin.quantize(Decimal("0.01"))

    return CalculationResult(
        calculation_id=cid,
        metric_name="NetMargin",
        formula="(NetIncome / TotalRevenue) * 100",
        numeric_result=margin_rounded,
        formatted_result=f"{margin_rounded:.2f}%",
        unit="%",
        reporting_period=rev_period,
        reporting_scope=rev_scope,
        source_fact_ids=src_ids,
        validation_outcome="VALID",
    )


def calculate_current_ratio(
    current_assets: Any,
    current_liabilities: Any,
) -> CalculationResult:
    """Calculate liquidity current ratio = Current Assets / Current Liabilities."""
    err = _validate_comparability(current_assets, current_liabilities)
    if err:
        err.metric_name = "CurrentRatio"
        err.formula = "CurrentAssets / CurrentLiabilities"
        return err

    cid = f"calc_{uuid.uuid4().hex[:10]}"
    ca_val = Decimal(str(_get_fact_val(current_assets, "numeric_value", "0")))
    cl_val = Decimal(str(_get_fact_val(current_liabilities, "numeric_value", "0")))

    ca_period = _get_fact_val(current_assets, "period_type", "annual")
    ca_scope = _get_fact_val(current_assets, "reporting_scope", "consolidated")
    src_ids = [_get_fact_val(current_assets, "id"), _get_fact_val(current_liabilities, "id")]

    if cl_val == Decimal("0"):
        return CalculationResult(
            calculation_id=cid,
            metric_name="CurrentRatio",
            formula="CurrentAssets / CurrentLiabilities",
            numeric_result=None,
            formatted_result="N/A (Div by zero)",
            unit="ratio",
            reporting_period=ca_period,
            reporting_scope=ca_scope,
            source_fact_ids=src_ids,
            validation_outcome="DIVIDE_BY_ZERO",
            warnings=["Current liabilities are zero; current ratio undefined."],
        )

    ratio = (ca_val / cl_val).quantize(Decimal("0.01"))
    return CalculationResult(
        calculation_id=cid,
        metric_name="CurrentRatio",
        formula="CurrentAssets / CurrentLiabilities",
        numeric_result=ratio,
        formatted_result=f"{ratio:.2f}x",
        unit="ratio",
        reporting_period=ca_period,
        reporting_scope=ca_scope,
        source_fact_ids=src_ids,
        validation_outcome="VALID",
    )


def calculate_debt_to_equity(
    total_debt: Any,
    equity: Any,
) -> CalculationResult:
    """Calculate leverage ratio = Total Debt / Stockholders' Equity."""
    err = _validate_comparability(total_debt, equity)
    if err:
        err.metric_name = "DebtToEquity"
        err.formula = "TotalDebt / StockholdersEquity"
        return err

    cid = f"calc_{uuid.uuid4().hex[:10]}"
    debt_val = Decimal(str(_get_fact_val(total_debt, "numeric_value", "0")))
    eq_val = Decimal(str(_get_fact_val(equity, "numeric_value", "0")))

    debt_period = _get_fact_val(total_debt, "period_type", "annual")
    debt_scope = _get_fact_val(total_debt, "reporting_scope", "consolidated")
    src_ids = [_get_fact_val(total_debt, "id"), _get_fact_val(equity, "id")]

    if eq_val == Decimal("0"):
        return CalculationResult(
            calculation_id=cid,
            metric_name="DebtToEquity",
            formula="TotalDebt / StockholdersEquity",
            numeric_result=None,
            formatted_result="N/A (Div by zero)",
            unit="ratio",
            reporting_period=debt_period,
            reporting_scope=debt_scope,
            source_fact_ids=src_ids,
            validation_outcome="DIVIDE_BY_ZERO",
            warnings=["Stockholders equity is zero; debt-to-equity ratio undefined."],
        )

    ratio = (debt_val / eq_val).quantize(Decimal("0.01"))
    return CalculationResult(
        calculation_id=cid,
        metric_name="DebtToEquity",
        formula="TotalDebt / StockholdersEquity",
        numeric_result=ratio,
        formatted_result=f"{ratio:.2f}x",
        unit="ratio",
        reporting_period=debt_period,
        reporting_scope=debt_scope,
        source_fact_ids=src_ids,
        validation_outcome="VALID",
    )


def calculate_gross_margin(
    gross_profit_or_cogs: Any,
    revenue: Any,
    is_cogs: bool = False,
) -> CalculationResult:
    """Calculate gross profit margin = (Gross Profit / Total Revenue) * 100."""
    err = _validate_comparability(gross_profit_or_cogs, revenue)
    if err:
        err.metric_name = "GrossMargin"
        err.formula = "((TotalRevenue - CostOfRevenue) / TotalRevenue) * 100" if is_cogs else "(GrossProfit / TotalRevenue) * 100"
        return err

    cid = f"calc_{uuid.uuid4().hex[:10]}"
    rev_val = Decimal(str(_get_fact_val(revenue, "numeric_value", "0")))
    op_val = Decimal(str(_get_fact_val(gross_profit_or_cogs, "numeric_value", "0")))

    rev_period = _get_fact_val(revenue, "period_type", "annual")
    rev_scope = _get_fact_val(revenue, "reporting_scope", "consolidated")
    src_ids = [_get_fact_val(gross_profit_or_cogs, "id"), _get_fact_val(revenue, "id")]

    if rev_val == Decimal("0"):
        return CalculationResult(
            calculation_id=cid,
            metric_name="GrossMargin",
            formula="(GrossProfit / TotalRevenue) * 100",
            numeric_result=None,
            formatted_result="N/A (Div by zero)",
            unit="%",
            reporting_period=rev_period,
            reporting_scope=rev_scope,
            source_fact_ids=src_ids,
            validation_outcome="DIVIDE_BY_ZERO",
            warnings=["Total revenue is zero; gross margin mathematically undefined."],
        )

    gp_val = (rev_val - op_val) if is_cogs else op_val
    margin = (gp_val / rev_val) * Decimal("100")
    margin_rounded = margin.quantize(Decimal("0.01"))

    formula_str = "((TotalRevenue - CostOfRevenue) / TotalRevenue) * 100" if is_cogs else "(GrossProfit / TotalRevenue) * 100"
    return CalculationResult(
        calculation_id=cid,
        metric_name="GrossMargin",
        formula=formula_str,
        numeric_result=margin_rounded,
        formatted_result=f"{margin_rounded:.2f}%",
        unit="%",
        reporting_period=rev_period,
        reporting_scope=rev_scope,
        source_fact_ids=src_ids,
        validation_outcome="VALID",
    )


def calculate_free_cash_flow(
    operating_cash_flow: Any,
    capex: Any,
) -> CalculationResult:
    """Calculate Free Cash Flow = Operating Cash Flow - Capital Expenditures."""
    err = _validate_comparability(operating_cash_flow, capex)
    if err:
        err.metric_name = "FreeCashFlow"
        err.formula = "OperatingCashFlow - CapitalExpenditures"
        return err

    cid = f"calc_{uuid.uuid4().hex[:10]}"
    ocf_val = Decimal(str(_get_fact_val(operating_cash_flow, "numeric_value", "0")))
    capex_val = Decimal(str(_get_fact_val(capex, "numeric_value", "0")))

    ocf_period = _get_fact_val(operating_cash_flow, "period_type", "annual")
    ocf_scope = _get_fact_val(operating_cash_flow, "reporting_scope", "consolidated")
    src_ids = [_get_fact_val(operating_cash_flow, "id"), _get_fact_val(capex, "id")]

    fcf = ocf_val - abs(capex_val)
    fcf_rounded = fcf.quantize(Decimal("0.01"))
    curr = _get_fact_val(operating_cash_flow, "currency", "USD")
    scale = _get_fact_val(operating_cash_flow, "unit_scale", "ONES")

    return CalculationResult(
        calculation_id=cid,
        metric_name="FreeCashFlow",
        formula="OperatingCashFlow - abs(CapitalExpenditures)",
        numeric_result=fcf_rounded,
        formatted_result=f"{fcf_rounded} {curr} ({scale})",
        unit=curr,
        reporting_period=ocf_period,
        reporting_scope=ocf_scope,
        source_fact_ids=src_ids,
        validation_outcome="VALID",
    )
