"""Probe Feishu endpoints with the same HTTP stack the connector uses.

Reads credentials from .env.local; never prints secret values.
"""
from __future__ import annotations

import json
import argparse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    target = ROOT / ".env.local"
    for line in target.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        value = value.strip().strip('"').strip("'")
        if value:
            values[key.strip()] = value
    return values


def call(label: str, url: str, *, token: str = "", method: str = "GET", body: Any = None) -> None:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    print(f"---- {label}: {method}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
            print(f"     HTTP={response.status}")
            decoded = json.loads(payload) if payload else {}
            data = decoded.get("data") if isinstance(decoded, dict) else None
            count = len(data.get("items", [])) if isinstance(data, dict) and isinstance(data.get("items"), list) else 0
            print(f"     code={decoded.get('code')} msg={decoded.get('msg')} items={count}")
    except urllib.error.HTTPError as error:
        payload = ""
        try:
            payload = error.read().decode("utf-8")
        except Exception:
            payload = "<无法读取>"
        print(f"     HTTP={error.code}  reason={error.reason}")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            decoded = {}
        print(f"     code={decoded.get('code')} msg={decoded.get('msg') or '<响应正文已隐藏>'}")
    except Exception as error:  # network level
        print(f"     NETWORK ERROR: {type(error).__name__}: {error}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-token", required=True, help="待探测的 wiki 节点 token；不会输出")
    args = parser.parse_args()
    env = load_env()
    app_id = env.get("FEISHU_APP_ID", "")
    app_secret = env.get("FEISHU_APP_SECRET", "")
    table_id = env.get("FEISHU_BITABLE_TABLE_ID", "")
    print(f"凭据状态: app_id={'已配置' if app_id else '缺失'} app_secret={'已配置' if app_secret else '缺失'} table_id={'已配置' if table_id else '缺失'}\n")

    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    request = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        auth = json.loads(response.read().decode("utf-8"))
    print(f"鉴权: code={auth.get('code')} msg={auth.get('msg')}")
    token = str(auth.get("tenant_access_token") or "")
    print(f"访问令牌: {'已获取' if token else '未获取'}\n")
    if not token:
        return

    wiki = args.wiki_token.strip()
    call("wiki 节点（指定类型）", f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={wiki}&obj_type=wiki", token=token)
    call("wiki 节点", f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={wiki}", token=token)
    call("按 wiki token 查询数据表", f"https://open.feishu.cn/open-apis/bitable/v1/apps/{wiki}/tables", token=token)
    call(
        "按 wiki token 查询记录",
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{wiki}/tables/{table_id}/records/search",
        token=token,
        method="POST",
        body={"automatic_fields": True},
    )
    call("应用列表", "https://open.feishu.cn/open-apis/bitable/v1/apps", token=token)


if __name__ == "__main__":
    main()
