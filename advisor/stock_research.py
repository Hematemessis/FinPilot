from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import isfinite


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    name: str
    source_type: str
    published_at: date
    retrieved_at: date
    as_of: date
    location: str | None = None
    is_synthetic: bool = False


@dataclass(frozen=True)
class ResearchMetric:
    name: str
    display_value: str
    period: str
    source_id: str
    evidence_type: str


@dataclass(frozen=True)
class ValuationInputs:
    price: float
    currency: str
    eps_ttm: float | None
    eps_ntm: float | None
    eps_fy1: float | None
    peer_median_ntm_pe: float | None
    historical_median_ntm_pe: float | None
    estimate_revision_90d: float | None
    estimate_dispersion: float | None
    analyst_count: int
    price_as_of: date
    estimate_as_of: date
    price_source_id: str
    estimate_source_id: str
    earnings_basis: str = "摊薄、调整后每股收益"

    def __post_init__(self) -> None:
        if not isfinite(self.price) or self.price <= 0:
            raise ValueError("Price must be positive and finite")
        if self.analyst_count < 0:
            raise ValueError("Analyst count cannot be negative")
        if self.estimate_dispersion is not None and self.estimate_dispersion < 0:
            raise ValueError("Estimate dispersion cannot be negative")


@dataclass(frozen=True)
class ValuationAssessment:
    pe_ttm: float | None
    pe_ntm: float | None
    pe_fy1: float | None
    peer_discount: float | None
    historical_discount: float | None
    posture: str
    plain_summary: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CompanyResearchSnapshot:
    company_name: str
    ticker: str
    exchange: str
    business_summary: str
    earning_power: str
    latest_event: str
    primary_risk: str
    market_expectation: str
    variant_hypothesis: str
    first_rejection: str
    validation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    critical_flags: tuple[str, ...]
    metrics: tuple[ResearchMetric, ...]
    valuation: ValuationInputs
    sources: tuple[EvidenceSource, ...]
    is_synthetic: bool = False


@dataclass(frozen=True)
class CompanyResearchCard:
    company_name: str
    ticker: str
    exchange: str
    research_status: str
    status_reason: str
    evidence_confidence: str
    business_summary: str
    earning_power: str
    latest_event: str
    primary_risk: str
    market_expectation: str
    variant_hypothesis: str
    first_rejection: str
    validation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    metrics: tuple[ResearchMetric, ...]
    valuation: ValuationAssessment
    sources: tuple[EvidenceSource, ...]
    boundary_note: str


def calculate_pe(price: float, eps: float | None) -> float | None:
    """Return a meaningful P/E only when both price and earnings are valid."""

    if eps is None or not isfinite(eps) or eps <= 0:
        return None
    if not isfinite(price) or price <= 0:
        raise ValueError("Price must be positive and finite")
    return price / eps


