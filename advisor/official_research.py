from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = PROJECT_ROOT / "data" / "evidence"


@dataclass(frozen=True)
class OfficialFact:
    label: str
    value: str
    change: str
    meaning: str
    source_id: str
    source_location: str


@dataclass(frozen=True)
class OfficialSource:
    source_id: str
    name: str
    as_of_date: str
    location: str
    notes: str


@dataclass(frozen=True)
class OfficialCompanyResearch:
    ticker: str
    company_name: str
    market: str
    business_summary: str
    research_status: str
    status_reason: str
    suggested_action: str
    core_question: str
    verified_view: tuple[str, ...]
    primary_risks: tuple[str, ...]
    validation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    facts: tuple[OfficialFact, ...]
    sources: tuple[OfficialSource, ...]
    valuation_status: str
    valuation_reason: str
    data_as_of: str
    audit_readiness: str
    boundary_note: str


@lru_cache(maxsize=1)
def load_evidence_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_index = pd.read_csv(EVIDENCE_ROOT / "Source_Index.csv")
    financials = pd.read_csv(EVIDENCE_ROOT / "Normalized_Financials_Long.csv")
    qa_flags = pd.read_csv(EVIDENCE_ROOT / "QA_Flags.csv")
    checks = pd.read_csv(EVIDENCE_ROOT / "Validation_Checks.csv")

    known_source_ids = set(source_index["source_id"])
    missing_ids = set(financials["source_id"]) - known_source_ids
    if missing_ids:
        raise ValueError(f"归一化财务数据存在未登记来源：{sorted(missing_ids)}")
    if financials[["period_end", "currency", "units"]].isna().any().any():
        raise ValueError("归一化财务数据缺少报告期、币种或单位")
    return source_index, financials, qa_flags, checks


def _row(entity: str, source_id: str, line_item_id: str) -> pd.Series:
    _, financials, _, _ = load_evidence_tables()
    matched = financials[
        (financials["entity"] == entity)
        & (financials["source_id"] == source_id)
        & (financials["line_item_id"] == line_item_id)
    ]
    if len(matched) != 1:
        raise ValueError(
            f"财务指标定位失败：{entity} {source_id} {line_item_id}，匹配 {len(matched)} 行"
        )
    return matched.iloc[0]


def _cny_yi(row: pd.Series, digits: int = 1) -> str:
    return f"{float(row['normalized_value']) / 100:,.{digits}f} 亿元"


def _eps(row: pd.Series) -> str:
    return f"{float(row['normalized_value']):.3f} 元/股".replace(".000", "")


def _sources(source_ids: tuple[str, ...]) -> tuple[OfficialSource, ...]:
    source_index, _, _, _ = load_evidence_tables()
    rows = source_index.set_index("source_id").loc[list(source_ids)]
    return tuple(
        OfficialSource(
            source_id=source_id,
            name=str(row["source_name"]),
            as_of_date=str(row["as_of_date"]),
            location=str(row["file_tab_page_url_or_location"]),
            notes=str(row["notes"]),
        )
        for source_id, row in rows.iterrows()
    )


