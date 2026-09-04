"""Offline tests for the DeepSeek ASK / BUILD stage."""

from __future__ import annotations

import copy
import json
import os
import unittest
from unittest.mock import patch

from deepseek_ask_build import (
    DeepSeekClient,
    DeepSeekError,
    ModelOutputError,
    build_messages,
    evaluate_brief,
)


COMPLETE_BRIEF = {
    "featureName": "项目风险看板引导",
    "featureBrief": "帮助项目经理发现、查看并处理当前项目风险。",
    "targetUsers": "首次使用风险看板的项目经理",
    "entryPoint": "项目详情页的风险看板入口",
    "operationSteps": [
        "查看风险总数",
        "筛选高风险",
        "查看风险详情",
        "标记为已处理",
    ],
    "successState": "选中的风险显示为已处理并完成引导",
    "pageElements": {
        "riskTotal": "risk-total",
        "highRiskFilter": "high-risk-filter",
        "riskDetail": "risk-detail",
        "resolveRisk": "resolve-risk",
    },
}

VALID_BUILD = {
    "decision": "BUILD",
    "reason": "信息完整且步骤可以映射到页面元素",
    "guide": {
        "pageElements": COMPLETE_BRIEF["pageElements"],
        "guideSteps": [
            {
                "step": 1,
                "target": "riskTotal",
                "title": "先看风险总数",
                "description": "确认当前项目的风险规模。",
            },
            {
                "step": 2,
                "target": "highRiskFilter",
                "title": "筛选高风险",
                "description": "聚焦需要优先处理的风险。",
                "action": "filter-high",
            },
            {
                "step": 3,
                "target": "riskDetail",
                "title": "查看风险详情",
                "description": "了解影响、责任人与应对计划。",
            },
            {
                "step": 4,
                "target": "resolveRisk",
                "title": "完成处理",
                "description": "确认解决后标记为已处理。",
            },
        ],
    },
}


class FakeClient:
    model = "deepseek-v4-flash"

    def __init__(self, response: dict | str) -> None:
        self.response = response
        self.call_count = 0

    def create_json(self, messages: list[dict[str, str]]) -> str:
        self.call_count += 1
        if isinstance(self.response, str):
            return self.response
        return json.dumps(self.response, ensure_ascii=False)


class AskBuildTests(unittest.TestCase):
    def test_missing_fields_return_local_ask_without_api_call(self) -> None:
        client = FakeClient(VALID_BUILD)
        result = evaluate_brief({"featureName": "风险引导"}, client)
        self.assertEqual("ASK", result["decision"])
        self.assertEqual("local-precheck", result["source"])
        self.assertEqual(0, client.call_count)
        self.assertTrue(any(q["field"] == "targetUsers" for q in result["questions"]))

    def test_complete_brief_accepts_valid_build(self) -> None:
        client = FakeClient(VALID_BUILD)
        result = evaluate_brief(COMPLETE_BRIEF, client)
        self.assertEqual("BUILD", result["decision"])
        self.assertEqual("deepseek-api", result["source"])
        self.assertEqual(1, client.call_count)

    def test_model_can_still_ask_about_ambiguous_content(self) -> None:
        response = {
            "decision": "ASK",
            "reason": "成功状态含糊",
            "questions": [
                {"field": "successState", "question": "页面出现什么变化才算成功？"}
            ],
        }
        result = evaluate_brief(COMPLETE_BRIEF, FakeClient(response))
        self.assertEqual("ASK", result["decision"])

    def test_invalid_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(ModelOutputError, "不是合法 JSON"):
            evaluate_brief(COMPLETE_BRIEF, FakeClient("not-json"))

    def test_invented_page_element_is_rejected(self) -> None:
        response = copy.deepcopy(VALID_BUILD)
        response["guide"]["pageElements"]["riskTotal"] = "invented-id"
        with self.assertRaisesRegex(ModelOutputError, "不得虚构页面元素"):
            evaluate_brief(COMPLETE_BRIEF, FakeClient(response))

    def test_duplicate_ask_field_is_rejected(self) -> None:
        response = {
            "decision": "ASK",
            "reason": "需要确认用户",
            "questions": [
                {"field": "targetUsers", "question": "用户是谁？"},
                {"field": "targetUsers", "question": "请再次说明用户。"},
            ],
        }
        with self.assertRaisesRegex(ModelOutputError, "重复询问"):
            evaluate_brief(COMPLETE_BRIEF, FakeClient(response))

    def test_request_explicitly_uses_json_mode(self) -> None:
        captured: dict = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                envelope = {"choices": [{"message": {"content": "{}"}}]}
                return json.dumps(envelope).encode("utf-8")

        def opener(request, timeout):
            captured.update(json.loads(request.data.decode("utf-8")))
            captured["timeout"] = timeout
            return FakeResponse()

        DeepSeekClient(api_key="test-only", opener=opener).create_json(
            build_messages(COMPLETE_BRIEF)
        )
        self.assertEqual({"type": "json_object"}, captured["response_format"])
        self.assertFalse(captured["stream"])
        self.assertIn("json", build_messages(COMPLETE_BRIEF)[0]["content"])

    def test_missing_key_stops_before_network(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            client = DeepSeekClient(api_key="")
            with self.assertRaisesRegex(DeepSeekError, "未配置"):
                client.create_json(build_messages(COMPLETE_BRIEF))


if __name__ == "__main__":
    unittest.main(verbosity=2)
