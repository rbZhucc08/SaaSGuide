"""Offline tests for the DeepSeek risk assistant."""

from __future__ import annotations

import copy
import json
import unittest

from deepseek_ask_build import ModelOutputError
from deepseek_risk_assistant import analyze_risk, validate_risk_result


COMPLETE_RISK = {
    "id": "api-delay",
    "title": "第三方 API 联调延迟",
    "description": "供应商环境不稳定，联调延期三天，可能影响核心功能验收。",
    "level": "高风险",
    "impact": "支付与消息模块",
    "status": "待处理",
    "owner": "周航",
    "due": "2026-09-02",
    "plan": ["申请专属联调环境"],
}

VALID_PLAN = {
    "decision": "PLAN",
    "summary": "接口延期可能影响核心验收。",
    "suggestedLevel": "高风险",
    "priority": "立即处理",
    "rationale": ["已经延期三天", "影响支付与消息模块"],
    "actions": [
        {
            "step": 1,
            "action": "确认供应商可用联调时间。",
            "successSignal": "获得明确时间表。",
        },
        {
            "step": 2,
            "action": "准备本地模拟接口。",
            "successSignal": "关键流程可独立完成验收。",
        },
    ],
    "cautions": ["建议等级需要项目负责人确认。"],
}


class FakeClient:
    model = "deepseek-v4-flash"
    last_usage = {"total_tokens": 456}

    def __init__(self, response):
        self.response = response
        self.call_count = 0

    def create_json(self, _messages):
        self.call_count += 1
        return self.response if isinstance(self.response, str) else json.dumps(self.response, ensure_ascii=False)


class RiskAssistantTests(unittest.TestCase):
    def test_missing_risk_information_returns_local_ask(self) -> None:
        client = FakeClient(VALID_PLAN)
        result = analyze_risk({"id": "new", "title": "接口问题"}, client=client)
        self.assertEqual("ASK", result["decision"])
        self.assertEqual("local-precheck", result["source"])
        self.assertEqual(0, client.call_count)

    def test_valid_plan_is_accepted(self) -> None:
        result = analyze_risk(COMPLETE_RISK, client=FakeClient(VALID_PLAN))
        self.assertEqual("PLAN", result["decision"])
        self.assertEqual(456, result["usage"]["total_tokens"])

    def test_model_ask_is_accepted(self) -> None:
        response = {
            "decision": "ASK",
            "reason": "缺少影响说明",
            "questions": [{"field": "impact", "question": "会影响哪个里程碑？"}],
        }
        result = analyze_risk(COMPLETE_RISK, client=FakeClient(response))
        self.assertEqual("ASK", result["decision"])

    def test_invalid_priority_is_rejected(self) -> None:
        response = copy.deepcopy(VALID_PLAN)
        response["priority"] = "随便处理"
        with self.assertRaisesRegex(ModelOutputError, "priority"):
            analyze_risk(COMPLETE_RISK, client=FakeClient(response))

    def test_skipped_action_number_is_rejected(self) -> None:
        response = copy.deepcopy(VALID_PLAN)
        response["actions"][1]["step"] = 3
        with self.assertRaisesRegex(ModelOutputError, "步骤顺序错误"):
            analyze_risk(COMPLETE_RISK, client=FakeClient(response))

    def test_empty_success_signal_is_rejected(self) -> None:
        response = copy.deepcopy(VALID_PLAN)
        response["actions"][0]["successSignal"] = ""
        errors = validate_risk_result(response)
        self.assertTrue(any("successSignal" in error for error in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
