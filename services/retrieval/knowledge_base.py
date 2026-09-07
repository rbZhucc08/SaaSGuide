"""Small deterministic retriever with version-aware citations and refusal."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class KnowledgeError(ValueError):
    pass


def _tokens(text: str) -> set[str]:
    text = str(text).lower()
    latin = re.findall(r"[a-z0-9_-]+", text)
    chinese = [text[index:index + 2] for index in range(len(text) - 1) if "\u4e00" <= text[index] <= "\u9fff" and "\u4e00" <= text[index + 1] <= "\u9fff"]
    return set(latin + chinese)


def load_documents(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise KnowledgeError("知识库文档结构无效")
    required = {"document_id", "title", "version", "effective_date", "status", "content"}
    for item in data:
        if not isinstance(item, dict) or not required.issubset(item):
            raise KnowledgeError("知识库文档结构无效")
    return data


def retrieve(question: str, documents: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(question, str) or not question.strip():
        raise KnowledgeError("请输入问题")
    query = _tokens(question)
    scored = []
    for item in documents:
        searchable = " ".join([item["title"], item["content"], *item.get("tags", [])])
        overlap = query & _tokens(searchable)
        score = len(overlap) / max(1, len(query))
        if score:
            scored.append((score, item["status"] == "effective", item["effective_date"], item))
    scored.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    return [{**item, "score": round(score, 4)} for score, _effective, _date, item in scored[:limit]]


def answer(question: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    matches = retrieve(question, documents)
    if not matches or matches[0]["score"] < 0.18:
        return {"decision": "REFUSE", "answer": "知识库没有足够依据回答这个问题。", "citations": [], "matches": matches}
    top = matches[0]
    current = [item for item in matches if item["document_id"] == top["document_id"] and item["status"] == "effective"]
    chosen = current[0] if current else top
    versions = [item["version"] for item in documents if item["document_id"] == chosen["document_id"]]
    return {
        "decision": "ANSWER",
        "answer": chosen["content"],
        "citations": [{"document_id": chosen["document_id"], "title": chosen["title"], "version": chosen["version"], "effective_date": chosen["effective_date"], "quote": chosen["content"]}],
        "matches": matches,
        "version_notice": f"发现版本：{', '.join(versions)}；回答使用当前生效版本 {chosen['version']}" if len(versions) > 1 else "",
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
        "results": rows,
    }