def _moutai_research() -> OfficialCompanyResearch:
    revenue = _row("贵州茅台", "SRC-MT-H1-2026", "revenue")
    profit = _row("贵州茅台", "SRC-MT-H1-2026", "net_income_attributable")
    cash_flow = _row("贵州茅台", "SRC-MT-H1-2026", "operating_cash_flow")
    eps = _row("贵州茅台", "SRC-MT-H1-2026", "basic_eps")

    return OfficialCompanyResearch(
        ticker="600519",
        company_name="贵州茅台",
        market="A股",
        business_summary=(
            "核心收入来自茅台酒和系列酒，销售通过直销与批发代理完成。品牌、产能、渠道和终端需求共同决定增长质量。"
        ),
        research_status="等待盈利恢复",
        status_reason=(
            "2026年上半年收入同比增长1.47%，但归母净利润同比下降1.95%；2025年全年收入和归母净利润也分别下降1.21%和4.53%。"
        ),
        suggested_action="列入观察名单，暂不形成个性化买入结论",
        core_question="渠道改革能否重新带动利润增长，而不只是维持收入规模？",
        verified_view=(
            "2026年一季度收入同比增长6.54%，到上半年累计增速回落至1.47%，增长节奏明显放慢。",
            "上半年归母净利润同比下降1.95%，利润恢复尚未得到验证。",
            "官方披露显示经营现金流大增主要受财务公司成员单位存款与同业存款变动影响，不能直接视为白酒主业现金质量改善。",
        ),
        primary_risks=(
            "白酒行业处于周期和结构调整阶段，终端需求与价格体系仍需观察。",
            "合同负债较上年末下降60.31%，报告解释为销售模式和预收货款政策调整；这一变化需要结合后续动销验证。",
            "缺少可靠的未来盈利一致预期，当前不能判断市场价格是否已经充分反映增长放缓。",
        ),
        validation_conditions=(
            "下一期收入与归母净利润增速同步改善，而不是继续分化。",
            "渠道改革后合同负债、经销商与终端动销形成一致信号。",
            "剔除财务公司影响后，白酒主业现金回款与利润趋势相匹配。",
        ),
        invalidation_conditions=(
            "收入增速继续放缓且利润降幅扩大。",
            "终端价格和渠道库存持续恶化。",
            "估值仍处高位，但未来盈利预期继续下修。",
        ),
        facts=(
            OfficialFact(
                "上半年营业收入",
                _cny_yi(revenue),
                "同比 +1.47%",
                "公司仍保持收入增长，但增速较一季度明显放缓。",
                str(revenue["source_id"]),
                str(revenue["source_location"]),
            ),
            OfficialFact(
                "上半年归母净利润",
                _cny_yi(profit),
                "同比 -1.95%",
                "利润尚未跟随收入恢复，是当前最重要的验证点。",
                str(profit["source_id"]),
                str(profit["source_location"]),
            ),
            OfficialFact(
                "上半年经营现金流",
                _cny_yi(cash_flow),
                "同比 +438.84%",
                "增幅受财务公司存款变动影响，不能直接等同于主业改善。",
                str(cash_flow["source_id"]),
                str(cash_flow["source_location"]),
            ),
            OfficialFact(
                "上半年基本每股收益",
                _eps(eps),
                "同比 -1.68%",
                "这是已披露历史利润口径，不是未来盈利预测。",
                str(eps["source_id"]),
                str(eps["source_location"]),
            ),
        ),
        sources=_sources(("SRC-MT-FY2025", "SRC-MT-Q1-2026", "SRC-MT-H1-2026")),
        valuation_status="动态估值数据不足",
        valuation_reason=(
            "已接入历史财报每股收益，但没有授权实时价格和未来12个月一致预期。当前不计算NTM市盈率、目标价或买入空间。"
        ),
        data_as_of="2026-06-30",
        audit_readiness="关键财务指标已核验；完整模型仍不具备",
        boundary_note="研究状态用于展示证据链，不构成针对任何人的证券买卖建议。",
    )


