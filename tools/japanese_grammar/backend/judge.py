"""Offline deterministic judging helpers for local Japanese grammar training."""

from __future__ import annotations

import json
import re
from typing import Any

from graspmemoedu.judging import judge_answer
from graspmemoedu.question_types import (
    exact as qt_exact,
    normalize as qt_normalize,
    parse_answer as qt_parse_answer,
)

from .romaji import resolve_blank_answer_with_romaji

_WHITESPACE_RE = re.compile(r"[\s\u3000]+")


def _interaction(question: dict[str, Any]) -> dict[str, Any]:
    nested = question.get("interaction")
    if isinstance(nested, dict):
        return nested
    return question


def _question_type(question: dict[str, Any]) -> str:
    spec = _interaction(question)
    return str(spec.get("type") or question.get("type") or "").strip()


def _question_blanks(question: dict[str, Any]) -> list[dict[str, Any]]:
    spec = _interaction(question)
    blanks = spec.get("blanks")
    if isinstance(blanks, list):
        return blanks
    top_blanks = question.get("blanks")
    return top_blanks if isinstance(top_blanks, list) else []


def canonical_japanese(value: Any) -> str:
    """Normalize Japanese short-answer text without altering kana or kanji."""
    if value is None:
        return ""
    text = qt_normalize(str(value))
    return _WHITESPACE_RE.sub("", text)