def _relative_discount(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None or not isfinite(reference) or reference <= 0:
        return None
    return value / reference - 1


def assess_valuation(inputs: ValuationInputs) -> ValuationAssessment:
    pe_ttm = calculate_pe(inputs.price, inputs.eps_ttm)
    pe_ntm = calculate_pe(inputs.price, inputs.eps_ntm)
    pe_fy1 = calculate_pe(inputs.price, inputs.eps_fy1)
    peer_discount = _relative_discount(pe_ntm, inputs.peer_median_ntm_pe)
    historical_discount = _relative_discount(pe_ntm, inputs.historical_median_ntm_pe)

    warnings: list[str] = []
    if pe_ttm is None:
        warnings.append("过去一年利润为负或接近零，TTM 市盈率不适用。")
    if pe_ntm is None:
        warnings.append("缺少可用的未来 12 个月盈利预测，不能计算动态市盈率。")
    if inputs.analyst_count < 5:
        warnings.append("覆盖预测的分析师较少，动态估值可信度有限。")
    if inputs.estimate_revision_90d is not None and inputs.estimate_revision_90d <= -0.05:
        warnings.append("最近 90 天盈利预测明显下调，需要等待经营数据验证。")
    if inputs.estimate_dispersion is not None and inputs.estimate_dispersion >= 0.20:
        warnings.append("不同预测之间分歧较大，不应依赖单点动态市盈率。")
    if inputs.price_as_of - inputs.estimate_as_of > timedelta(days=45):
        warnings.append("盈利预测比价格数据陈旧超过 45 天，需要刷新后再比较。")

    if pe_ntm is None:
        posture = "动态估值数据不足"
        plain_summary = "目前只能看到过去利润，缺少可靠的未来盈利预测。"
    elif inputs.estimate_revision_90d is not None and inputs.estimate_revision_90d <= -0.05:
        posture = "估值看起来不贵，但等待盈利验证"
        plain_summary = (
            f"按市场预计的未来一年利润，当前价格约相当于 {pe_ntm:.1f} 年利润；"
            "但最近盈利预期正在下调，便宜度需要打折。"
        )
    elif peer_discount is not None and peer_discount >= 0.20:
        posture = "价格包含较多乐观预期"
        plain_summary = (
            f"按未来一年利润计算约为 {pe_ntm:.1f} 倍，比可比公司中位数高"
            f" {peer_discount:.0%}，需要更强的增长来支撑。"
        )
    else:
        posture = "估值可以继续研究"
        if peer_discount is None:
            plain_summary = f"按未来一年利润计算约为 {pe_ntm:.1f} 倍，但缺少可靠同行口径。"
        else:
            comparison = "低" if peer_discount < 0 else "高"
            plain_summary = (
                f"按未来一年利润计算约为 {pe_ntm:.1f} 倍，比可比公司中位数"
                f"{comparison} {abs(peer_discount):.0%}。"
            )

    return ValuationAssessment(
        pe_ttm=pe_ttm,
        pe_ntm=pe_ntm,
        pe_fy1=pe_fy1,
        peer_discount=peer_discount,
        historical_discount=historical_discount,
        posture=posture,
        plain_summary=plain_summary,
        warnings=tuple(warnings),
    )


class StockResearchAgent:
    """Build a research card while preserving source and recommendation boundaries."""

    def run(self, snapshot: CompanyResearchSnapshot) -> CompanyResearchCard:
        source_ids = {source.source_id for source in snapshot.sources}
        required_source_ids = {
            snapshot.valuation.price_source_id,
            snapshot.valuation.estimate_source_id,
            *(metric.source_id for metric in snapshot.metrics),
        }
        missing_source_ids = required_source_ids - source_ids
        valuation = assess_valuation(snapshot.valuation)

        if snapshot.critical_flags:
            status = "暂不考虑"
            status_reason = f"触发硬门槛：{snapshot.critical_flags[0]}"
        elif missing_source_ids:
            status = "数据不足"
            status_reason = "部分关键指标找不到对应来源，暂时不能形成可靠判断。"
        elif valuation.pe_ntm is None:
            status = "数据不足"
            status_reason = "缺少可解释的未来盈利预测，暂时无法判断动态估值。"
        elif (
            snapshot.valuation.estimate_revision_90d is not None
            and snapshot.valuation.estimate_revision_90d <= -0.05
        ):
            status = "等待业绩验证"
            status_reason = "估值表面上不贵，但近期盈利预测下调，需要新财报确认。"
        elif valuation.peer_discount is not None and valuation.peer_discount >= 0.20:
            status = "等待更好价格"
            status_reason = "当前价格相对可比公司包含较多乐观预期。"
        else:
            status = "值得继续研究"
            status_reason = "基础证据和估值口径完整，尚未触发明显否决条件。"

        if snapshot.is_synthetic:
            confidence = "流程演示"
            boundary = "公司和全部数据均为虚构离线样例，只用于展示调查流程，不对应真实证券。"
        elif missing_source_ids or snapshot.missing_evidence:
            confidence = "B"
            boundary = "仍有证据缺口，研究状态不是买卖建议。"
        else:
            confidence = "A"
            boundary = "研究卡用于信息整理，不构成个性化证券买卖建议。"

        gaps = list(snapshot.missing_evidence)
        if missing_source_ids:
            gaps.append(f"缺少来源记录：{', '.join(sorted(missing_source_ids))}")

        return CompanyResearchCard(
            company_name=snapshot.company_name,
            ticker=snapshot.ticker,
            exchange=snapshot.exchange,
            research_status=status,
            status_reason=status_reason,
            evidence_confidence=confidence,
            business_summary=snapshot.business_summary,
            earning_power=snapshot.earning_power,
            latest_event=snapshot.latest_event,
            primary_risk=snapshot.primary_risk,
            market_expectation=snapshot.market_expectation,
            variant_hypothesis=snapshot.variant_hypothesis,
            first_rejection=snapshot.first_rejection,
            validation_conditions=snapshot.validation_conditions,
            invalidation_conditions=snapshot.invalidation_conditions,
            missing_evidence=tuple(gaps),
            metrics=snapshot.metrics,
            valuation=valuation,
            sources=snapshot.sources,
            boundary_note=boundary,
        )


def make_demo_company_snapshot(market: str = "A股") -> CompanyResearchSnapshot:
    """Create a deterministic fictional A-share or HK-share research sample."""

    if market not in {"A股", "港股"}:
        raise ValueError("Market must be A股 or 港股")
    market_copy = {
        "A股": {
            "company_name": "华曜消费（虚构A股公司）",
            "ticker": "A-DEMO",
            "exchange": "A股离线演示股票池",
            "currency": "CNY",
            "price": 84.0,
            "eps_ttm": 3.5,
            "eps_ntm": 4.2,
            "eps_fy1": 4.0,
        },
        "港股": {
            "company_name": "云海互联（虚构港股公司）",
            "ticker": "H-DEMO",
            "exchange": "港股离线演示股票池",
            "currency": "HKD",
            "price": 126.0,
            "eps_ttm": 5.25,
            "eps_ntm": 6.3,
            "eps_fy1": 6.0,
        },
    }[market]

    sources = (
        EvidenceSource(
            source_id="demo_price",
            name=f"{market}离线演示行情",
            source_type="演示市场数据",
            published_at=date(2026, 1, 15),
            retrieved_at=date(2026, 1, 15),
            as_of=date(2026, 1, 15),
            is_synthetic=True,
        ),
        EvidenceSource(
            source_id="demo_filing",
            name=f"{market_copy['company_name']} 2025 年演示财报",
            source_type="虚构公司披露",
            published_at=date(2026, 1, 10),
            retrieved_at=date(2026, 1, 15),
            as_of=date(2025, 12, 31),
            is_synthetic=True,
        ),
        EvidenceSource(
            source_id="demo_estimates",
            name="离线一致预期样例",
            source_type="虚构市场预测",
            published_at=date(2026, 1, 15),
            retrieved_at=date(2026, 1, 15),
            as_of=date(2026, 1, 15),
            is_synthetic=True,
        ),
        EvidenceSource(
            source_id="demo_event",
            name="离线客户续费事件样例",
            source_type="虚构事件记录",
            published_at=date(2026, 1, 12),
            retrieved_at=date(2026, 1, 15),
            as_of=date(2026, 1, 12),
            is_synthetic=True,
        ),
    )
    metrics = (
        ResearchMetric("收入同比增长", "+18%", "2025 年", "demo_filing", "演示财报"),
        ResearchMetric("营业利润率", "21%", "2025 年", "demo_filing", "演示财报"),
        ResearchMetric("经营现金流/净利润", "1.12 倍", "2025 年", "demo_filing", "派生计算"),
        ResearchMetric("未来一年 EPS 预测变化", "-8%", "最近 90 天", "demo_estimates", "演示一致预期"),
    )
    valuation = ValuationInputs(
        price=market_copy["price"],
        currency=market_copy["currency"],
        eps_ttm=market_copy["eps_ttm"],
        eps_ntm=market_copy["eps_ntm"],
        eps_fy1=market_copy["eps_fy1"],
        peer_median_ntm_pe=22.5,
        historical_median_ntm_pe=24.0,
        estimate_revision_90d=-0.08,
        estimate_dispersion=0.12,
        analyst_count=12,
        price_as_of=date(2026, 1, 15),
        estimate_as_of=date(2026, 1, 15),
        price_source_id="demo_price",
        estimate_source_id="demo_estimates",
    )
    return CompanyResearchSnapshot(
        company_name=market_copy["company_name"],
        ticker=market_copy["ticker"],
        exchange=market_copy["exchange"],
        business_summary="向中小企业提供订阅制协作软件，主要收入来自持续付费，而不是一次性项目。",
        earning_power="演示财报显示收入增长 18%、营业利润率 21%，经营现金流能够覆盖账面利润。",
        latest_event="近期样例事件显示部分大客户延后续费，可能影响下一季度收入确认和续费率。",
        primary_risk="未来利润增长依赖续费率稳定和利润率继续改善；如果客户缩减软件支出，动态估值会迅速变贵。",
        market_expectation="未来 12 个月每股利润预计从 3.50 增至 4.20，但最近 90 天预测已下调 8%。",
        variant_hypothesis="如果续费率在下一次财报中稳定、现金回款没有恶化，市场可能低估订阅收入的韧性。",
        first_rejection="动态市盈率下降主要依赖尚未兑现的利润增长，而盈利预测正在下调。",
        validation_conditions=(
            "下一次财报显示续费率停止下降。",
            "经营现金流继续高于净利润。",
            "未来一年盈利预测不再连续下调。",
        ),
        invalidation_conditions=(
            "收入增速连续两个季度低于 10%。",
            "经营现金流/净利润降至 0.8 倍以下。",
            "未来一年盈利预测再次下调超过 10%。",
        ),
        missing_evidence=(
            "没有真实公司、真实财报、实时价格或真实分析师一致预期。",
            "尚未完成真实同行选择和行业口径验证。",
        ),
        critical_flags=(),
        metrics=metrics,
        valuation=valuation,
        sources=sources,
        is_synthetic=True,
    )
