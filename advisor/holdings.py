"""Deterministic snapshot diagnostics; never infer a historical track record."""
from __future__ import annotations

import csv
import io
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

CATEGORIES = {"stock": "股票", "fund": "基金", "bond": "债券", "gold": "黄金", "cash": "现金", "other": "其他"}
SHOCKS = {"stock": -.20, "fund": -.15, "bond": -.03, "gold": -.10, "cash": 0., "other": -.10}
FIELDS = ["symbol", "name", "asset_class", "quantity", "cost_price", "current_price", "as_of"]
LIMITATION = "仅分析所提供的人民币多头持仓截面。浮动盈亏不含费用、分红和已实现收益；不代表历史投资收益率。分类不穿透底层资产，压力情景不是预测。不提供具体交易建议。"


def example_csv(today: date | None = None) -> str:
    day = (today or date.today()).isoformat()
    return "symbol,name,asset_class,quantity,cost_price,current_price,as_of,currency\n" + "\n".join([
        f"DEMO_A,自制股票甲,stock,1000,20,24,{day},CNY",
        f"DEMO_B,自制宽基基金,fund,5000,3,2.8,{day},CNY",
        f"DEMO_C,自制债券基金,bond,8000,1,1.05,{day},CNY",
        f"CASH,现金,cash,10000,1,1,{day},CNY",
    ]) + "\n"


def number(value: str, label: str, allow_zero: bool = False) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label}必须是有效数字。") from None
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0) or result > Decimal("1e12"):
        raise ValueError(f"{label}超出范围，不能为负数、无穷或非数字。")
    if result != 0 and result < Decimal("1e-8"):
        raise ValueError(f"{label}精度超出原型支持范围。")
    return result


def analyze_holdings(text: str, today: date | None = None, source: str = "用户上传CSV") -> dict:
    today = today or date.today()
    if not isinstance(text, str) or not text.strip() or len(text) > 150000:
        raise ValueError("请输入不超过150KB的持仓CSV。")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
        raise ValueError("缺少必填列：" + ", ".join(FIELDS))
    if len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("CSV表头不能重复。")
    positions, seen, warnings = [], set(), []
    total = Decimal(0)
    cost = Decimal(0)
    for line, row in enumerate(reader, 2):
        if len(positions) >= 100:
            raise ValueError("最多支持100项持仓。")
        if None in row or any(row.get(f) is None or not str(row[f]).strip() for f in FIELDS):
            raise ValueError(f"第{line}行列数或必填字段不正确。")
        symbol, name, category = (row[k].strip() for k in ("symbol", "name", "asset_class"))
        if len(symbol) > 40 or len(name) > 80:
            raise ValueError(f"第{line}行代码或名称过长。")
        if symbol.upper() in seen:
            raise ValueError(f"第{line}行代码重复，请先合并同一资产。")
        seen.add(symbol.upper())
        if category not in CATEGORIES:
            raise ValueError(f"第{line}行asset_class无效：使用stock/fund/bond/gold/cash/other。")
        if row.get("currency", "CNY").strip().upper() != "CNY":
            raise ValueError(f"第{line}行不是CNY计价，V1不支持跨币种合并。")
        try:
            as_of = date.fromisoformat(row["as_of"].strip())
        except ValueError:
            raise ValueError(f"第{line}行日期必须为YYYY-MM-DD。") from None
        if row["as_of"].strip() != as_of.isoformat() or as_of > today:
            raise ValueError(f"第{line}行日期无效或晚于今天。")
        qty = number(row["quantity"], f"第{line}行数量")
        cp = number(row["cost_price"], f"第{line}行成本价", allow_zero=True)
        price = number(row["current_price"], f"第{line}行当前价")
        value, basis = qty * price, qty * cp
        if max(value, basis) > Decimal("1e15"):
            raise ValueError(f"第{line}行金额超出原型范围。")
        total += value
        cost += basis
        stale = (today - as_of).days > 7
        if stale:
            warnings.append(f"{symbol}价格日期超过7个自然日，需确认数据时效。")
        positions.append(dict(symbol=symbol, name=name, asset_class=category, quantity=float(qty), cost_price=float(cp), current_price=float(price), as_of=as_of.isoformat(), market_value=float(value), cost=float(basis), pnl=float(value - basis), stale=stale))
    if not positions:
        raise ValueError("CSV没有持仓记录。")
    total_f, cost_f = float(total), float(cost)
    for p in positions:
        p["weight"] = p["market_value"] / total_f
    distribution = {c: sum(p["market_value"] for p in positions if p["asset_class"] == c) for c in CATEGORIES}
    largest = max((p for p in positions if p["asset_class"] != "cash"), key=lambda p: p["weight"], default=None)
    concentration = largest["weight"] if largest else 0.
    cash_weight = distribution["cash"] / total_f
    if concentration > .4:
        warnings.append("单一非现金持仓超过总资产40%，达到原型集中度提醒阈值；不等于违反适当性。")
    dates = sorted({p["as_of"] for p in positions})
    if len(dates) > 1:
        warnings.append("持仓价格日期不一致，合计为混合日期快照，不能当作同一交易日估值。")
    impact = sum(distribution[c] * SHOCKS[c] for c in CATEGORIES)
    facts = [
        dict(id="total", title="持仓总市值", value=f"¥{total_f:,.2f}", description="各项数量乘当前价后求和，包含现金。"),
        dict(id="pnl", title="浮动盈亏", value=f"¥{float(total-cost):+,.2f}", description="当前市值减账面成本；不含交易费用、分红及已实现收益。"),
        dict(id="concentration", title="最大非现金持仓占比", value=f"{concentration:.2%}", description="最大一项非现金持仓市值除以包含现金的总市值；不穿透基金底层。"),
        dict(id="cash", title="现金占比", value=f"{cash_weight:.2%}", description="资产类别标记为cash的市值占总资产比例。"),
        dict(id="scenario", title="静态情景影响", value=f"¥{impact:,.2f} / {impact/total_f:.2%}", description="按页面列明的假设跌幅作用于当前市值，无概率含义，不是收益预测或回测。"),
        dict(id="quality", title="价格日期与数据来源", value=f"{dates[0]} 至 {dates[-1]}；{source}", description=("存在陈旧价格，需要确认数据质量。" if any(p["stale"] for p in positions) else "未触发七个自然日陈旧阈值，但输入价格未经独立核实。") + ("持仓使用不同日期价格，合计为混合日期快照。" if len(dates) > 1 else "持仓价格日期一致。")),
    ]
    snapshot = json.dumps({"positions": positions, "source": source, "shocks": SHOCKS, "version": "1.1"}, sort_keys=True, ensure_ascii=False)
    report_id = "HOLD-" + hashlib.sha256(snapshot.encode()).hexdigest()[:12]
    return dict(positions=positions, total=total_f, cost=cost_f, pnl=float(total-cost), pnl_rate=float((total-cost)/cost) if cost else None, concentration=concentration, cash_weight=cash_weight, distribution=distribution, scenario_impact=impact, shocks=SHOCKS, warnings=warnings, facts=facts, source=source, created_at=today.isoformat(), generated_at=datetime.now().astimezone().isoformat(timespec="seconds"), report_id=report_id, limitation=LIMITATION)