def _blank_expected_values(blank: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("answers", "accepted", "accepted_answers"):
        raw = blank.get(key)
        if isinstance(raw, list):
            values.extend(str(item) for item in raw if str(item).strip())
    for key in ("answer", "expected", "reference_answer"):
        raw = blank.get(key)
        if isinstance(raw, str) and raw.strip():
            values.append(raw)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        marker = qt_normalize(item)
        if marker and marker not in seen:
            seen.add(marker)
            deduped.append(item)
    return deduped


def _parse_fill_blank_answer(question: dict[str, Any], answer: Any) -> dict[str, str]:
    try:
        parsed = qt_parse_answer(question, answer)
        if isinstance(parsed, dict):
            return {str(k): "" if v is None else str(v) for k, v in parsed.items()}
    except Exception:
        pass
    if isinstance(answer, dict):
        return {str(k): "" if v is None else str(v) for k, v in answer.items()}
    if isinstance(answer, str):
        stripped = answer.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                loaded = json.loads(stripped)
            except ValueError:
                loaded = None
            if isinstance(loaded, dict):
                return {str(k): "" if v is None else str(v) for k, v in loaded.items()}
        blanks = _question_blanks(question)
        if len(blanks) == 1 and isinstance(blanks[0], dict):
            blank_id = str(blanks[0].get("id") or "b1")
            return {blank_id: answer}
    return {}


def canonicalize_fill_blank_answer(question: dict[str, Any], answer: Any) -> Any:
    """Resolve romaji blank values to matching canonical answers while preserving shape."""
    if _question_type(question) != "fill_blank":
        return answer
    blanks = _question_blanks(question)
    if not blanks:
        return answer
    try:
        parsed = qt_parse_answer(question, answer)
    except Exception:
        return answer
    if not isinstance(parsed, dict):
        return answer

    resolved: dict[str, str] = {}
    changed = False
    for index, blank in enumerate(blanks, start=1):
        if not isinstance(blank, dict):
            continue
        blank_id = str(blank.get("id") or f"b{index}")
        raw_val = "" if parsed.get(blank_id) is None else str(parsed.get(blank_id))
        expected = _blank_expected_values(blank)
        matched = resolve_blank_answer_with_romaji(expected, raw_val)
        resolved[blank_id] = matched
        if matched != raw_val:
            changed = True
    if not changed:
        return answer
    return json.dumps(resolved, ensure_ascii=False, separators=(",", ":"))


def per_blank_results(question: dict[str, Any], answer: Any) -> list[dict[str, Any]]:
    """Return deterministic per-blank verdict items for a fill_blank question."""
    blanks = _question_blanks(question)
    submitted_map = _parse_fill_blank_answer(question, answer)
    results: list[dict[str, Any]] = []
    for index, blank in enumerate(blanks, start=1):
        if not isinstance(blank, dict):
            continue
        blank_id = str(blank.get("id") or f"b{index}")
        label = str(blank.get("label") or f"空{index}")
        submitted = submitted_map.get(blank_id, "")
        expected = _blank_expected_values(blank)
        candidate = resolve_blank_answer_with_romaji(expected, submitted)
        ok = False
        if expected:
            try:
                ok = bool(qt_exact(blank, candidate))
            except Exception:
                normalized_submitted = canonical_japanese(candidate)
                ok = bool(normalized_submitted) and any(
                    normalized_submitted == canonical_japanese(candidate_exp)
                    for candidate_exp in expected
                )
        results.append(
            {
                "index": index,
                "id": blank_id,
                "label": label,
                "submitted": submitted,
                "expected": expected,
                "correct": ok,
                "mark": "✓" if ok else "✗",
            }
        )
    return results


def format_blank_summary(
    question: dict[str, Any],
    answer: Any,
    *,
    results: list[dict[str, Any]] | None = None,
) -> str:
    """Format concise per-blank ✓ / ✗ feedback plus expected answers."""
    items = results if results is not None else per_blank_results(question, answer)
    if not items:
        return ""
    parts: list[str] = []
    for item in items:
        label = str(item.get("label") or item.get("id") or f"空{item.get('index', '')}")
        submitted = str(item.get("submitted") or "").strip() or "未作答"
        expected = [str(v) for v in (item.get("expected") or []) if str(v).strip()]
        expected_text = " / ".join(expected)
        if item.get("correct"):
            parts.append(f"{label} ✓ {submitted}")
        elif expected_text:
            parts.append(f"{label} ✗ 「{submitted}」（参考：{expected_text}）")
        else:
            parts.append(f"{label} ✗ 「{submitted}」")
    correct_count = sum(1 for item in items if item.get("correct"))
    return f"逐空判定（{correct_count}/{len(items)}）：" + "；".join(parts)


def evaluate_question_offline(
    question: dict[str, Any],
    answer: Any,
) -> tuple[bool | None, str]:
    """Evaluate deterministically via shared judging.judge_answer(None, ...).

    Never acquires database locks or performs network I/O.
    """
    canonical_answer = canonicalize_fill_blank_answer(question, answer)
    passed, reason = judge_answer(None, question, canonical_answer)
    if _question_type(question) == "fill_blank":
        items = per_blank_results(question, answer)
        summary = format_blank_summary(question, answer, results=items)
        if passed is not None:
            return passed, summary or reason
        if items and all(item.get("expected") for item in items):
            all_correct = all(bool(item.get("correct")) for item in items)
            return all_correct, summary or reason
    return passed, reason


class JapaneseGrammarJudge:
    """Callable offline judge passed to shared LearningService instances."""

    is_offline = True
    mode = "offline"

    def available(self) -> bool:
        return True

    def normalize_answer(self, question: dict[str, Any], answer: Any) -> Any:
        """Resolve romaji fill-blank answers to canonical Japanese before exact judging."""
        return canonicalize_fill_blank_answer(question, answer)

    def grade_fill_blank(self, question: dict[str, Any], answer: Any) -> dict[str, Any]:
        """Return structured per-blank verdict details without mutating DB state."""
        passed, reason = evaluate_question_offline(question, answer)
        items = per_blank_results(question, answer)
        return {
            "passed": passed,
            "reason": reason,
            "blanks": items,
            "summary": format_blank_summary(question, answer, results=items),
        }

    def __call__(self, question: dict[str, Any], answer: Any) -> tuple[bool | None, str]:
        passed, reason = evaluate_question_offline(question, answer)
        if passed is not None:
            return passed, reason

        candidates: list[str] = []
        for key in ("accepted_answers", "answers", "accepted"):
            raw = question.get(key)
            if isinstance(raw, list):
                candidates.extend(str(item) for item in raw if str(item).strip())
        for key in ("expected", "reference_answer", "answer"):
            raw = question.get(key)
            if isinstance(raw, str) and raw.strip():
                candidates.append(raw)

        if candidates:
            actual = canonical_japanese(answer)
            matched = bool(actual) and any(
                actual == canonical_japanese(item) for item in candidates
            )
            if matched:
                return True, "离线精确匹配通过。"
            return False, f"与参考答案不一致（参考：{' / '.join(candidates)}）。"

        return None, reason or "当前题目仅支持离线精确判题，未配置外部语义判题服务。"


__all__ = [
    "JapaneseGrammarJudge",
    "canonical_japanese",
    "evaluate_question_offline",
    "format_blank_summary",
    "per_blank_results",
]
