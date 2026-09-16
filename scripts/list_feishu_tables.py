"""列出指定多维表格内的数据表，输出真实的 table_id。

用法: python scripts/list_feishu_tables.py [app_token]
不传 app_token 时使用 .env.local 中的 FEISHU_BITABLE_APP_TOKEN。
"""
from __future__ import annotations

import json
import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    parser = argparse.ArgumentParser()
    parser.add_argument("app_token", nargs="?")
    parser.add_argument("--show-identifiers", action="store_true")
    args = parser.parse_args()
    env = load_env()
    app_token = args.app_token.strip() if args.app_token else env.get("FEISHU_BITABLE_APP_TOKEN", "")
    if not app_token:
        print("缺少 app_token")
        raise SystemExit(2)

    body = json.dumps({"app_id": env.get("FEISHU_APP_ID", ""), "app_secret": env.get("FEISHU_APP_SECRET", "")}).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        token = str(json.loads(response.read().decode("utf-8")).get("tenant_access_token") or "")

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?page_size=100"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print(f"HTTP={error.code} {error.read().decode('utf-8', errors='replace')[:400]}")
        return

    print("app_token = [已配置；不显示]")
    if payload.get("code") != 0:
        print(f"查询失败 code={payload.get('code')} msg={payload.get('msg')}")
        return

    items = (payload.get("data") or {}).get("items") or []
    print(f"共 {len(items)} 张数据表：\n")
    for item in items:
        print(f"  name      : {item.get('name')}")
        identifier = item.get("table_id") if args.show_identifiers else "[已隐藏；需要时加 --show-identifiers]"
        print(f"  table_id  : {identifier}")
        print()
    if items:
        print("把正确的 table_id 写入 .env.local 的 FEISHU_BITABLE_TABLE_ID")


if __name__ == "__main__":
    main()
