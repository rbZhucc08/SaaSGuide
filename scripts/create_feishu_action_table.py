"""在已有 base 中创建「AI 待确认行动」表，并写入表头字段。

用法: python scripts/create_feishu_action_table.py
读取 .env.local 中的 FEISHU_BITABLE_APP_TOKEN，创建后打印新表的 table_id。
"""
from __future__ import annotations

import json
import argparse
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION_TABLE_NAME = "AI 待确认行动"
FIELDS = (
    ("行动编号", 1), ("关联任务", 1), ("建议内容", 1), ("制度依据", 1),
    ("建议负责人", 1), ("完成信号", 1), ("确认状态", 1), ("写入时间", 1),
)


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


def call(url: str, token: str, method: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, {"raw": raw}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-identifiers", action="store_true", help="创建后显示 table_id，便于写入本机环境文件")
    args = parser.parse_args()
    env = load_env()
    body = json.dumps({"app_id": env.get("FEISHU_APP_ID", ""), "app_secret": env.get("FEISHU_APP_SECRET", "")}).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        token = str(json.loads(response.read().decode("utf-8")).get("tenant_access_token") or "")

    app_token = env.get("FEISHU_BITABLE_APP_TOKEN", "")
    base = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}"

    # 先看是否已存在同名表
    status, payload = call(f"{base}/tables?page_size=100", token, "GET")
    existing = {item.get("name"): item.get("table_id") for item in (payload.get("data") or {}).get("items") or []}
    if ACTION_TABLE_NAME in existing:
        print(f"已存在同名数据表：{ACTION_TABLE_NAME}")
        if args.show_identifiers:
            print(f"table_id={existing[ACTION_TABLE_NAME]}")
        print("无需重复创建。")
        return
    print(f"现有数据表：{len(existing)} 张（标识符不显示）\n")

    status, payload = call(f"{base}/tables", token, "POST", {"table": {"name": ACTION_TABLE_NAME, "default_view_name": "待确认", "fields": [
        {"field_name": name, "type": field_type} for name, field_type in FIELDS
    ]}})
    print(f"创建数据表 HTTP={status}")
    if payload.get("code") != 0:
        print(f"code={payload.get('code')} msg={payload.get('msg')}")
        print(json.dumps(payload, ensure_ascii=False)[:400])
        print("\n若提示缺权限，请到开发者后台为应用开通「查看、评论、编辑和管理多维表格」的写入能力后重试。")
        return

    table_id = payload["data"]["table_id"]
    print(f"\n创建成功！")
    print(f"  name     = {ACTION_TABLE_NAME}")
    if args.show_identifiers:
        print(f"  table_id = {table_id}")
        print("\n写入 .env.local：")
        print(f"FEISHU_BITABLE_WRITEBACK_TABLE_ID={table_id}")
    else:
        print("  table_id 已隐藏；需要配置时用 --show-identifiers 重新运行")
    print("FEISHU_BITABLE_WRITEBACK_ENABLED=1")


if __name__ == "__main__":
    main()
