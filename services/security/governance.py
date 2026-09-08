"""Local security controls and an explicit real-data readiness gate."""

from __future__ import annotations

import re
import threading
import time
import zipfile
from collections import defaultdict, deque
from io import BytesIO
from typing import Any, Callable, Iterable


MAX_ARCHIVE_ENTRIES = 2_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 25 * 1024 * 1024

_SENSITIVE_PATTERNS = {
    "email": re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    "china_mobile": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "china_id_like": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    "api_token_like": re.compile(
        r"(?i)(?:api[_ -]?key|access[_ -]?token|secret)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{12,})"
    ),
}


class SecurityInputError(ValueError):
    """Raised when a file violates a deterministic security boundary."""

    def __init__(self, message: str, code: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def assess_sensitive_text(values: Iterable[Any]) -> dict[str, Any]:
    """Return categories and counts without returning matched sensitive values."""
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        text = str(value or "")
        for category, pattern in _SENSITIVE_PATTERNS.items():
            counts[category] += len(pattern.findall(text))
    findings = [
        {"category": category, "count": count, "severity": "high" if category in {"china_id_like", "api_token_like"} else "medium"}
        for category, count in sorted(counts.items())
        if count
    ]
    return {
        "classification": "sensitive_detected" if findings else "no_common_sensitive_pattern_detected",
        "sensitive_data_detected": bool(findings),
        "findings": findings,
        "real_data_allowed": False,
        "notice": (
            "检测到常见敏感信息样式；请移除或去标识化后再使用。"
            if findings else
            "未检出内置规则覆盖的常见样式；这不等于文件不含敏感信息。"
        ),
    }


def inspect_office_archive(content: bytes, filename: str) -> dict[str, Any]:
    """Reject malformed or expanded Office archives before document parsing."""
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            expanded = sum(item.file_size for item in entries)
    except (zipfile.BadZipFile, OSError) as error:
        raise SecurityInputError(f"{filename} 不是有效的 Office 压缩文件", "office_archive_invalid") from error
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise SecurityInputError("Office 文件包含过多压缩条目", "archive_entry_limit")
    if expanded > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise SecurityInputError("Office 文件解压后超过 25 MB 安全限制", "archive_expansion_limit", 413)
    return {"archive_entries": len(entries), "uncompressed_bytes": expanded, "malware_scan": "not_available"}


def readiness_status() -> dict[str, Any]:
    """Describe implemented controls and blockers without implying production readiness."""
    controls = [
        {"control": "localhost_binding", "implemented": True, "evidence": "开发服务器默认监听 127.0.0.1"},
        {"control": "security_headers", "implemented": True, "evidence": "CSP、frame、MIME、referrer、permissions 和 no-store 响应头"},
        {"control": "upload_boundaries", "implemented": True, "evidence": "扩展名、文件大小、行列和 Office 解压边界"},
        {"control": "sensitive_pattern_warning", "implemented": True, "evidence": "预览只返回敏感类别和数量，不回显匹配值"},
        {"control": "local_write_rate_limit", "implemented": True, "evidence": "单进程、单来源写接口限流；不是分布式生产限流"},
        {"control": "tracked_file_secret_scan", "implemented": True, "evidence": "完整检查会扫描 Git 跟踪文件"},
        {"control": "authentication", "implemented": False, "evidence": "没有登录和会话"},
        {"control": "role_based_access", "implemented": False, "evidence": "没有角色或权限模型"},
        {"control": "true_tenant_isolation", "implemented": False, "evidence": "company_id 只是本地数据上下文"},
        {"control": "database_encryption", "implemented": False, "evidence": "本地 SQLite 未加密"},
        {"control": "managed_secret_store", "implemented": False, "evidence": "密钥仅由进程环境变量注入"},
        {"control": "malware_scanning", "implemented": False, "evidence": "没有反恶意软件扫描引擎"},
    ]
    return {
        "status": "blocked_for_real_data",
        "scope": "simulated_or_deidentified_test_data_only",
        "real_data_allowed": False,
        "public_deployment_allowed": False,
        "controls": controls,
        "blocking_controls": [item["control"] for item in controls if not item["implemented"]],
        "retention": {
            "policy": "no_automatic_retention_guarantee",
            "user_action": "通过页面确认删除本地公司数据；运行产物和备份需由设备所有者管理",
        },
    }


class LocalRateLimiter:
    """Small per-process limiter for local write endpoints."""

    def __init__(self, limit: int = 120, window_seconds: int = 60, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = self.clock()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - events[0])))
                return False, retry_after
            events.append(now)
            return True, 0
