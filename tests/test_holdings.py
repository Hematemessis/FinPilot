from datetime import date
import json
import pytest

from advisor.holdings import analyze_holdings, example_csv, local_explanation, export_report
from advisor.holding_model import config_for, validate_explanation, explain

DAY = date(2026, 10, 8)


def test_hand_calculated_totals_and_scenario():
    report = analyze_holdings(example_csv(DAY), today=DAY)
    assert report["total"] == 56400
    assert report["cost"] == 53000
    assert report["pnl"] == 3400
    assert report["concentration"] == pytest.approx(24000 / 56400)
    assert report["cash_weight"] == pytest.approx(10000 / 56400)
    assert report["scenario_impact"] == pytest.approx(-7152)
    assert sum(p["weight"] for p in report["positions"]) == pytest.approx(1)


@pytest.mark.parametrize("old,new", [("1000,20,24", "-1,20,24"), ("1000,20,24", "NaN,20,24"), ("1000,20,24", "1,20,Infinity"), ("1000,20,24", "1e-10000,20,24"), (",CNY", ",USD"), ("2026-10-08", "2026-10-09"), ("2026-10-08", "2026-02-30"), (",stock,", ",option,")])
def test_invalid_inputs_are_rejected(old, new):
    with pytest.raises(ValueError):
        analyze_holdings(example_csv(DAY).replace(old, new), today=DAY)


def test_duplicate_and_empty_csv():
    csv = example_csv(DAY)
    with pytest.raises(ValueError, match="重复"):
        analyze_holdings(csv + csv.splitlines()[1] + "\n", today=DAY)
    with pytest.raises(ValueError):
        analyze_holdings(csv.splitlines()[0], today=DAY)


def test_cash_only_zero_cost_and_stale_dates():
    text = "symbol,name,asset_class,quantity,cost_price,current_price,as_of\nCASH,现金,cash,100,0,1,2026-09-01\n"
    report = analyze_holdings(text, today=DAY)
    assert report["concentration"] == 0
    assert report["pnl_rate"] is None
    assert report["scenario_impact"] == 0
    assert len(report["warnings"]) == 1


def test_local_mode_and_export_label():
    report = analyze_holdings(example_csv(DAY), today=DAY, source="自制示例")
    explanation = local_explanation(report, "集中度是什么？")
    assert explanation["mode"] == "local"
    assert explanation["items"][0]["factId"] == "concentration"
    text = export_report(report, explanation)
    assert "56,400.00" in text and "未调用大模型" in text and "自制示例" in text


def test_config_protects_secret_transport():
    assert config_for("https://example.com/v1", "test", "synthetic")["endpoint"].endswith("/v1/chat/completions")
    for url in ["http://example.com/v1", "https://a:b@example.com/v1", "https://example.com/?token=x", "file:///x"]:
        with pytest.raises(ValueError):
            config_for(url, "test", "synthetic")


@pytest.mark.parametrize("item", [{"factId":"fake","explanation":"集中度需要关注。"}, {"factId":"total","explanation":"预计收益20%。"}, {"factId":"total","explanation":"建议买入某股票。"}])
def test_bad_model_output_rejected(item):
    with pytest.raises(ValueError):
        validate_explanation(json.dumps({"summary":"解释", "items":[item]}, ensure_ascii=False), analyze_holdings(example_csv(DAY), today=DAY)["facts"])


def test_optional_model_receives_facts_not_raw_positions():
    report = analyze_holdings(example_csv(DAY), today=DAY)
    seen = {}

    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def iter_content(self, size):
            yield json.dumps({"choices":[{"message":{"content":json.dumps({"summary":"集中度可用于理解单一资产暴露。","items":[{"factId":"concentration","explanation":"占比反映该资产对总市值的影响。"}]}, ensure_ascii=False)}}]}, ensure_ascii=False).encode()

    def post(url, **kwargs):
        seen.update(kwargs)
        return Response()

    result = explain(report, config_for("https://example.com/v1", "test", "synthetic"), post=post)
    assert result["mode"] == "live"
    payload = json.loads(seen["json"]["messages"][1]["content"])
    assert "facts" in payload and "positions" not in payload
    assert seen["allow_redirects"] is False


def test_snapshot_changes_with_input_and_export_contains_only_matching_history():
    report = analyze_holdings(example_csv(DAY), today=DAY)
    changed = analyze_holdings(example_csv(DAY).replace("1000,20,24", "1000,20,25"), today=DAY)
    assert changed["report_id"] != report["report_id"]
    assert analyze_holdings(example_csv(DAY), today=DAY)["report_id"] == report["report_id"]
    answer = local_explanation(report, "现金占比？")
    history = [
        {"report_id": report["report_id"], "at": "test", "question": "现金占比？", "answer": answer},
        {"report_id": report["report_id"], "at": "test", "question": "集中度？", "error": "模型请求超时"},
        {"report_id": changed["report_id"], "at": "test", "question": "不应混入的旧快照问题", "answer": answer},
    ]
    text = export_report(report, answer, history)
    assert "持仓快照明细" in text and "自制股票甲" in text
    assert "现金占比？" in text and "模型请求超时" in text
    assert "不应混入" not in text


def test_stale_and_mixed_dates_are_explicit_in_model_facts():
    text = example_csv(DAY).replace("1000,20,24,2026-10-08", "1000,20,24,2026-09-01")
    report = analyze_holdings(text, today=DAY)
    fact = next(f for f in report["facts"] if f["id"] == "quality")
    assert "陈旧" in fact["description"] and "混合日期" in fact["description"]


def test_fenced_json_supported_but_bad_id_type_and_duplicate_id_rejected():
    facts = analyze_holdings(example_csv(DAY), today=DAY)["facts"]
    item = {"factId": "cash", "explanation": "现金比例反映当前资产的流动性结构。"}
    data = {"summary": "解释当前现金占比。", "items": [item]}
    assert validate_explanation("```json\n" + json.dumps(data, ensure_ascii=False) + "\n```", facts)["mode"] == "live"
    for items in [[{**item, "factId": []}], [item, item]]:
        with pytest.raises(ValueError):
            validate_explanation(json.dumps({**data, "items": items}), facts)


def test_export_escapes_user_markdown_and_does_not_create_remote_images():
    report = analyze_holdings(example_csv(DAY), today=DAY)
    history = [{"report_id":report["report_id"], "at":"test", "question":"![test](https://example.com/x)", "answer":local_explanation(report)}]
    text = export_report(report, history=history)
    assert "\\!\\[test\\]" in text
