from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

import pandas as pd
import requests

from .data import validate_prices


@dataclass(frozen=True)
class ChinaSecurity:
    code: str
    name: str
    market: str
    exchange: str
    currency: str
    eastmoney_secid: str
    asset_name: str
    instrument_type: str
    exposure_market: str


@dataclass(frozen=True)
class MarketSource:
    source_id: str
    market: str
    category: str
    name: str
    url: str | None
    authority: str
    implementation_status: str
    note: str


SECURITY_MASTER: dict[str, ChinaSecurity] = {
    "510300": ChinaSecurity(
        code="510300",
        name="沪深300ETF华泰柏瑞",
        market="A股",
        exchange="上交所",
        currency="CNY",
        eastmoney_secid="1.510300",
        asset_name="A股宽基",
        instrument_type="ETF",
        exposure_market="A股",
    ),
    "159920": ChinaSecurity(
        code="159920",
        name="恒生ETF华夏",
        market="A股",
        exchange="深交所",
        currency="CNY",
        eastmoney_secid="0.159920",
        asset_name="港股宽基",
        instrument_type="跨境ETF",
        exposure_market="港股",
    ),
    "511260": ChinaSecurity(
        code="511260",
        name="十年国债ETF国泰",
        market="A股",
        exchange="上交所",
        currency="CNY",
        eastmoney_secid="1.511260",
        asset_name="中国国债",
        instrument_type="债券ETF",
        exposure_market="中国债券",
    ),
    "518880": ChinaSecurity(
        code="518880",
        name="黄金ETF华安",
        market="A股",
        exchange="上交所",
        currency="CNY",
        eastmoney_secid="1.518880",
        asset_name="黄金ETF",
        instrument_type="商品ETF",
        exposure_market="黄金",
    ),
    "600519": ChinaSecurity(
        code="600519",
        name="贵州茅台",
        market="A股",
        exchange="上交所",
        currency="CNY",
        eastmoney_secid="1.600519",
        asset_name="贵州茅台",
        instrument_type="股票",
        exposure_market="A股",
    ),
    "00700": ChinaSecurity(
        code="00700",
        name="腾讯控股",
        market="港股",
        exchange="港交所",
        currency="HKD",
        eastmoney_secid="116.00700",
        asset_name="腾讯控股",
        instrument_type="股票",
        exposure_market="港股",
    ),
}

DEFAULT_CHINA_ALLOCATION_SYMBOLS = ("510300", "159920", "511260", "518880")

MARKET_SOURCES: tuple[MarketSource, ...] = (
    MarketSource(
        source_id="eastmoney_history",
        market="A股/港股",
        category="历史行情",
        name="东方财富公开历史行情接口",
        url="https://push2his.eastmoney.com/",
        authority="公开演示源（非交易所官方）",
        implementation_status="已接入",
        note="前复权日线；用于求职演示，生产环境应替换为授权行情源。",
    ),
    MarketSource(
        source_id="cninfo",
        market="A股",
        category="公告与财报",
        name="巨潮资讯",
        url="https://www.cninfo.com.cn/new/index",
        authority="法定信息披露平台",
        implementation_status="来源规则已定义，正文解析待接入",
        note="优先使用公告原文，不用二手摘要替代。",
    ),
    MarketSource(
        source_id="sse",
        market="A股",
        category="上交所公告",
        name="上海证券交易所",
        url="https://www.sse.com.cn/disclosure/listedinfo/announcement/",
        authority="交易所官方",
        implementation_status="贵州茅台财报已接入",
        note="已接入贵州茅台2025年报、2026一季报和2026半年报；其他公司仍需逐家扩展。",
    ),
    MarketSource(
        source_id="szse",
        market="A股",
        category="深交所公告",
        name="深圳证券交易所",
        url="https://www.szse.cn/disclosure/listed/notice/index.html",
        authority="交易所官方",
        implementation_status="来源规则已定义，正文解析待接入",
        note="与巨潮资讯交叉核验深交所公司公告。",
    ),
    MarketSource(
        source_id="hkexnews",
        market="港股",
        category="公告与财报",
        name="披露易 HKEXnews",
        url="https://www1.hkexnews.hk/index.htm",
        authority="港交所官方",
        implementation_status="来源规则已定义，正文解析待接入",
        note="港股公告和定期报告的首选一手来源。",
    ),
    MarketSource(
        source_id="issuer_ir",
        market="A股/港股",
        category="公司材料",
        name="上市公司投资者关系网站",
        url=None,
        authority="公司一手披露",
        implementation_status="腾讯财报已接入",
        note="已接入腾讯2025年报和2026中报；管理层表述仍与审计财务事实分开标记。",
    ),
    MarketSource(
        source_id="official_policy_events",
        market="A股/港股",
        category="政策与市场事件",
        name="证监会、交易所及政府部门官方发布",
        url=None,
        authority="监管或政府一手来源",
        implementation_status="来源规则已定义，事件解析待接入",
        note="先记录原文、发布时间和影响路径，再判断是否改变公司经营假设。",
    ),
    MarketSource(
        source_id="licensed_financial_news",
        market="A股/港股",
        category="财经新闻",
        name="授权财经新闻数据源",
        url=None,
        authority="需版权和接口授权",
        implementation_status="未接入",
        note="未授权前只使用公司公告和官方政策信息，不批量抓取网页新闻冒充稳定数据源。",
    ),
    MarketSource(
        source_id="licensed_consensus",
        market="A股/港股",
        category="一致预期与动态估值",
        name="授权预测数据源",
        url=None,
        authority="需 Wind、Choice、iFinD 或同等级授权源",
        implementation_status="未接入",
        note="未接入前不展示真实 NTM/FY1 市盈率，不抓取网页值冒充一致预期。",
    ),
)


