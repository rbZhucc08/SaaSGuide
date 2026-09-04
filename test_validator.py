"""Automated tests for the SaaSGuide data validator."""

from __future__ import annotations

import copy
import json
import unittest

from validate_data import (
    GUIDE_FILE,
    HTML_FILE,
    RISK_FILE,
    collect_html_ids,
    validate_guide_data,
    validate_project,
    validate_risk_data,
)


class ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guide_data = json.loads(GUIDE_FILE.read_text(encoding="utf-8"))
        cls.risk_data = json.loads(RISK_FILE.read_text(encoding="utf-8"))
        cls.html_ids, cls.html_errors = collect_html_ids(HTML_FILE)

    def test_current_project_is_valid(self) -> None:
        self.assertEqual([], validate_project())

    def test_missing_guide_field_is_rejected(self) -> None:
        data = copy.deepcopy(self.guide_data)
        del data["guideSteps"][0]["title"]
        errors = validate_guide_data(data, self.html_ids)
        self.assertTrue(any("缺少字段：title" in error for error in errors))

    def test_duplicate_step_is_rejected(self) -> None:
        data = copy.deepcopy(self.guide_data)
        data["guideSteps"][1]["step"] = 1
        errors = validate_guide_data(data, self.html_ids)
        self.assertTrue(any("步骤顺序错误" in error for error in errors))

    def test_missing_page_target_is_rejected(self) -> None:
        data = copy.deepcopy(self.guide_data)
        data["pageElements"]["riskTotal"] = "missing-target"
        errors = validate_guide_data(data, self.html_ids)
        self.assertTrue(any("不存在的页面 id" in error for error in errors))

    def test_invalid_risk_status_is_rejected(self) -> None:
        data = copy.deepcopy(self.risk_data)
        data["risks"][0]["status"] = "未知状态"
        errors = validate_risk_data(data)
        self.assertTrue(any("status 不受支持" in error for error in errors))

    def test_duplicate_risk_id_is_rejected(self) -> None:
        data = copy.deepcopy(self.risk_data)
        data["risks"][1]["id"] = data["risks"][0]["id"]
        errors = validate_risk_data(data)
        self.assertTrue(any("重复 id" in error for error in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