def local_explanation(report: dict, question: str = "") -> dict:
    mapping = [("集中", "concentration"), ("风险", "concentration"), ("现金", "cash"), ("盈亏", "pnl"), ("收益", "pnl"), ("情景", "scenario"), ("下跌", "scenario"), ("日期", "quality"), ("数据", "quality")]
    ids = [fid for term, fid in mapping if term in question]
    if not question:
        ids = ["concentration", "cash", "pnl", "quality"]
    facts = [f for f in report["facts"] if f["id"] in ids]
    return dict(mode="local", summary="本地指标口径说明，未调用大模型。" if facts else "这里只解释已计算的持仓结构、盈亏口径、数据日期和静态情景，不提供买卖或未来收益判断。", items=[dict(factId=f["id"], explanation=f["description"]) for f in facts])


def markdown_text(value: str) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ")
    for char in "\\`*_[]<>|#!":
        text = text.replace(char, "\\" + char)
    return text


def export_report(report: dict, explanation: dict | None = None, history: list | None = None) -> str:
    lines = ["# FinPilot 持仓分析", "", f"快照：{report.get('report_id', '未记录')}；生成时间：{report.get('generated_at', report['created_at'])}", f"来源：{report['source']}；分析日期：{report['created_at']}", report["limitation"], "", "## 确定性指标"]
    lines += [f"- {f['title']}：{f['value']}。{f['description']}" for f in report["facts"]]
    lines += ["", "## 数据与风险提醒"] + [f"- {x}" for x in report["warnings"]]
    lines += ["", "## 静态情景假设"] + [f"- {CATEGORIES[c]}：{shock:.0%}" for c, shock in report["shocks"].items()]
    lines += ["", "## 持仓快照明细", "| 代码 | 名称 | 数量 | 成本价 | 当前价 | 市值 | 浮动盈亏 | 权重 | 价格日期 |", "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for p in report["positions"]:
        lines.append(f"| {markdown_text(p['symbol'])} | {markdown_text(p['name'])} | {p['quantity']:g} | {p['cost_price']:g} | {p['current_price']:g} | {p['market_value']:.2f} | {p['pnl']:.2f} | {p['weight']:.2%} | {p['as_of']} |")
    lookup = {f["id"]: f for f in report["facts"]}

    def add_explanation(data):
        lines.append(f"模式：{'AI生成（需核对）' if data.get('mode') == 'live' else '本地说明'}；模型：{markdown_text(data.get('model', '未调用'))}")
        lines.append(markdown_text(data["summary"]))
        lines.extend(f"- [{item['factId']}] {lookup[item['factId']]['value']}：{markdown_text(item['explanation'])}" for item in data["items"] if item["factId"] in lookup)

    if explanation:
        lines += ["", "## 最近一次成功解释"]
        add_explanation(explanation)
    current_history = [entry for entry in (history or []) if entry.get("report_id") == report.get("report_id")][-10:]
    if current_history:
        lines += ["", "## 当前快照追问记录（最近10次；每次独立作答）"]
        for i, entry in enumerate(current_history, 1):
            lines += ["", f"### 追问{i} · {entry['at']}", "问题：" + markdown_text(entry["question"])]
            if entry.get("error"):
                lines += ["本次未成功：" + markdown_text(entry["error"]) + "；未生成回答。"]
            else:
                add_explanation(entry["answer"])
    return "\n".join(lines) + "\n"