def _tencent_research() -> OfficialCompanyResearch:
    revenue = _row("腾讯控股", "SRC-TC-H1-2026", "revenue")
    profit = _row("腾讯控股", "SRC-TC-H1-2026", "net_income_attributable")
    cash_flow = _row("腾讯控股", "SRC-TC-H1-2026", "operating_cash_flow")
    eps = _row("腾讯控股", "SRC-TC-H1-2026", "basic_eps")

    return OfficialCompanyResearch(
        ticker="00700",
        company_name="腾讯控股",
        market="港股",
        business_summary=(
            "核心业务由增值服务、营销服务、金融科技与企业服务组成，游戏、广告、支付与云共同贡献收入和现金流。"
        ),
        research_status="基本面通过，估值待补",
        status_reason=(
            "2026年上半年收入、经营利润和归母净利润分别同比增长10%、14%和10%，但AI基础设施投入明显上升，估值数据仍缺失。"
        ),
        suggested_action="列入重点观察名单，补齐估值后再决定是否进入候选组合",
        core_question="AI投入能否形成可持续收入与利润，而不只是推高资本开支？",
        verified_view=(
            "2026年上半年收入为4,012.43亿元，同比增长10%；经营利润同比增长14%。",
            "同期归母净利润同比增长10%，核心盈利仍保持增长。",
            "经营活动现金流净额同比约增长1.8%，而与固定资产和在建工程相关的现金支出从455.58亿元升至956.15亿元。",
        ),
        primary_risks=(
            "AI基础设施投入加速，短期自由现金流和资本回报需要持续验证。",
            "公司同时披露IFRS与非IFRS利润，二者必须分开看，不能只选择更好看的口径。",
            "缺少可靠的实时价格与未来盈利一致预期，尚不能判断当前估值是否提供足够安全边际。",
        ),
        validation_conditions=(
            "营销服务、游戏和云收入继续支撑两位数或接近两位数增长。",
            "AI相关投入逐步转化为收入、毛利或可验证的用户价值。",
            "经营现金流增速能够覆盖资本开支上升，资本回报没有持续恶化。",
        ),
        invalidation_conditions=(
            "收入增速明显下降，同时资本开支继续快速增长。",
            "非IFRS利润增长但IFRS利润和现金流持续走弱。",
            "估值显著高于历史与可比公司，而盈利预测开始下修。",
        ),
        facts=(
            OfficialFact(
                "上半年营业收入",
                _cny_yi(revenue),
                "同比 +10%",
                "三项核心业务共同支持增长。",
                str(revenue["source_id"]),
                str(revenue["source_location"]),
            ),
            OfficialFact(
                "上半年归母净利润",
                _cny_yi(profit),
                "同比 +10%",
                "这里采用IFRS口径，与公司非IFRS利润分开呈现。",
                str(profit["source_id"]),
                str(profit["source_location"]),
            ),
            OfficialFact(
                "上半年经营现金流",
                _cny_yi(cash_flow),
                "同比约 +1.8%",
                "现金流仍为正，但增速低于利润增速。",
                str(cash_flow["source_id"]),
                str(cash_flow["source_location"]),
            ),
            OfficialFact(
                "上半年基本每股收益",
                _eps(eps),
                "同比 +11%",
                "这是已披露历史利润口径，不是未来盈利预测。",
                str(eps["source_id"]),
                str(eps["source_location"]),
            ),
        ),
        sources=_sources(("SRC-TC-FY2025", "SRC-TC-H1-2026")),
        valuation_status="动态估值数据不足",
        valuation_reason=(
            "已接入历史财报每股收益，但没有授权港股实时价格和未来12个月一致预期。当前不计算NTM市盈率、目标价或买入空间。"
        ),
        data_as_of="2026-06-30",
        audit_readiness="关键财务指标已核验；中报未经审计，完整模型仍不具备",
        boundary_note="研究状态用于展示证据链，不构成针对任何人的证券买卖建议。",
    )


def research_universe() -> dict[str, str]:
    return {"600519": "贵州茅台（600519）", "00700": "腾讯控股（00700）"}


def get_official_company_research(ticker: str) -> OfficialCompanyResearch:
    if ticker == "600519":
        return _moutai_research()
    if ticker == "00700":
        return _tencent_research()
    raise ValueError(f"当前官方证据包不支持：{ticker}")


def evidence_audit_summary() -> dict[str, int | str]:
    source_index, financials, qa_flags, checks = load_evidence_tables()
    return {
        "sources": len(source_index),
        "financial_rows": len(financials),
        "open_flags": int((qa_flags["status"] == "open").sum()),
        "passed_checks": int((checks["result"] == "pass").sum()),
        "readiness": "关键指标可用于研究卡，不能用于完整估值模型",
    }
