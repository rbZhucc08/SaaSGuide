"""跑一次真实飞书同步，并打印归一化结果，用于确认日期字段是否被正确处理。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.connectors.feishu_bitable import FeishuBitableClient, sync_snapshot  # noqa: E402

MAPPING = {
    "project_id": "项目编号", "project_name": "项目名称", "task_id": "任务编号", "task_name": "任务名称",
    "owner": "负责人", "due_date": "截止日期", "status": "状态", "updated_at": "更新时间",
}


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        value = value.strip().strip('"').strip("'")
        if value:
            values[key.strip()] = value
    return values


def main() -> None:
    env = load_env()
    client = FeishuBitableClient(
        app_id=env["FEISHU_APP_ID"],
        app_secret=env["FEISHU_APP_SECRET"],
        app_token=env["FEISHU_BITABLE_APP_TOKEN"],
        table_id=env["FEISHU_BITABLE_TABLE_ID"],
    )
    target = ROOT / "generated" / "connectors" / "feishu" / "records.json"
    result = sync_snapshot(client, MAPPING, target)
    print("同步结果（不显示源记录标识符）：")
    print(json.dumps({key: result[key] for key in ("fetched_count", "applied_count", "stored_count", "writeback")}, ensure_ascii=False, indent=2))
    snapshot = json.loads(target.read_text(encoding="utf-8"))
    print(f"\n共存储 {len(snapshot['records'])} 条：\n")
    for index, item in enumerate(snapshot["records"], start=1):
        print(f"  记录 {index}: 截止={item['due_date']:<16} 状态={item['status']}")
    print("\n判断：")
    sample = snapshot["records"][0]["due_date"] if snapshot["records"] else ""
    if sample.isdigit():
        print(f"  ❌ due_date 是纯数字字符串 '{sample}'，不是 YYYY-MM-DD —— 规则引擎的日期比较会失效")
    else:
        print(f"  ✅ due_date 看起来是日期字符串 '{sample}'")


if __name__ == "__main__":
    main()
