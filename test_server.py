"""Offline integration tests for the local Flask workflow."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from deepseek_ask_build import DeepSeekError, ModelOutputError
from server import create_app
from test_deepseek_ask_build import COMPLETE_BRIEF, VALID_BUILD
from test_risk_assistant import COMPLETE_RISK, VALID_PLAN


class ServerTests(unittest.TestCase):
    def make_client(self, evaluator, risk_evaluator=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name)
        risk_file = output_dir / "risk-data.json"
        source_risk_text = (Path(__file__).resolve().parent / "risk-data.json").read_text(
            encoding="utf-8"
        )
        self.initial_risk_count = len(json.loads(source_risk_text)["risks"])
        risk_file.write_text(source_risk_text, encoding="utf-8")
        options = {
            "output_dir": output_dir,
            "evaluator": evaluator,
            "risk_file": risk_file,
        }
        if risk_evaluator is not None:
            options["risk_evaluator"] = risk_evaluator
        app = create_app(**options)
        app.config["TESTING"] = True
        app.logger.disabled = True
        return app.test_client(), output_dir

    def test_builder_page_is_served(self) -> None:
        client, _ = self.make_client(lambda brief: {})
        response = client.get("/builder")
        self.assertEqual(200, response.status_code)
        self.assertIn("AI 引导生成器", response.get_data(as_text=True))
        response.close()

    def test_non_json_request_is_rejected(self) -> None:
        client, _ = self.make_client(lambda brief: {})
        response = client.post("/api/guides/generate", data="plain text")
        self.assertEqual(400, response.status_code)

    def test_ask_is_returned_and_only_logged(self) -> None:
        result = {
            "decision": "ASK",
            "reason": "入口含糊",
            "questions": [{"field": "entryPoint", "question": "入口在哪里？"}],
            "source": "deepseek-api",
            "model": "deepseek-v4-flash",
        }
        client, output_dir = self.make_client(lambda brief: result.copy())
        response = client.post("/api/guides/generate", json=COMPLETE_BRIEF)
        self.assertEqual(200, response.status_code)
        self.assertEqual("ASK", response.get_json()["decision"])
        self.assertTrue((output_dir / "run-log.jsonl").exists())
        self.assertFalse((output_dir / "guide-data.generated.json").exists())

    def test_build_is_saved_as_json_and_html(self) -> None:
        result = {
            **VALID_BUILD,
            "source": "deepseek-api",
            "model": "deepseek-v4-flash",
            "usage": {"total_tokens": 321},
        }
        client, output_dir = self.make_client(lambda brief: result.copy())
        response = client.post("/api/guides/generate", json=COMPLETE_BRIEF)
        data = response.get_json()
        self.assertEqual(200, response.status_code)
        self.assertIn("artifacts", data)
        saved = json.loads(
            (output_dir / "guide-data.generated.json").read_text(encoding="utf-8")
        )
        self.assertEqual(4, len(saved["guideSteps"]))
        self.assertEqual(321, saved["meta"]["usage"]["total_tokens"])
        self.assertTrue((output_dir / "guide-preview.generated.html").exists())

    def test_generated_html_escapes_user_text(self) -> None:
        result = {
            **VALID_BUILD,
            "source": "deepseek-api",
            "model": "deepseek-v4-flash",
        }
        unsafe_brief = {**COMPLETE_BRIEF, "featureName": "<script>alert(1)</script>"}
        client, output_dir = self.make_client(lambda brief: result.copy())
        response = client.post("/api/guides/generate", json=unsafe_brief)
        self.assertEqual(200, response.status_code)
        preview = (output_dir / "guide-preview.generated.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", preview)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", preview)

    def test_model_output_error_is_reported_without_saving(self) -> None:
        def fail(_brief):
            raise ModelOutputError("步骤顺序错误")

        client, output_dir = self.make_client(fail)
        response = client.post("/api/guides/generate", json=COMPLETE_BRIEF)
        self.assertEqual(502, response.status_code)
        self.assertIn("步骤顺序错误", response.get_json()["error"])
        self.assertFalse((output_dir / "run-log.jsonl").exists())
        self.assertFalse((output_dir / "guide-data.generated.json").exists())
        self.assertFalse((output_dir / "guide-preview.generated.html").exists())

    def test_deepseek_error_is_reported_without_exposing_key(self) -> None:
        def fail(_brief):
            raise DeepSeekError("DeepSeek 服务繁忙，请稍后重试")

        client, _ = self.make_client(fail)
        response = client.post("/api/guides/generate", json=COMPLETE_BRIEF)
        self.assertEqual(502, response.status_code)
        self.assertEqual("DeepSeek 服务繁忙，请稍后重试", response.get_json()["error"])

    def test_risk_plan_is_saved(self) -> None:
        result = {
            **VALID_PLAN,
            "source": "deepseek-api",
            "model": "deepseek-v4-flash",
            "usage": {"total_tokens": 654},
        }
        client, output_dir = self.make_client(
            lambda brief: {}, lambda risk, note: result.copy()
        )
        response = client.post(
            "/api/risks/analyze", json={"risk": COMPLETE_RISK, "contextNote": ""}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("PLAN", response.get_json()["decision"])
        saved = json.loads(
            (output_dir / "latest-risk-analysis.json").read_text(encoding="utf-8")
        )
        self.assertEqual("api-delay", saved["meta"]["riskId"])
        self.assertEqual(2, len(saved["analysis"]["actions"]))
        self.assertTrue((output_dir / "risk-assistant-run-log.jsonl").exists())

    def test_risk_ask_does_not_create_plan_file(self) -> None:
        result = {
            "decision": "ASK",
            "reason": "信息不足",
            "questions": [{"field": "impact", "question": "会影响什么？"}],
            "source": "deepseek-api",
            "model": "deepseek-v4-flash",
        }
        client, output_dir = self.make_client(
            lambda brief: {}, lambda risk, note: result.copy()
        )
        response = client.post(
            "/api/risks/analyze", json={"risk": COMPLETE_RISK, "contextNote": ""}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("ASK", response.get_json()["decision"])
        self.assertFalse((output_dir / "latest-risk-analysis.json").exists())

    def test_risk_request_requires_risk_object(self) -> None:
        client, _ = self.make_client(lambda brief: {})
        response = client.post("/api/risks/analyze", json={"risk": "wrong"})
        self.assertEqual(400, response.status_code)

    def test_risk_context_length_is_limited(self) -> None:
        client, _ = self.make_client(lambda brief: {})
        response = client.post(
            "/api/risks/analyze",
            json={"risk": COMPLETE_RISK, "contextNote": "x" * 2001},
        )
        self.assertEqual(400, response.status_code)

    def test_confirmed_low_risk_is_saved_with_backup(self) -> None:
        client, output_dir = self.make_client(lambda brief: {})
        analysis = deepcopy(VALID_PLAN)
        analysis["suggestedLevel"] = "低风险"
        draft = {
            "title": "测试环境证书即将过期",
            "description": "测试环境证书将在两天后过期，可能导致接口联调中断。",
            "impact": "登录与接口测试",
            "owner": "陈宁",
            "due": "2026-12-31",
        }

        response = client.post("/api/risks", json={"draft": draft, "analysis": analysis})
        data = response.get_json()
        self.assertEqual(201, response.status_code)
        self.assertEqual("low", data["risk"]["type"])
        self.assertEqual("低风险", data["risk"]["level"])
        self.assertEqual("待处理", data["risk"]["status"])

        saved = json.loads((output_dir / "risk-data.json").read_text(encoding="utf-8"))
        self.assertEqual(self.initial_risk_count + 1, len(saved["risks"]))
        self.assertEqual(data["risk"]["id"], saved["risks"][-1]["id"])
        self.assertEqual(1, len(list((output_dir / "backups").glob("*.backup.json"))))

    def test_ask_cannot_be_saved_as_risk(self) -> None:
        client, output_dir = self.make_client(lambda brief: {})
        response = client.post(
            "/api/risks",
            json={
                "draft": {
                    "title": "待补充风险",
                    "description": "信息还不完整。",
                    "impact": "未知",
                    "owner": "陈宁",
                    "due": "2026-12-31",
                },
                "analysis": {
                    "decision": "ASK",
                    "reason": "需要补充信息",
                    "questions": [{"field": "impact", "question": "影响什么？"}],
                },
            },
        )
        self.assertEqual(400, response.status_code)
        saved = json.loads((output_dir / "risk-data.json").read_text(encoding="utf-8"))
        self.assertEqual(self.initial_risk_count, len(saved["risks"]))

    def test_invalid_due_date_is_rejected(self) -> None:
        client, output_dir = self.make_client(lambda brief: {})
        response = client.post(
            "/api/risks",
            json={
                "draft": {
                    "title": "日期错误风险",
                    "description": "用于验证日期校验。",
                    "impact": "测试",
                    "owner": "陈宁",
                    "due": "2026-02-30",
                },
                "analysis": VALID_PLAN,
            },
        )
        self.assertEqual(400, response.status_code)
        saved = json.loads((output_dir / "risk-data.json").read_text(encoding="utf-8"))
        self.assertEqual(self.initial_risk_count, len(saved["risks"]))

    def test_create_risk_requires_draft_and_analysis(self) -> None:
        client, _ = self.make_client(lambda brief: {})
        response = client.post("/api/risks", json={"draft": {}})
        self.assertEqual(400, response.status_code)

    def test_oversized_request_is_rejected(self) -> None:
        client, _ = self.make_client(lambda brief: {})
        response = client.post(
            "/api/guides/generate",
            data="x" * (65 * 1024),
            content_type="application/json",
        )
        self.assertEqual(413, response.status_code)

    def test_guide_output_failure_is_reported(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        blocked_output = Path(temporary.name) / "not-a-directory"
        blocked_output.write_text("occupied", encoding="utf-8")
        app = create_app(
            output_dir=blocked_output,
            evaluator=lambda brief: {**VALID_BUILD, "source": "test"},
            risk_file=Path(__file__).resolve().parent / "risk-data.json",
        )
        app.config["TESTING"] = True
        app.logger.disabled = True
        response = app.test_client().post("/api/guides/generate", json=COMPLETE_BRIEF)
        self.assertEqual(500, response.status_code)
        self.assertIn("保存失败", response.get_json()["error"])

    def test_missing_risk_file_is_reported_without_creating_data(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        app = create_app(
            output_dir=root / "generated",
            evaluator=lambda brief: {},
            risk_file=root / "missing-risk-data.json",
        )
        app.config["TESTING"] = True
        app.logger.disabled = True
        draft = {
            "title": "测试风险",
            "description": "用于检查风险文件缺失时是否安全停止。",
            "impact": "测试范围",
            "owner": "测试人",
            "due": "2026-12-31",
        }
        response = app.test_client().post(
            "/api/risks", json={"draft": draft, "analysis": VALID_PLAN}
        )
        self.assertEqual(500, response.status_code)
        self.assertFalse((root / "missing-risk-data.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
