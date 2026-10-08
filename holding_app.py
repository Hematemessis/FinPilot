from __future__ import annotations

import hashlib
import io
from datetime import datetime
import pandas as pd
import streamlit as st

from advisor.holdings import CATEGORIES, analyze_holdings, example_csv, export_report, local_explanation
from advisor.holding_model import call_model, config_for, explain


def main():
    st.set_page_config(page_title="FinPilot · 持仓分析", page_icon="◈", layout="wide")
    st.markdown("""<style>.stApp{background:#f6f8f7}.block-container{max-width:1180px;padding-top:2rem}h1{letter-spacing:-1px}div[data-testid=stMetric]{background:white;border:1px solid #dfe7e4;padding:16px;border-radius:8px}div[data-testid=stMetricValue]{font-size:24px!important}.stButton>button[kind=primary]{background:#235e54;border-color:#235e54}h2,h3{font-weight:600!important}footer{visibility:hidden}</style>""", unsafe_allow_html=True)
    st.caption("FINPILOT / PORTFOLIO REVIEW · V1.1")
    st.title("看懂持仓，再理解风险")
    st.write("把资产分布、浮动盈亏和数据来源放在一起。先核对事实，再阅读解释。")
    with st.sidebar:
        st.header("模型设置")
        st.caption("可选。未配置时，指标计算和本地说明仍可使用。")
        base = st.text_input("Base URL", value="https://api.openai.com/v1", key="holding_base")
        model = st.text_input("Model Name", placeholder="服务商提供的完整模型ID", key="holding_model")
        key = st.text_input("API Key", type="password", key="holding_key")
        if st.button("测试模型连接"):
            try:
                with st.spinner("测试连接…"):
                    call_model(config_for(base, model, key), [{"role": "user", "content": "Reply OK."}], timeout=15)
                st.success("连接成功，仅验证通信。")
            except ValueError as e:
                st.error(str(e))
        use_ai = st.toggle("启用 AI 解释", key="holding_use_ai")
        consent = st.checkbox("同意将指标摘要和问题发送至所配模型", key="holding_consent")
        st.caption("不发送原始CSV；密钥不写入文件或报告。模型服务的数据政策由该服务决定。请只用自制或脱敏数据。")
        st.divider()
        st.caption("本模块新增于现有FinPilot，专注只读持仓分析；不自动优化或交易。")

    with st.container(border=True):
        st.subheader("01 / 导入一份持仓快照")
        mode = st.radio("数据来源", ["自制示例", "上传 CSV"], horizontal=True, key="holding_source")
        uploaded = None
        if mode == "上传 CSV":
            uploaded = st.file_uploader("选择 UTF-8 CSV（最多100项，150KB）", type=["csv"], key="holding_upload")
            st.download_button("下载字段模板", example_csv().encode("utf-8-sig"), "holding_template.csv", "text/csv")
        source = "自制示例（价格为人为设定，非真实行情）" if mode == "自制示例" else "用户上传CSV（未独立核验）"
        try:
            if uploaded is not None and uploaded.size > 150000:
                st.error("文件超过150KB，请拆分持仓后重试。")
                uploaded = None
            text = example_csv() if mode == "自制示例" else uploaded.getvalue().decode("utf-8-sig") if uploaded else ""
        except UnicodeDecodeError:
            st.error("文件不是UTF-8编码，请另存为CSV UTF-8后重试。")
            text = ""
        fingerprint = hashlib.sha256((text + source).encode()).hexdigest()
        if st.session_state.get("holding_fingerprint") != fingerprint:
            for k in ["holding_report", "holding_explanation", "holding_chat", "holding_history", "holding_generation_error", "holding_question"]:
                st.session_state.pop(k, None)
            st.session_state["holding_fingerprint"] = fingerprint
        st.caption("仅人民币计价；分类由输入提供，不穿透基金。无历史净值时不计算波动率或最大回撤。")
        if text:
            with st.expander("核对输入数据", expanded=True):
                try:
                    st.dataframe(pd.read_csv(io.StringIO(text), dtype=str), hide_index=True, width="stretch")
                except Exception:
                    st.warning("CSV预览失败，请检查格式。")
        if st.button("分析持仓", type="primary", disabled=not bool(text)):
            st.session_state.pop("holding_explanation", None)
            st.session_state.pop("holding_chat", None)
            st.session_state.pop("holding_report", None)
            for k in ["holding_history", "holding_generation_error", "holding_question"]:
                st.session_state.pop(k, None)
            try:
                st.session_state.holding_report = analyze_holdings(text, source=source)
            except ValueError as e:
                st.error(str(e))

    report = st.session_state.get("holding_report")
    if report and "report_id" not in report:
        for name in ["holding_report", "holding_explanation", "holding_history", "holding_chat", "holding_generation_error"]:
            st.session_state.pop(name, None)
        report = None
        st.info("分析模块已更新，请重新分析当前持仓以生成新版本快照。")
    if not report:
        st.info("选择示例后点击“分析持仓”，无需配置模型即可体验。")
        return
    st.caption("程序计算 · " + report["source"])
    st.caption(f"快照 {report['report_id']} · {report['generated_at']}")
    columns = st.columns(4)
    for col, fact in zip(columns, report["facts"][:4]):
        col.metric(fact["title"], fact["value"])
    for warning in report["warnings"]:
        st.warning(warning)
    tab1, tab2, tab3 = st.tabs(["资产结构", "压力情景", "数据与计算口径"])
    with tab1:
        left, right = st.columns([1, 1.4])
        values = {CATEGORIES[c]: v for c, v in report["distribution"].items() if v}
        left.bar_chart(pd.DataFrame({"市值（元）": values}), color="#2c7267", horizontal=True)
        positions = pd.DataFrame(report["positions"])
        positions["权重"] = positions["weight"].map(lambda x: f"{x:.2%}")
        positions = positions.rename(columns={"name": "名称", "market_value": "市值（元）", "pnl": "浮动盈亏（元）", "as_of": "价格日期"})
        right.dataframe(positions[["名称", "市值（元）", "浮动盈亏（元）", "权重", "价格日期"]], hide_index=True, width="stretch")
    with tab2:
        st.info("静态敏感性分析，不是概率预测或历史回测。假设同时作用于当前持仓，忽略相关性变化、交易费用和路径。")
        st.metric("该情景下的市值变化", report["facts"][4]["value"])
        st.table(pd.DataFrame([{"资产类别": CATEGORIES[c], "假设变动": f"{v:.0%}"} for c, v in report["shocks"].items()]))
    with tab3:
        for fact in report["facts"]:
            st.write(f"**{fact['title']}** · {fact['value']}")
            st.caption(f"[{fact['id']}] {fact['description']}")
        st.caption(report["limitation"])

    st.subheader("02 / 解释与追问")
    st.caption("AI只解释已计算的事实，不自行生成数值。结构校验不等于语义正确，仍需核对。")

    def generate(question=""):
        if use_ai:
            if not consent:
                raise ValueError("请先确认允许发送指标摘要和问题。")
            return explain(report, config_for(base, model, key), question or "请解释我的持仓结构与风险边界。")
        return local_explanation(report, question)

    if st.button("生成 AI 解释" if use_ai else "查看本地指标说明"):
        st.session_state.pop("holding_generation_error", None)
        try:
            with st.spinner("生成解释…" if use_ai else "整理指标口径…"):
                st.session_state.holding_explanation = generate()
        except ValueError as e:
            st.session_state.holding_generation_error = str(e)

    def render_explanation(data):
        st.caption(f"AI生成 · 模型：{data.get('model', '未记录')} · 已通过结构校验" if data["mode"] == "live" else "本地说明 · 未调用模型")
        st.text(data["summary"])
        facts = {f["id"]: f for f in report["facts"]}
        for item in data["items"]:
            fact = facts[item["factId"]]
            with st.container(border=True):
                st.write(f"**{fact['title']} · {fact['value']}**")
                st.text(item["explanation"])
                with st.expander("查看计算依据"):
                    st.write(fact["description"])
                    st.caption(f"事实ID：{fact['id']}；来源：{report['source']}")

    explanation = st.session_state.get("holding_explanation")
    if st.session_state.get("holding_generation_error"):
        st.error(st.session_state.holding_generation_error)
        if explanation:
            st.caption("下方保留上次成功解释，本次失败没有生成新解释。")
    if explanation:
        render_explanation(explanation)
    st.caption("保留当前快照最近10次追问。每次独立作答，不会把历史追问发送给模型；修改持仓后清空。")
    question = st.text_input("针对本次持仓追问", placeholder="例如：集中度是什么意思？我的浮动盈亏包含分红吗？", max_chars=1000, key="holding_question")
    if st.button("提交追问", disabled=not question.strip()):
        entry = {"question": question, "report_id": report["report_id"], "at": datetime.now().astimezone().isoformat(timespec="seconds")}
        try:
            with st.spinner("处理追问…"):
                entry["answer"] = generate(question)
        except ValueError as e:
            entry["error"] = str(e)
        st.session_state.holding_history = [*st.session_state.get("holding_history", []), entry][-10:]
    history = st.session_state.get("holding_history", [])
    for i, entry in enumerate(reversed(history)):
        with st.expander(f"{len(history)-i}. {entry['question'][:50]} · {'未成功' if entry.get('error') else '已回答'}", expanded=i == 0):
            st.caption(entry["at"])
            st.text(entry["question"])
            if entry.get("error"):
                st.error(entry["error"])
            else:
                render_explanation(entry["answer"])
    st.divider()
    st.download_button("导出持仓分析报告", export_report(report, explanation, history), "FinPilot_持仓分析.md", "text/markdown")
    st.caption("报告包含持仓明细、快照编号、最近一次成功解释及追问记录；会话刷新后可能丢失，请及时导出。")
    st.caption(report["limitation"])


if __name__ == "__main__":
    main()
