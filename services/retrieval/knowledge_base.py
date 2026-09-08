"""Version-aware hybrid retrieval with exact citations and safe refusal."""

from __future__ import annotations

from collections import Counter
import json
import math
import re
from pathlib import Path
from typing import Any


RETRIEVAL_VERSION = "hybrid-retrieval-v1"
INJECTION_PATTERNS = ("忽略系统规则", "忽略之前", "输出全部数据", "system prompt", "ignore previous", "reveal secrets")


class KnowledgeError(ValueError):
    pass


def _tokens(text: str) -> list[str]:
    text = str(text).lower()
    latin = re.findall(r"[a-z0-9_-]+", text)
    chinese = [text[index:index + 2] for index in range(len(text) - 1) if "\u4e00" <= text[index] <= "\u9fff" and "\u4e00" <= text[index + 1] <= "\u9fff"]
    return latin + chinese


def _contains_injection(text: str) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in INJECTION_PATTERNS)


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(value * right.get(token, 0) for token, value in left.items())
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(sum(value * value for value in right.values()))
    return numerator / denominator if denominator else 0.0


def load_documents(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise KnowledgeError("知识库文档结构无效")
    required = {"document_id", "title", "version", "effective_date", "status", "content"}
    for item in data:
        if not isinstance(item, dict) or not required.issubset(item):
            raise KnowledgeError("知识库文档结构无效")
        if not all(isinstance(item.get(field), str) and item[field].strip() for field in required):
            raise KnowledgeError("知识库文档字段不能为空")
    return data


def chunk_documents(documents: list[dict[str, Any]], max_chars: int = 240) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for item in documents:
        content = item["content"]
        sentences = [part.strip() for part in re.split(r"(?<=[。！？；\n])", content) if part.strip()]
        if not sentences:
            sentences = [content]
        buckets: list[str] = []
        for sentence in sentences:
            if buckets and len(buckets[-1]) + len(sentence) <= max_chars:
                buckets[-1] += sentence
            else:
                buckets.append(sentence)
        search_start = 0
        for index, quote in enumerate(buckets, start=1):
            start = content.find(quote, search_start)
            start = start if start >= 0 else search_start
            search_start = start + len(quote)
            chunks.append({
                **item,
                "chunk_id": f"{item['document_id']}@{item['version']}#c{index}",
                "quote": quote,
                "location": f"正文字符 {start + 1}-{start + len(quote)}",
                "suspicious_instruction": _contains_injection(quote),
            })
    return chunks


def _matches_filters(item: dict[str, Any], filters: dict[str, Any]) -> bool:
    for field in ("document_id", "status", "company_id", "document_type"):
        expected = filters.get(field)
        if expected and item.get(field) != expected:
            return False
    required_tags = set(filters.get("tags") or [])
    return not required_tags or required_tags.issubset(set(item.get("tags") or []))


def retrieve(question: str, documents: list[dict[str, Any]], limit: int = 3, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if not isinstance(question, str) or not question.strip():
        raise KnowledgeError("请输入问题")
    if len(question) > 1000:
        raise KnowledgeError("问题不能超过 1000 个字符")
    query_tokens = _tokens(question)
    query_set = set(query_tokens)
    query_vector = Counter(query_tokens)
    scored = []
    for chunk in chunk_documents(documents):
        if chunk["suspicious_instruction"] or not _matches_filters(chunk, filters or {}):
            continue
        searchable = " ".join([chunk["title"], chunk["quote"], *chunk.get("tags", [])])
        item_tokens = _tokens(searchable)
        keyword_score = len(query_set & set(item_tokens)) / max(1, len(query_set))
        vector_score = _cosine(query_vector, Counter(item_tokens))
        score = 0.65 * keyword_score + 0.35 * vector_score
        if score:
            scored.append((score, keyword_score, vector_score, chunk["status"] == "effective", chunk["effective_date"], chunk))
    effective_ids = {row[5]["document_id"] for row in scored if row[3]}
    scored = [row for row in scored if row[3] or row[5]["document_id"] not in effective_ids]
    scored.sort(key=lambda row: (row[0], row[3], row[4]), reverse=True)
    return [
        {**item, "score": round(score, 4), "keyword_score": round(keyword, 4), "vector_score": round(vector, 4), "retrieval_version": RETRIEVAL_VERSION}
        for score, keyword, vector, _effective, _date, item in scored[: max(1, min(limit, 20))]
    ]


def detect_version_conflicts(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    effective: dict[str, list[str]] = {}
    for item in documents:
        if item["status"] == "effective":
            effective.setdefault(item["document_id"], []).append(item["version"])
    return [
        {"document_id": document_id, "effective_versions": sorted(versions), "reason": "同一文档存在多个生效版本"}
        for document_id, versions in effective.items() if len(versions) > 1
    ]


def answer(question: str, documents: list[dict[str, Any]], filters: dict[str, Any] | None = None) -> dict[str, Any]:
    suspicious_documents = [item["document_id"] for item in documents if _contains_injection(item["content"])]
    conflicts = detect_version_conflicts(documents)
    matches = retrieve(question, documents, filters=filters)
    base = {
        "matches": matches,
        "retrieval": {"version": RETRIEVAL_VERSION, "method": "keyword_plus_local_sparse_vector", "filters": filters or {}},
        "conflicts": conflicts,
        "security_notices": [{"type": "prompt_injection_text_excluded", "document_id": item} for item in suspicious_documents],
    }
    if conflicts:
        return {"decision": "REFUSE", "answer": "知识库存在多个生效版本，请先解决版本冲突。", "citations": [], **base}
    if not matches or matches[0]["score"] < 0.18:
        return {"decision": "REFUSE", "answer": "知识库没有足够依据回答这个问题。", "citations": [], **base}
    top = matches[0]
    versions = [item["version"] for item in documents if item["document_id"] == top["document_id"]]
    citation = {field: top[field] for field in ("document_id", "title", "version", "effective_date", "chunk_id", "location", "quote")}
    return {
        "decision": "ANSWER",
        "answer": top["quote"],
        "citations": [citation],
        **base,
        "version_notice": f"发现版本：{', '.join(versions)}；回答使用当前生效版本 {top['version']}" if len(versions) > 1 else "",
        "generation": "deterministic_excerpt_no_llm",
    }


def evaluate(documents: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval_hits = citation_hits = refusal_hits = 0
    answer_cases = refusal_cases = 0
    rows = []
    for case in cases:
        result = answer(case["question"], documents)
        refused = result["decision"] == "REFUSE"
        if case["expect_refusal"]:
            refusal_cases += 1
            refusal_hits += refused
            ok = refused
        else:
            answer_cases += 1
            citation = result.get("citations", [{}])[0] if result.get("citations") else {}
            retrieval_ok = bool(result.get("matches")) and result["matches"][0]["document_id"] == case["expected_document"]
            citation_ok = citation.get("document_id") == case["expected_document"] and citation.get("version") == case["expected_version"]
            retrieval_hits += retrieval_ok
            citation_hits += citation_ok
            ok = retrieval_ok and citation_ok
        rows.append({"id": case["id"], "passed": ok, "decision": result["decision"]})
    return {
        "case_count": len(cases),
        "retrieval_hit_rate": retrieval_hits / answer_cases if answer_cases else 0,
        "citation_accuracy": citation_hits / answer_cases if answer_cases else 0,
        "refusal_accuracy": refusal_hits / refusal_cases if refusal_cases else 0,
        "passed": all(row["passed"] for row in rows),
        "retrieval_version": RETRIEVAL_VERSION,
        "results": rows,
    }
