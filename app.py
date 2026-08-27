from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from advisor.agent import PortfolioAdvisorAgent
from advisor.china_market_data import load_eastmoney_prices, research_source_plan
from advisor.data import make_demo_prices
from advisor.official_research import (
    evidence_audit_summary,
    get_official_company_research,
    research_universe,
)
from advisor.risk import RiskAnswers


st.set_page_config(
    page_title="FinPilot｜中国市场投资研究助手",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
    :root {
        --fp-ink: #12212f;
        --fp-muted: #5f6f7d;
        --fp-line: #dce4e3;
        --fp-paper: #ffffff;
        --fp-soft: #f3f7f5;
        --fp-green: #1c695a;
        --fp-green-dark: #124d43;
        --fp-gold: #a96f22;
        --fp-red: #a4423f;
    }
    .stApp { background: #f7f9f8; color: var(--fp-ink); }
    .block-container { max-width: 1160px; padding-top: 1.4rem; padding-bottom: 3rem; }
    h1, h2, h3, h4 { color: var(--fp-ink); letter-spacing: -0.025em; }
    h1 { font-size: clamp(2rem, 5vw, 3.6rem) !important; line-height: 1.08 !important; }
    h2 { margin-top: 1.8rem !important; }
    p, li, label { line-height: 1.65; }
    [data-testid="stHeader"] { background: rgba(247,249,248,.88); }
    [data-testid="stMetric"] {
        background: var(--fp-paper);
        border: 1px solid var(--fp-line);
        border-radius: 14px;
        padding: .9rem 1rem;
    }
    [data-testid="stMetricLabel"] { color: var(--fp-muted); }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--fp-line) !important;
        border-radius: 16px !important;
        background: var(--fp-paper);
    }
    .stButton > button, .stDownloadButton > button {
        min-height: 46px;
        border-radius: 10px;
        border-color: #b9c8c4;
        font-weight: 650;
    }
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
        background: var(--fp-green);
        border-color: var(--fp-green);
    }
    .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
        background: var(--fp-green-dark);
        border-color: var(--fp-green-dark);
    }
    .fp-kicker {
        color: var(--fp-green);
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .16em;
        text-transform: uppercase;
        margin-bottom: .5rem;
    }
    .fp-hero-copy {
        color: var(--fp-muted);
        font-size: 1.15rem;
        max-width: 760px;
        margin-bottom: 1.1rem;
    }
    .fp-note {
        background: #edf4f1;
        border-left: 4px solid var(--fp-green);
        border-radius: 8px;
        padding: .95rem 1.05rem;
        margin: .5rem 0 1rem 0;
    }
    .fp-note strong { color: var(--fp-green-dark); }
    .fp-status {
        background: linear-gradient(135deg, #153f39 0%, #1c695a 100%);
        color: #ffffff;
        border-radius: 18px;
        padding: 1.3rem 1.4rem;
        margin: .5rem 0 1.2rem 0;
    }
    .fp-status .label { opacity: .78; font-size: .82rem; letter-spacing: .08em; }
    .fp-status .title { font-size: 1.65rem; font-weight: 760; margin: .25rem 0; }
    .fp-status .copy { opacity: .92; line-height: 1.6; }
    .fp-source-id {
        display: inline-block;
        color: var(--fp-green-dark);
        background: #e7f1ed;
        border-radius: 999px;
        padding: .14rem .55rem;
        font-size: .74rem;
        font-weight: 700;
    }
    .fp-divider { height: 1px; background: var(--fp-line); margin: 1.6rem 0; }
    @media (max-width: 640px) {
        .block-container { padding: 1rem .85rem 2rem; }
        h1 { font-size: 2.15rem !important; }
        .fp-hero-copy { font-size: 1rem; }
        .fp-status { padding: 1.05rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def demo_prices() -> pd.DataFrame:
    return make_demo_prices()


@st.cache_data(ttl=3_600, show_spinner=False)
def online_prices() -> pd.DataFrame:
    return load_eastmoney_prices(date(2018, 1, 1), date.today())


GOALS = (
    "让闲置资金稳步增值",
    "为买房或大额支出做准备",
    "为长期养老做准备",
    "暂时还没想清楚",
)
HORIZON = {"1年以内": 1, "1—3年": 2, "3—5年": 3, "5—10年": 4, "10年以上": 5}
LOSS = {"最多承受5%": 1, "最多承受10%": 2, "最多承受15%": 3, "最多承受25%": 4, "可承受35%": 5}
INCOME = {"很不稳定": 1, "偏不稳定": 2, "一般": 3, "较稳定": 4, "非常稳定": 5}
LIQUIDITY = {"基本不需要": 1, "需求较低": 2, "中等": 3, "需求较高": 4, "随时可能使用": 5}
REACTION = {"立即全部卖出": 1, "卖出大部分": 2, "保持观察": 3, "继续持有": 4, "按计划加仓": 5}

ASSET_COPY = {
    "510300": ("A股增长部分", "沪深300指数", "覆盖A股核心大盘公司"),
    "A股宽基": ("A股增长部分", "沪深300指数", "覆盖A股核心大盘公司"),
    "159920": ("港股增长部分", "恒生指数", "用人民币分散到港股市场"),
    "港股宽基": ("港股增长部分", "恒生指数", "用人民币分散到港股市场"),
    "511260": ("债券缓冲部分", "中国十年期国债", "缓冲股票市场波动"),
    "中国国债": ("债券缓冲部分", "中国十年期国债", "缓冲股票市场波动"),
    "518880": ("黄金分散部分", "黄金现货合约", "降低对单一市场的依赖"),
    "黄金ETF": ("黄金分散部分", "黄金现货合约", "降低对单一市场的依赖"),
    "现金": ("应急现金", "现金", "应对近期支出和市场波动"),
}

CSI300_PRODUCT = {
    "产品示例": "沪深300ETF华泰柏瑞（510300）",
    "产品说明": "上交所人民币交易，跟踪沪深300指数，作为A股宽基配置示例。",
    "产品风险": "随A股市场波动，并存在跟踪误差、流动性和交易价格偏离净值的风险。",
    "产品状态": "当前回测对应",
}
HANG_SENG_PRODUCT = {
    "产品示例": "恒生ETF华夏（159920）",
    "产品说明": "深交所人民币交易，为组合提供港股宽基敞口。",
    "产品风险": "还受到汇率、跨境额度、溢折价和跟踪误差影响。",
    "产品状态": "当前回测对应",
}
CN_BOND_PRODUCT = {
    "产品示例": "十年国债ETF国泰（511260）",
    "产品说明": "上交所人民币交易，以中国十年期国债作为债券缓冲示例。",
    "产品风险": "不是存款或保本产品，利率、久期和流动性都会造成价格波动。",
    "产品状态": "当前回测对应",
}
GOLD_PRODUCT = {
    "产品示例": "黄金ETF华安（518880）",
    "产品说明": "上交所人民币交易，主要跟踪境内黄金现货价格。",
    "产品风险": "不产生利息，受金价、汇率、溢折价和跟踪误差影响。",
    "产品状态": "当前回测对应",
}
CASH_PRODUCT = {
    "产品示例": "现金余额或银行活期资金",
    "产品说明": "不购买股票，用于近期支出和市场下跌时的缓冲。",
    "产品风险": "如果改为货币基金或短债产品，仍需核验费用、赎回与本金风险。",
    "产品状态": "保持现金",
}
PRODUCT_COPY = {
    "510300": CSI300_PRODUCT,
    "A股宽基": CSI300_PRODUCT,
    "159920": HANG_SENG_PRODUCT,
    "港股宽基": HANG_SENG_PRODUCT,
    "511260": CN_BOND_PRODUCT,
    "中国国债": CN_BOND_PRODUCT,
    "518880": GOLD_PRODUCT,
    "黄金ETF": GOLD_PRODUCT,
    "现金": CASH_PRODUCT,
}
BUCKET_COLORS = {
    "应急现金": "#667681",
    "债券缓冲部分": "#4f7b89",
    "A股增长部分": "#a96f22",
    "港股增长部分": "#1c695a",
    "黄金分散部分": "#8a6273",
}


def money(value: float) -> str:
    return f"¥{value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def go_to(stage: str) -> None:
    st.session_state.stage = stage
    st.session_state.scroll_top_pending = True
    st.rerun()


def restore_page_top() -> None:
    if st.session_state.pop("scroll_top_pending", False):
        components.html("<script>window.parent.scrollTo(0, 0);</script>", height=0)


def render_brand() -> None:
    st.markdown('<div class="fp-kicker">FinPilot · 中国市场研究版</div>', unsafe_allow_html=True)


def advisor_note(title: str, body: str) -> None:
    st.markdown(
        f'<div class="fp-note"><strong>{title}</strong><br>{body}</div>',
        unsafe_allow_html=True,
    )


def show_progress(step: int) -> None:
    labels = ("明确目标", "了解承受力", "生成方案")
    st.caption(f"第 {step} 步，共 3 步｜当前：{labels[step - 1]}")
    st.progress(step / 3)


def reset_journey() -> None:
    for key in (
        "profile_goal",
        "profile_amount",
        "profile_horizon",
        "profile_liquidity",
        "profile_loss",
        "profile_income",
        "profile_reaction",
        "result_strategy",
        "data_mode",
        "a_share_ratio",
        "deferred_buckets",
        "saved_plan",
    ):
        st.session_state.pop(key, None)
    st.session_state.stage = "welcome"
    st.rerun()


def render_welcome() -> None:
    restore_page_top()
    render_brand()
    st.title("把投资问题，变成一份能看懂、能核验的行动方案")
    st.markdown(
        '<div class="fp-hero-copy">先确定这笔钱该怎样分配，再研究具体公司。每个结论都说明证据、风险和下一次复查条件。</div>',
        unsafe_allow_html=True,
    )
    st.caption("面向投资小白的求职作品演示｜不连接证券账户｜不提供无条件买卖口令")

    start_col, research_col = st.columns(2)
    with start_col.container(border=True):
        st.markdown("### 配置一笔钱")
        st.write("回答目标、期限和亏损承受力，得到A股、港股、债券、黄金与现金的金额方案。")
        if st.button("开始做资产配置", type="primary", use_container_width=True):
            st.session_state.data_mode = "离线合成演示数据"
            go_to("goal")
    with research_col.container(border=True):
        st.markdown("### 研究一家公司")
        st.write("查看贵州茅台与腾讯控股的官方财报证据、核心矛盾、风险和验证条件。")
        if st.button("进入公司研究", use_container_width=True):
            go_to("stock_research")

    st.subheader("当前版本真正接入了什么")
    cols = st.columns(3)
    with cols[0].container(border=True):
        st.markdown("#### 资产配置")
        st.write("风险约束、金额分配、四种方案比较、市场下跌模拟和90天复查记录。")
    with cols[1].container(border=True):
        st.markdown("#### 官方财报")
        st.write("贵州茅台3份上交所报告、腾讯2份公司年报/中报，关键页已核验。")
    with cols[2].container(border=True):
        st.markdown("#### 证据边界")
        st.write("实时价格、授权新闻和未来一致预期未接入，不生成虚假的动态市盈率和目标价。")

    advisor_note(
        "你会先看到结论，再看研究过程",
        "结果页优先回答现在做什么、买什么产品、投入多少钱、可能亏多少、何时复查；公式与完整证据放在研究工作底稿。",
    )
    st.caption("本工具用于投资教育和产品演示，不构成证券买卖建议。")


def render_goal() -> None:
    restore_page_top()
    render_brand()
    show_progress(1)
    st.title("这笔钱要解决什么问题？")
    advisor_note("先明确目标", "用途和时间会直接影响需要保留多少现金，以及可以承受多少市场波动。")

    with st.form("goal_form"):
        saved_goal = st.session_state.get("profile_goal", GOALS[0])
        goal_label = st.radio("这笔钱主要用来做什么？", GOALS, index=GOALS.index(saved_goal))
        amount = st.number_input(
            "准备投入多少钱？",
            min_value=1_000.0,
            max_value=100_000_000.0,
            value=float(st.session_state.get("profile_amount", 100_000.0)),
            step=10_000.0,
            help="只用于把比例换算成金额，不会发生真实交易。",
        )
        saved_horizon = st.session_state.get("profile_horizon", "5—10年")
        horizon_label = st.radio(
            "预计多久不会用到这笔钱？",
            tuple(HORIZON),
            index=tuple(HORIZON).index(saved_horizon),
            horizontal=True,
        )
        saved_liquidity = st.session_state.get("profile_liquidity", "中等")
        liquidity_label = st.radio(
            "近期使用这笔钱的可能性？",
            tuple(LIQUIDITY),
            index=tuple(LIQUIDITY).index(saved_liquidity),
            horizontal=True,
        )
        submitted = st.form_submit_button("继续了解承受力", type="primary")

    if submitted:
        st.session_state.profile_goal = goal_label
        st.session_state.profile_amount = amount
        st.session_state.profile_horizon = horizon_label
        st.session_state.profile_liquidity = liquidity_label
        go_to("risk")
    if st.button("返回首页"):
        go_to("welcome")


def render_risk() -> None:
    restore_page_top()
    render_brand()
    show_progress(2)
    st.title("市场下跌时，你能承受到哪里？")
    advisor_note(
        "已记录你的目标",
        f"投入 {money(st.session_state.profile_amount)}，用于“{st.session_state.profile_goal}”，预计持有 {st.session_state.profile_horizon}。再回答三项，系统会排除超出承受范围的方案。",
    )

    with st.form("risk_form"):
        saved_loss = st.session_state.get("profile_loss", "最多承受15%")
        loss_label = st.radio(
            "如果投入10万元，阶段性最多亏多少仍不影响生活？",
            tuple(LOSS),
            index=tuple(LOSS).index(saved_loss),
            horizontal=True,
        )
        saved_income = st.session_state.get("profile_income", "较稳定")
        income_label = st.radio(
            "你的收入稳定吗？",
            tuple(INCOME),
            index=tuple(INCOME).index(saved_income),
            horizontal=True,
        )
        saved_reaction = st.session_state.get("profile_reaction", "继续持有")
        reaction_label = st.radio(
            "看到组合明显下跌时，你通常会怎么做？",
            tuple(REACTION),
            index=tuple(REACTION).index(saved_reaction),
            horizontal=True,
        )
        submitted = st.form_submit_button("生成投资方案", type="primary")

    if submitted:
        st.session_state.profile_loss = loss_label
        st.session_state.profile_income = income_label
        st.session_state.profile_reaction = reaction_label
        st.session_state.result_strategy = "风险适配"
        go_to("result")
    if st.button("返回修改目标"):
        go_to("goal")


def adjusted_weights(weights: pd.Series) -> pd.Series:
    adjusted = weights.copy().astype(float)
    a_key = "510300" if "510300" in adjusted else "A股宽基"
    hk_key = "159920" if "159920" in adjusted else "港股宽基"
    equity_total = float(adjusted.get(a_key, 0.0) + adjusted.get(hk_key, 0.0))
    default_ratio = 55
    if equity_total > 0:
        raw_ratio = float(adjusted.get(a_key, 0.0)) / equity_total * 100
        default_ratio = int(round(raw_ratio / 5) * 5)
    st.session_state.setdefault("a_share_ratio", default_ratio)
    ratio = float(st.session_state.a_share_ratio) / 100
    adjusted[a_key] = equity_total * ratio
    adjusted[hk_key] = equity_total * (1 - ratio)

    deferred = set(st.session_state.get("deferred_buckets", []))
    for asset in list(adjusted.index):
        bucket = ASSET_COPY.get(asset, (asset, asset, ""))[0]
        if bucket in deferred and asset != "现金":
            adjusted["现金"] = float(adjusted.get("现金", 0.0)) + float(adjusted[asset])
            adjusted[asset] = 0.0
    return adjusted / adjusted.sum()


def allocation_rows(weights: pd.Series, amount: float) -> pd.DataFrame:
    rows = []
    for asset, weight in weights.items():
        if float(weight) < 0.0001:
            continue
        title, example, purpose = ASSET_COPY.get(asset, (asset, asset, "分散组合风险"))
        product = PRODUCT_COPY.get(
            asset,
            {
                "产品示例": "尚未建立产品映射",
                "产品说明": "需要进一步核验可购买产品。",
                "产品风险": "缺少产品证据，不能用于执行。",
                "产品状态": "待核验",
            },
        )
        rows.append(
            {
                "放在哪里": title,
                "建议比例": float(weight),
                "参考金额": amount * float(weight),
                "主要作用": purpose,
                "底层示例": example,
                **product,
            }
        )
    order = {"应急现金": 0, "债券缓冲部分": 1, "A股增长部分": 2, "港股增长部分": 3, "黄金分散部分": 4}
    return pd.DataFrame(rows).sort_values("放在哪里", key=lambda x: x.map(order).fillna(99))


def allocation_chart(allocation: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    for row in allocation.to_dict("records"):
        figure.add_trace(
            go.Bar(
                name=row["放在哪里"],
                y=["全部资金"],
                x=[row["建议比例"]],
                orientation="h",
                marker={"color": BUCKET_COLORS.get(row["放在哪里"], "#667681"), "line": {"color": "#FFFFFF", "width": 2}},
                text=[pct(row["建议比例"])],
                textposition="inside",
                insidetextanchor="middle",
                textfont={"color": "#FFFFFF", "size": 14},
                customdata=[[row["放在哪里"], money(row["参考金额"]), row["产品示例"]]],
                hovertemplate="<b>%{customdata[0]}</b><br>比例 %{x:.1%}<br>参考金额 %{customdata[1]}<br>%{customdata[2]}<extra></extra>",
            )
        )
    figure.update_layout(
        barmode="stack",
        height=135,
        margin={"l": 4, "r": 4, "t": 6, "b": 6},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        uniformtext={"minsize": 10, "mode": "hide"},
    )
    figure.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
    figure.update_yaxes(visible=False, fixedrange=True)
    return figure


def build_plan_record(report, allocation: pd.DataFrame, data_label: str) -> dict:
    return {
        "product": "FinPilot China Market Demo",
        "created_at": date.today().isoformat(),
        "review_on": (date.today() + timedelta(days=90)).isoformat(),
        "goal": st.session_state.profile_goal,
        "amount_cny": float(st.session_state.profile_amount),
        "horizon": st.session_state.profile_horizon,
        "risk_level": report.profile.level,
        "risk_score": int(report.profile.score),
        "strategy": st.session_state.get("result_strategy", "风险适配"),
        "data_label": data_label,
        "allocation": [
            {
                "bucket": row["放在哪里"],
                "weight": round(float(row["建议比例"]), 6),
                "amount_cny": round(float(row["参考金额"]), 2),
                "product_example": row["产品示例"],
            }
            for row in allocation.to_dict("records")
        ],
        "boundary": "求职作品与投资教育演示，不构成证券买卖建议。",
    }


def render_result() -> None:
    restore_page_top()
    required = (
        "profile_goal",
        "profile_amount",
        "profile_horizon",
        "profile_liquidity",
        "profile_loss",
        "profile_income",
        "profile_reaction",
    )
    if any(key not in st.session_state for key in required):
        go_to("goal")
        return

    render_brand()
    show_progress(3)

    data_mode = st.session_state.get("data_mode", "离线合成演示数据")
    try:
        if data_mode == "A股/港股公开历史行情":
            with st.spinner("正在读取公开历史行情并验证方案"):
                prices = online_prices()
            data_label = "东方财富公开历史行情（前复权、非生产授权行情）"
        else:
            prices = demo_prices()
            data_label = "四类中国市场资产的固定随机种子合成演示数据"
    except Exception:
        st.warning("公开行情暂时无法读取，已自动切回离线演示数据。")
        prices = demo_prices()
        data_label = "四类中国市场资产的固定随机种子合成演示数据"
        st.session_state.data_mode = "离线合成演示数据"

    answers = RiskAnswers(
        investment_horizon=HORIZON[st.session_state.profile_horizon],
        loss_tolerance=LOSS[st.session_state.profile_loss],
        income_stability=INCOME[st.session_state.profile_income],
        liquidity_need=LIQUIDITY[st.session_state.profile_liquidity],
        loss_reaction=REACTION[st.session_state.profile_reaction],
    )
    strategy = st.session_state.get("result_strategy", "风险适配")
    report = PortfolioAdvisorAgent().run(prices, answers, strategy=strategy, fee_bps=10.0, data_label=data_label)
    amount = float(st.session_state.profile_amount)
    # Initialise the editable A/H split from the model before Streamlit renders the slider.
    adjusted_weights(report.weights)

    st.title("你的第一版投资方案")
    strategy_title = "建议采用分散配置，分批执行" if strategy == "风险适配" else "当前正在查看更稳健的备选方案"
    st.markdown(
        f"""
        <div class="fp-status">
            <div class="label">现在建议做什么</div>
            <div class="title">{strategy_title}</div>
            <div class="copy">你属于{report.profile.level}，准备投入 {money(amount)}，目标是“{st.session_state.profile_goal}”。先保留现金缓冲，再把长期资金分散到四类资产。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("调整这份方案", expanded=False):
        adjust_cols = st.columns(2)
        with adjust_cols[0]:
            st.slider("A股占股票部分的比例", 0, 100, key="a_share_ratio", step=5, help="只调整A股与港股的内部比例，不改变股票总比例。")
        with adjust_cols[1]:
            st.multiselect(
                "暂不执行哪些部分，先留作现金",
                ("A股增长部分", "港股增长部分", "债券缓冲部分", "黄金分散部分"),
                key="deferred_buckets",
                help="被选中的部分会暂时转为现金。",
            )
        st.caption("手动调整会更新金额和情景模拟；历史回测仍对应系统生成的原方案。")

    weights = adjusted_weights(report.weights)
    allocation = allocation_rows(weights, amount)
    result = report.primary_result

    st.subheader("买什么、投入多少钱")
    st.caption("整条资金带合计100%。点击图表中的区段可以查看金额与产品。")
    st.plotly_chart(allocation_chart(allocation), use_container_width=True, config={"displayModeBar": False, "responsive": True})

    for start in range(0, len(allocation), 2):
        product_cols = st.columns(2)
        for offset, row in enumerate(allocation.to_dict("records")[start : start + 2]):
            with product_cols[offset].container(border=True):
                name_col, amount_col = st.columns((1.45, 1))
                name_col.markdown(f"#### {row['放在哪里']}")
                name_col.caption(row["主要作用"])
                amount_col.metric("参考金额", money(row["参考金额"]))
                amount_col.caption(f"占总资金 {pct(row['建议比例'])}")
                st.markdown(f"**{row['产品示例']}**")
                st.write(row["产品说明"])
                st.caption(f"主要风险：{row['产品风险']}")

    st.caption("当前没有接入实时盘口、手续费和最小交易单位，所以给出参考金额，不伪造可下单份数。")

    st.subheader("可能亏多少")
    historical_drawdown = abs(result.metrics["最大回撤"])
    historical_loss = amount * historical_drawdown
    tolerance_loss = amount * report.profile.max_drawdown_tolerance
    risk_cols = st.columns(3)
    risk_cols[0].metric("历史测试最大回落", pct(historical_drawdown))
    risk_cols[1].metric("折算为当前金额", money(historical_loss))
    risk_cols[2].metric("你的问卷承受上限", money(tolerance_loss))
    if historical_drawdown > report.profile.max_drawdown_tolerance:
        st.warning("历史测试已经超过你的承受范围，不建议直接采用。请降低风险或重新评估投入金额。")
    else:
        st.info("历史测试未超过问卷上限，但未来可能出现更大波动；这不是最大损失保证。")

    with st.expander("模拟一次市场下跌"):
        shock_cols = st.columns(4)
        a_shock = shock_cols[0].slider("A股变动", -60, 10, -20, key="a_shock", format="%d%%") / 100
        hk_shock = shock_cols[1].slider("港股变动", -60, 10, -25, key="hk_shock", format="%d%%") / 100
        bond_shock = shock_cols[2].slider("国债变动", -20, 20, -3, key="bond_shock", format="%d%%") / 100
        gold_shock = shock_cols[3].slider("黄金变动", -30, 30, 5, key="gold_shock", format="%d%%") / 100
        shocks = {"A股增长部分": a_shock, "港股增长部分": hk_shock, "债券缓冲部分": bond_shock, "黄金分散部分": gold_shock, "应急现金": 0.0}
        scenario_return = sum(float(row["建议比例"]) * shocks.get(row["放在哪里"], 0.0) for row in allocation.to_dict("records"))
        scenario_loss = amount * scenario_return
        st.metric("这组假设下的组合变动", pct(scenario_return), delta=money(scenario_loss), delta_color="normal")
        st.caption("这是一次静态情景计算，不是价格预测，也没有模拟市场相关性随危机变化。")

    st.subheader("为什么这样安排")
    reason_cols = st.columns(2)
    with reason_cols[0].container(border=True):
        st.markdown("#### 来自你的约束")
        st.write(f"持有期限：{st.session_state.profile_horizon}")
        st.write(f"资金使用需求：{st.session_state.profile_liquidity}")
        st.write(f"阶段亏损承受：{st.session_state.profile_loss.replace('最多承受', '')}")
        st.write(f"最低现金比例：{pct(report.profile.min_cash_weight)}")
    with reason_cols[1].container(border=True):
        st.markdown("#### 来自组合规则")
        st.write("先锁定现金底线和单类资产上限。")
        st.write("再结合历史波动和资产之间的联动关系分配剩余资金。")
        st.write("前65%数据生成比例，后35%只用于检验。")
        st.write("这不是对某类资产未来一定上涨的预测。")

    st.subheader("你可以继续调整")
    action_cols = st.columns(4)
    with action_cols[0]:
        if st.button("降低风险", use_container_width=True, disabled=strategy == "最小方差"):
            st.session_state.result_strategy = "最小方差"
            st.rerun()
    with action_cols[1]:
        if st.button("恢复建议方案", use_container_width=True, disabled=strategy == "风险适配"):
            st.session_state.result_strategy = "风险适配"
            st.rerun()
    with action_cols[2]:
        if st.button("研究具体公司", use_container_width=True):
            go_to("stock_research")
    with action_cols[3]:
        if st.button("重新回答问题", use_container_width=True):
            reset_journey()

    with st.expander("比较四种配置方式"):
        strategy_names = {"风险适配": "建议方案", "最小方差": "更低波动", "最大夏普": "收益风险比优先", "等权配置": "平均分配"}
        comparison_rows = [
            {
                "配置方式": strategy_names[name],
                "测试期年化增长": pct(item.metrics["年化收益"]),
                "测试期波动": pct(item.metrics["年化波动"]),
                "历史最大回落": pct(item.metrics["最大回撤"]),
                "收益风险比": f"{item.metrics['夏普比率']:.2f}",
            }
            for name, item in report.comparisons.items()
        ]
        st.dataframe(pd.DataFrame(comparison_rows), hide_index=True, use_container_width=True)
        st.caption("这些结果只描述当前数据和测试假设，不代表未来表现。")

    st.subheader("保存方案与复查条件")
    plan_record = build_plan_record(report, allocation, data_label)
    save_col, download_col = st.columns(2)
    with save_col:
        if st.button("保存当前方案", type="primary", use_container_width=True):
            st.session_state.saved_plan = plan_record
            st.success(f"已保存在当前浏览器会话中，建议在 {plan_record['review_on']} 前复查。")
    with download_col:
        st.download_button(
            "下载方案记录",
            data=json.dumps(plan_record, ensure_ascii=False, indent=2),
            file_name=f"finpilot_plan_{date.today().isoformat()}.json",
            mime="application/json",
            use_container_width=True,
        )
    st.markdown(
        "- 每90天复查一次，或在目标、收入和用钱时间发生变化时提前复查。\n"
        "- 如果实际回落接近问卷上限，先检查风险承受力，不追涨杀跌。\n"
        "- 产品费率、规模、跟踪误差或流动性明显变化时，重新比较同类产品。"
    )

    with st.expander("研究工作底稿"):
        st.radio(
            "验证数据",
            ("离线合成演示数据", "A股/港股公开历史行情"),
            horizontal=True,
            key="data_mode",
            help="在线模式是公开前复权日线，仅用于求职演示；失败会自动回退。",
        )
        st.write(f"样本外验证区间：{result.test_start.date()}—{result.test_end.date()}")
        metric_cols = st.columns(4)
        metric_cols[0].metric("测试期年化增长", pct(result.metrics["年化收益"]))
        metric_cols[1].metric("历史最大回落", pct(result.metrics["最大回撤"]))
        metric_cols[2].metric("收益风险比", f"{result.metrics['夏普比率']:.2f}")
        metric_cols[3].metric("测试期年化波动", pct(result.metrics["年化波动"]))
        st.code(
            "风险适配权重 = (1-g) × 最小方差权重 + g × 最大夏普权重\n"
            "g = 50% × 风险得分 + 50% × 目标波动位置，并限制在10%—90%\n"
            "约束：总权重=100%，现金≥现金底线，单类资产≤集中度上限",
            language="text",
        )
        st.caption(f"当前计算数据：{data_label}")

    st.caption("能力边界：不执行交易，不预测短期涨跌，不把回测收益当作承诺。")


def render_stock_research() -> None:
    restore_page_top()
    render_brand()
    st.title("研究一家公司，先找证据再下结论")
    universe = research_universe()
    ticker = st.selectbox(
        "选择公司",
        tuple(universe),
        format_func=lambda code: universe[code],
        key="research_ticker",
    )
    research = get_official_company_research(ticker)

    st.markdown(
        f"""
        <div class="fp-status">
            <div class="label">投顾研究结论 · {research.market}</div>
            <div class="title">{research.research_status}</div>
            <div class="copy">{research.status_reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    action_col, asof_col, confidence_col = st.columns(3)
    with action_col.container(border=True):
        st.caption("现在建议做什么")
        st.markdown(f"#### {research.suggested_action}")
    with asof_col.container(border=True):
        st.caption("数据截止")
        st.markdown(f"#### {research.data_as_of}")
    with confidence_col.container(border=True):
        st.caption("证据状态")
        st.markdown("#### 官方财报已核验")

    advisor_note("核心矛盾", research.core_question)

    st.subheader("先看四个关键数字")
    fact_cols = st.columns(2)
    for index, fact in enumerate(research.facts):
        with fact_cols[index % 2].container(border=True):
            st.caption(fact.label)
            st.markdown(f"### {fact.value}")
            st.write(fact.change)
            st.write(fact.meaning)
            st.markdown(f'<span class="fp-source-id">{fact.source_id}</span>', unsafe_allow_html=True)
            st.caption(fact.source_location)

    st.subheader("公司怎么赚钱")
    st.write(research.business_summary)

    view_col, risk_col = st.columns(2)
    with view_col.container(border=True):
        st.markdown("#### 已验证的事实")
        for item in research.verified_view:
            st.markdown(f"- {item}")
    with risk_col.container(border=True):
        st.markdown("#### 需要重点防范")
        for item in research.primary_risks:
            st.markdown(f"- {item}")

    st.subheader("估值能不能支持买入判断")
    st.warning(f"{research.valuation_status}：{research.valuation_reason}")
    st.caption("动态市盈率应使用当前价格除以未来12个月一致预期每股收益；不能把最近一个季度利润简单乘以四。")

    st.subheader("什么会证明或推翻这项判断")
    prove_col, disprove_col = st.columns(2)
    with prove_col.container(border=True):
        st.markdown("#### 继续研究前需要看到")
        for item in research.validation_conditions:
            st.markdown(f"- {item}")
    with disprove_col.container(border=True):
        st.markdown("#### 出现这些情况就重新判断")
        for item in research.invalidation_conditions:
            st.markdown(f"- {item}")

    st.subheader("官方来源与证据追溯")
    for source in research.sources:
        with st.container(border=True):
            title_col, link_col = st.columns((3, 1))
            title_col.markdown(f"**{source.name}**")
            title_col.caption(f"{source.source_id}｜报告期 {source.as_of_date}")
            title_col.write(source.notes)
            url = source.location.split(" | ")[0]
            link_col.link_button("打开官方报告", url, use_container_width=True)
            st.caption(source.location)

    with st.expander("查看数据源接入状态与研究底稿"):
        for market_source in research_source_plan(research.market):
            st.markdown(f"**{market_source.category}｜{market_source.implementation_status}**")
            st.caption(f"{market_source.name}｜{market_source.authority}")
            st.write(market_source.note)
        audit = evidence_audit_summary()
        audit_cols = st.columns(4)
        audit_cols[0].metric("官方来源", audit["sources"])
        audit_cols[1].metric("归一化指标", audit["financial_rows"])
        audit_cols[2].metric("已通过检查", audit["passed_checks"])
        audit_cols[3].metric("仍需处理", audit["open_flags"])
        st.caption(str(audit["readiness"]))

    st.caption(research.audit_readiness)
    st.caption(research.boundary_note)
    back_col, result_col = st.columns(2)
    with back_col:
        if st.button("返回首页", use_container_width=True):
            go_to("welcome")
    with result_col:
        has_result = all(
            key in st.session_state
            for key in (
                "profile_goal",
                "profile_amount",
                "profile_horizon",
                "profile_liquidity",
                "profile_loss",
                "profile_income",
                "profile_reaction",
            )
        )
        if st.button("回到资产配置", use_container_width=True, disabled=not has_result):
            go_to("result")


st.session_state.setdefault("stage", "welcome")

if st.session_state.stage == "welcome":
    render_welcome()
elif st.session_state.stage == "goal":
    render_goal()
elif st.session_state.stage == "risk":
    render_risk()
elif st.session_state.stage == "stock_research":
    render_stock_research()
else:
    render_result()
