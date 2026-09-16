"""列出当前租户云空间中可访问的多维表格，默认隐藏资源标识符。

不依赖用户手输 token：直接查云文档列表。
只读取 .env.local 中的应用凭据，不打印凭据值。
"""
from __future__ import annotations

import json
import argparse
import urllib.error
import urllib.parse
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


def request_json(url: str, token: str) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")
    except Exception as error:
        return 0, f"{type(error).__name__}: {error}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-identifiers", action="store_true", help="在本机交互终端显示资源 token")
    args = parser.parse_args()
    env = load_env()
    body = json.dumps({"app_id": env.get("FEISHU_APP_ID", ""), "app_secret": env.get("FEISHU_APP_SECRET", "")}).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        auth = json.loads(response.read().decode("utf-8"))
    token = str(auth.get("tenant_access_token") or "")
    if not token:
        print(f"鉴权失败: {auth}")
        return
    print(f"鉴权成功 (code={auth.get('code')})\n")

    endpoints = [
        ("根目录文件列表", "https://open.feishu.cn/open-apis/drive/v1/files?page_size=50"),
        ("我的空间(带 order_by)", "https://open.feishu.cn/open-apis/drive/v1/files?page_size=50&order_by=EditedTime&direction=DESC"),
    ]
    for label, url in endpoints:
        status, payload = request_json(url, token)
        print(f"==== {label}")
        print(f"  HTTP={status}")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print(f"  {payload[:300]}")
            continue
        if data.get("code") != 0:
            print(f"  code={data.get('code')} msg={data.get('msg')}")
            continue
        files = (data.get("data") or {}).get("files") or []
        print(f"  共 {len(files)} 项")
        for item in files:
            if item.get("type") == "bitable":
                identifier = item.get("token") if args.show_identifiers else "[已隐藏；需要时加 --show-identifiers]"
                print(f"   ★ [多维表格] name={item.get('name')}  token={identifier}")
            else:
                print(f"     [{item.get('type')}] name={item.get('name')}")
        print()


if __name__ == "__main__":
    main()
