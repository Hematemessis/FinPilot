from pathlib import Path
from streamlit.testing.v1 import AppTest


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_snapshot_analysis_explanation_and_invalidation():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "holding_app.py"), default_timeout=20).run()
    assert not app.exception
    button(app, "分析持仓").click().run()
    assert not app.exception
    assert [m.value for m in app.metric][:2] == ["¥56,400.00", "¥+3,400.00"]
    button(app, "查看本地指标说明").click().run()
    assert not app.exception
    assert app.session_state["holding_explanation"]["mode"] == "local"
    app.radio[0].set_value("上传 CSV").run()
    assert "holding_report" not in app.session_state
    assert "holding_explanation" not in app.session_state
    assert not app.exception


def test_ai_requires_consent_and_configuration_without_losing_metrics():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "holding_app.py"), default_timeout=20).run()
    button(app, "分析持仓").click().run()
    app.toggle[0].set_value(True).run()
    button(app, "生成 AI 解释").click().run()
    assert any("确认允许" in err.value for err in app.error)
    app.checkbox[0].set_value(True).run()
    button(app, "生成 AI 解释").click().run()
    assert any("尚未配置" in err.value for err in app.error)
    assert len(app.metric) >= 4
    assert not app.exception


def test_multiple_questions_survive_failed_attempt_and_clear_on_new_input():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "holding_app.py"), default_timeout=20).run()
    button(app, "分析持仓").click().run()
    app.text_input(key="holding_question").set_value("集中度是什么意思？").run()
    button(app, "提交追问").click().run()
    app.text_input(key="holding_question").set_value("现金占比怎么计算？").run()
    button(app, "提交追问").click().run()
    assert len(app.session_state["holding_history"]) == 2
    app.toggle[0].set_value(True).run()
    button(app, "提交追问").click().run()
    history = app.session_state["holding_history"]
    assert len(history) == 3 and "error" in history[-1] and "answer" in history[0]
    assert not app.exception
    app.radio[0].set_value("上传 CSV").run()
    assert "holding_history" not in app.session_state


def test_failed_regeneration_preserves_last_success_with_error_label():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "holding_app.py"), default_timeout=20).run()
    button(app, "分析持仓").click().run()
    button(app, "查看本地指标说明").click().run()
    app.toggle[0].set_value(True).run()
    button(app, "生成 AI 解释").click().run()
    assert app.session_state["holding_explanation"]["mode"] == "local"
    assert app.session_state["holding_generation_error"]
    assert any("上次成功解释" in caption.value for caption in app.caption)
    assert not app.exception


def test_existing_v1_session_needs_reanalysis_instead_of_crashing():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "holding_app.py"), default_timeout=20).run()
    button(app, "分析持仓").click().run()
    del app.session_state["holding_report"]["report_id"]
    app.run()
    assert not app.exception
    assert "holding_report" not in app.session_state
    assert any("模块已更新" in message.value for message in app.info)
