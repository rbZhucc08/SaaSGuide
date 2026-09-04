"""Validate SaaSGuide JSON data against the static demo page."""

from __future__ import annotations

import json
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
GUIDE_FILE = PROJECT_DIR / "guide-data.json"
RISK_FILE = PROJECT_DIR / "risk-data.json"
HTML_FILE = PROJECT_DIR / "index.html"

GUIDE_REQUIRED_FIELDS = {
    "step": int,
    "target": str,
    "title": str,
    "description": str,
}

RISK_REQUIRED_FIELDS = {
    "id": str,
    "type": str,
    "level": str,
    "title": str,
    "summary": str,
    "description": str,
    "owner": str,
    "due": str,
    "overdue": bool,
    "impact": str,
    "status": str,
    "plan": list,
}

ALLOWED_ACTIONS = {"filter-high"}
ALLOWED_RISK_TYPES = {"high": "高风险", "medium": "中风险", "low": "低风险"}
ALLOWED_STATUSES = {"待处理", "处理中", "已处理"}


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.append(value)


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file), []
    except FileNotFoundError:
        return None, [f"缺少文件：{path.name}"]
    except json.JSONDecodeError as error:
        return None, [
            f"{path.name} 不是合法 JSON：第 {error.lineno} 行，第 {error.colno} 列"
        ]


def collect_html_ids(path: Path) -> tuple[set[str], list[str]]:
    try:
        html = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set(), [f"缺少文件：{path.name}"]

    collector = IdCollector()
    collector.feed(html)
    duplicates = sorted({item for item in collector.ids if collector.ids.count(item) > 1})
    errors = [f"index.html 存在重复 id：{item}" for item in duplicates]
    return set(collector.ids), errors


def check_required_fields(
    item: Any,
    required_fields: dict[str, type],
    location: str,
) -> list[str]:
    if not isinstance(item, dict):
        return [f"{location} 必须是对象"]

    errors: list[str] = []
    for field, expected_type in required_fields.items():
        if field not in item:
            errors.append(f"{location} 缺少字段：{field}")
            continue

        value = item[field]
        if type(value) is not expected_type:
            errors.append(
                f"{location}.{field} 类型错误，应为 {expected_type.__name__}"
            )
        elif expected_type is str and not value.strip():
            errors.append(f"{location}.{field} 不能为空")
    return errors


def validate_guide_data(data: Any, html_ids: set[str]) -> list[str]:
    if not isinstance(data, dict):
        return ["guide-data.json 顶层必须是对象"]

    errors: list[str] = []
    page_elements = data.get("pageElements")
    steps = data.get("guideSteps")

    if not isinstance(page_elements, dict) or not page_elements:
        errors.append("guide-data.json.pageElements 必须是非空对象")
        page_elements = {}

    element_ids: list[str] = []
    for key, element_id in page_elements.items():
        location = f"pageElements.{key}"
        if not isinstance(element_id, str) or not element_id.strip():
            errors.append(f"{location} 必须是非空字符串")
            continue
        element_ids.append(element_id)
        if element_id not in html_ids:
            errors.append(f"{location} 指向不存在的页面 id：{element_id}")

    duplicate_element_ids = sorted(
        {element_id for element_id in element_ids if element_ids.count(element_id) > 1}
    )
    for element_id in duplicate_element_ids:
        errors.append(f"pageElements 重复使用页面 id：{element_id}")

    if not isinstance(steps, list) or not steps:
        errors.append("guide-data.json.guideSteps 必须是非空列表")
        return errors

    step_numbers: list[int] = []
    targets: list[str] = []
    for index, step in enumerate(steps):
        location = f"guideSteps[{index}]"
        errors.extend(check_required_fields(step, GUIDE_REQUIRED_FIELDS, location))
        if not isinstance(step, dict):
            continue

        step_number = step.get("step")
        target = step.get("target")
        action = step.get("action")

        if type(step_number) is int:
            step_numbers.append(step_number)
        if isinstance(target, str):
            targets.append(target)
            if target not in page_elements:
                errors.append(f"{location}.target 未在 pageElements 中定义：{target}")
        if action is not None and action not in ALLOWED_ACTIONS:
            errors.append(f"{location}.action 不受支持：{action}")

    expected_steps = list(range(1, len(steps) + 1))
    if step_numbers != expected_steps:
        errors.append(
            f"guideSteps 步骤顺序错误，当前为 {step_numbers}，应为 {expected_steps}"
        )

    duplicate_targets = sorted(
        {target for target in targets if targets.count(target) > 1}
    )
    for target in duplicate_targets:
        errors.append(f"guideSteps 重复使用目标：{target}")

    return errors


def validate_risk_data(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["risk-data.json 顶层必须是对象"]

    risks = data.get("risks")
    if not isinstance(risks, list) or not risks:
        return ["risk-data.json.risks 必须是非空列表"]

    errors: list[str] = []
    risk_ids: list[str] = []

    for index, risk in enumerate(risks):
        location = f"risks[{index}]"
        errors.extend(check_required_fields(risk, RISK_REQUIRED_FIELDS, location))
        if not isinstance(risk, dict):
            continue

        risk_id = risk.get("id")
        risk_type = risk.get("type")
        level = risk.get("level")
        status = risk.get("status")
        due = risk.get("due")
        plan = risk.get("plan")
        avatar_class = risk.get("avatarClass", "")

        if isinstance(risk_id, str):
            risk_ids.append(risk_id)
        if isinstance(risk_type, str) and risk_type not in ALLOWED_RISK_TYPES:
            errors.append(f"{location}.type 不受支持：{risk_type}")
        elif risk_type in ALLOWED_RISK_TYPES and level != ALLOWED_RISK_TYPES[risk_type]:
            errors.append(
                f"{location}.level 与 type 不一致，应为 {ALLOWED_RISK_TYPES[risk_type]}"
            )
        if isinstance(status, str) and status not in ALLOWED_STATUSES:
            errors.append(f"{location}.status 不受支持：{status}")
        if not isinstance(avatar_class, str):
            errors.append(f"{location}.avatarClass 类型错误，应为 str")
        if isinstance(due, str):
            try:
                date.fromisoformat(due)
            except ValueError:
                errors.append(f"{location}.due 不是有效的 YYYY-MM-DD 日期：{due}")
        if isinstance(plan, list):
            if not plan:
                errors.append(f"{location}.plan 不能为空")
            elif any(not isinstance(item, str) or not item.strip() for item in plan):
                errors.append(f"{location}.plan 只能包含非空文字")

    duplicate_ids = sorted({risk_id for risk_id in risk_ids if risk_ids.count(risk_id) > 1})
    for risk_id in duplicate_ids:
        errors.append(f"risks 存在重复 id：{risk_id}")

    return errors


def validate_project(project_dir: Path = PROJECT_DIR) -> list[str]:
    html_ids, errors = collect_html_ids(project_dir / HTML_FILE.name)
    guide_data, guide_load_errors = load_json(project_dir / GUIDE_FILE.name)
    risk_data, risk_load_errors = load_json(project_dir / RISK_FILE.name)
    errors.extend(guide_load_errors)
    errors.extend(risk_load_errors)

    if guide_data is not None:
        errors.extend(validate_guide_data(guide_data, html_ids))
    if risk_data is not None:
        errors.extend(validate_risk_data(risk_data))
    return errors


def main() -> int:
    errors = validate_project()
    if errors:
        print(f"校验失败：发现 {len(errors)} 个问题")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1

    print("校验通过：guide-data.json、risk-data.json 与 index.html 一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
