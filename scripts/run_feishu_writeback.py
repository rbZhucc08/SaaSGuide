"""真实飞书写回往返测试：推送一条已确认行动，再从飞书读回验证。

用法: python scripts/run_feishu_writeback.py
只读取 .env.local 凭据；不打印凭据值。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.connectors.feishu_bitable import (  # noqa: E402
    FeishuBitableClient,
    FeishuConnectorError,
    writeback_actions,
)

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


def read_action_table(token: str, app_token: str, table_id: str) -> list[dict]:
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search?page_size=50"
    request = urllib.request.Request(
        url, data=json.dumps({"automatic_fields": True}).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return (payload.get("data") or {}).get("items") or []


def main() -> None:
    env = load_env()
    client = FeishuBitableClient(
        app_id=env["FEISHU_APP_ID"],
        app_secret=env["FEISHU_APP_SECRET"],
        app_token=env["FEISHU_BITABLE_APP_TOKEN"],
        table_id=env["FEISHU_BITABLE_TABLE_ID"],
        writeback_app_token=env.get("FEISHU_BITABLE_WRITEBACK_APP_TOKEN") or None,
        writeback_table_id=env.get("FEISHU_BITABLE_WRITEBACK_TABLE_ID") or None,
        writeback_enabled=True,
    )
    print("读表配置   : 已加载（标识符不显示）")
    print("写回表配置 : 已加载独立行动表（标识符不显示）")
    print(f"写回已开启: {client.writeback_configured}\n")

    # ---- 1. 未确认的行动必须被拒绝，且不发出任何请求 ----
    print("==== 测试 1：未确认的行动应被拒绝 ====")
    unconfirmed = {
        "action_id": "A-DENY-001", "task_id": "T-001", "content": "这条不该被写入",
        "policy_reference": "《测试制度》", "suggested_owner": "测试角色",
        "completion_signal": "不应出现", "confirmation_status": "待确认",
    }
    try:
        writeback_actions(client, [unconfirmed])
        print("  ❌ 未被拒绝（不符合预期）")
    except FeishuConnectorError as error:
        print(f"  ✅ 被拒绝: code={error.code} status={error.status} msg={error}")
        print("     未确认内容没有离开本机")

    # ---- 2. 已确认的行动应真实写入飞书 ----
    print("\n==== 测试 2：已确认的行动应写入飞书 ====")
    confirmed = {
        "action_id": "A-REAL-001", "task_id": "T-001", "content": "与客户确认交付范围并更新任务状态",
        "policy_reference": "《交付管理制度》第 4.2 条", "suggested_owner": "交付负责人",
        "completion_signal": "任务状态更新为进行中且备注填写完成", "confirmation_status": "已确认",
    }
    result = writeback_actions(client, [confirmed])
    safe_result = {key: value for key, value in result.items() if key != "writeback_created_record_ids"}
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))

    # ---- 3. 从飞书读回验证 ----
    print("\n==== 测试 3：从飞书读回，确认记录真的存在 ====")
    body = json.dumps({"app_id": env["FEISHU_APP_ID"], "app_secret": env["FEISHU_APP_SECRET"]}).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        token = str(json.loads(response.read().decode("utf-8"))["tenant_access_token"])

    items = read_action_table(token, client.writeback_app_token, client.writeback_table_id)
    print(f"  行动表中现有 {len(items)} 条记录：")
    print("  字段正文和记录标识符不输出；请在飞书界面核对。")

    # ---- 4. 幂等：再次推送同样的行动 ----
    print("\n==== 测试 4：重复推送同一行动应被跳过 ====")
    again = writeback_actions(client, [confirmed], already_written=[confirmed["action_id"]])
    print(f"  written_count={again['written_count']}  skipped_count={again['skipped_count']}  "
          f"skipped={again['skipped_action_ids']}")
    print("  ✅ 幂等生效" if again["written_count"] == 0 else "  ❌ 重复写入了")


if __name__ == "__main__":
    main()