def research_source_plan(market: str) -> tuple[MarketSource, ...]:
    if market not in {"A股", "港股"}:
        raise ValueError("Market must be A股 or 港股")
    return tuple(source for source in MARKET_SOURCES if market in source.market)


def parse_eastmoney_klines(
    payload: dict,
    security: ChinaSecurity,
) -> pd.Series:
    data = payload.get("data")
    if not data or not data.get("klines"):
        raise ValueError(f"东方财富未返回 {security.code} 的历史行情")
    returned_code = str(data.get("code", "")).zfill(len(security.code))
    if returned_code and returned_code != security.code:
        raise ValueError(
            f"证券代码不匹配：请求 {security.code}，返回 {returned_code}"
        )

    dates: list[pd.Timestamp] = []
    closes: list[float] = []
    for raw_row in data["klines"]:
        fields = raw_row.split(",")
        if len(fields) < 3:
            continue
        try:
            timestamp = pd.Timestamp(fields[0])
            close = float(fields[2])
        except (TypeError, ValueError):
            continue
        if close <= 0:
            raise ValueError(f"{security.code} 返回了非正数收盘价")
        dates.append(timestamp)
        closes.append(close)

    if not closes:
        raise ValueError(f"{security.code} 没有可用的正数收盘价")
    series = pd.Series(closes, index=pd.DatetimeIndex(dates), name=security.code)
    return series.loc[~series.index.duplicated(keep="last")].sort_index()


def _load_eastmoney_security(
    security: ChinaSecurity,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    query = urlencode(
        {
            "secid": security.eastmoney_secid,
            "klt": "101",
            "fqt": "1",
            "beg": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "lmt": "10000",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        }
    )
    url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?{query}"
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 FinPilot/1.0",
                "Referer": "https://quote.eastmoney.com/",
            },
            timeout=(2.5, 5.0),
        )
        response.raise_for_status()
        payload = response.json()
        return parse_eastmoney_klines(payload, security)
    except Exception as exc:  # Network/provider errors become a controlled fallback.
        raise ValueError(
            f"公开行情暂时不可用（{security.code} {security.name}），请稍后重试"
        ) from exc


def load_eastmoney_prices(
    start: date | str,
    end: date | str,
    symbols: tuple[str, ...] = DEFAULT_CHINA_ALLOCATION_SYMBOLS,
) -> pd.DataFrame:
    """Load aligned A/H-related ETF closes from a public demo endpoint.

    The series are daily forward-adjusted closes in CNY. This adapter is for
    reproducible product demos; it is not a licensed production market feed.
    """

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    if start_ts >= end_ts:
        raise ValueError("Start date must be earlier than end date")
    if len(set(symbols)) != len(symbols):
        raise ValueError("Security symbols must be unique")
    try:
        securities = tuple(SECURITY_MASTER[symbol] for symbol in symbols)
    except KeyError as exc:
        raise ValueError(f"Unsupported China-market symbol: {exc.args[0]}") from exc

    # Bound the UI wait: all public-demo requests run together and fail fast.
    with ThreadPoolExecutor(max_workers=len(securities)) as executor:
        series = list(
            executor.map(
                lambda security: _load_eastmoney_security(
                    security, start_ts, end_ts
                ),
                securities,
            )
        )
    prices = validate_prices(pd.concat(series, axis=1, join="inner"))
    prices.attrs.update(
        {
            "source": "东方财富公开历史行情接口",
            "adjustment": "前复权",
            "currency": "CNY",
            "markets": "A股ETF及港股跨境ETF",
            "as_of": prices.index.max().date().isoformat(),
            "licensed_production_feed": False,
        }
    )
    return prices
