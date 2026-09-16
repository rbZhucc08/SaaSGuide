"""打印飞书 wiki 节点的完整信息，重点输出 obj_token / obj_type。

用法: python scripts/show_feishu_wiki_node.py <wiki_node_token>
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
    parser.add_argument("wiki_node_token")
    parser.add_argument("--show-identifiers", action="store_true")
    args = parser.parse_args()
    node_token = args.wiki_node_token.strip()

    env = load_env()
    body = json.dumps({"app_id": env.get("FEISHU_APP_ID", ""), "app_secret": env.get("FEISHU_APP_SECRET", "")}).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        token = str(json.loads(response.read().decode("utf-8")).get("tenant_access_token") or "")

    url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={node_token}&obj_type=wiki"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print(f"HTTP={error.code} {error.read().decode('utf-8', errors='replace')[:400]}")
        return

    if payload.get("code") != 0:
        print(f"查询失败 code={payload.get('code')} msg={payload.get('msg')}")
        return

    node = payload["data"]["node"]
    print(f"标题      : {node.get('title')}")
    print(f"对象类型  : {node.get('obj_type')}")
    print(f"obj_token : {node.get('obj_token') if args.show_identifiers else '[已隐藏；需要时加 --show-identifiers]'}")
    if node.get("obj_type") == "bitable":
        print("\n这是多维表格。把下面这行写入 .env.local：")
        if args.show_identifiers:
            print(f"FEISHU_BITABLE_APP_TOKEN={node.get('obj_token')}")
        else:
            print("需要写入本机环境文件时，请加 --show-identifiers 重新运行。")


if __name__ == "__main__":
    main()
