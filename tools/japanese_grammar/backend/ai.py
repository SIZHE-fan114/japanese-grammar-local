"""OpenAI-compatible AI configuration, contextual tutor prompting, and local proxy client."""

from __future__ import annotations

from contextlib import closing
import html as html_lib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Iterator
from urllib.parse import urlparse

import httpx

from graspmemoedu.service import DomainError

from .runtime import REPO_ROOT, _atomic_write_json

AI_CONFIG_FILE = "ai_config.json"
DEFAULT_AI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AI_MODEL = "gpt-4o-mini"
DEFAULT_AI_TIMEOUT_SECONDS = 60.0
TEST_AI_TIMEOUT_SECONDS = 15.0

_TAG_RE = re.compile(r"<[^>]+>")
_RUBY_RT_RE = re.compile(r"<ruby>\s*([^<]*?)\s*<rt>([^<]*?)</rt>\s*</ruby>", re.IGNORECASE)
_BLANK_HTML_RE = re.compile(r"<span[^>]*data-blank-id=[^>]*>.*?</span>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")


def _strip_html(raw: str | None) -> str:
    text = str(raw or "")
    if not text:
        return ""
    text = _BLANK_HTML_RE.sub(" [ ___ ] ", text)
    text = _RUBY_RT_RE.sub(r"\1(\2)", text)
    text = re.sub(r"</(?:p|div|li|tr|h[1-6]|blockquote)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    text = html_lib.unescape(text)
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    joined = "\n".join(line for line in lines if line)
    return _MULTI_NL_RE.sub("\n\n", joined).strip()


def mask_api_key(api_key: str) -> str:
    """Return a non-recoverable masked key preview for UI display."""
    key = str(api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 4:
        return "••••"
    if len(key) <= 10:
        return f"{key[:2]}••••{key[-2:]}"
    return f"{key[:4]}••••{key[-4:]}"


def validate_ai_base_url(raw_url: str) -> str:
    """Validate and normalize an OpenAI-compatible HTTP(S) base URL."""
    cleaned = str(raw_url or "").strip().rstrip("/")
    if not cleaned:
        raise DomainError("invalid_ai_config", "Base URL 不能为空。", 422)
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise DomainError(
            "invalid_ai_config",
            "Base URL 必须是有效的 http:// 或 https:// 地址。",
            422,
        )
    if parsed.username or parsed.password:
        raise DomainError("invalid_ai_config", "Base URL 不允许内嵌用户名或密码。", 422)
    return cleaned


def _endpoint_urls(base_url: str) -> tuple[str, str]:
    normalized = validate_ai_base_url(base_url)
    lowered = normalized.lower()
    if lowered.endswith("/chat/completions"):
        root = normalized[: -len("/chat/completions")].rstrip("/")
        chat_url = normalized
    else:
        root = normalized
        chat_url = f"{root}/chat/completions"
    models_url = f"{root}/models" if not root.lower().endswith("/models") else root
    return chat_url, models_url


def _read_dotenv_fallback(env_path: Path | None = None) -> dict[str, str]:
    path = env_path or (REPO_ROOT / ".env")
    if not path.is_file() or path.is_symlink():
        return {}
    values: dict[str, str] = {}
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, sep, raw_val = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        val = raw_val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = val[1:-1]
        values[key] = val
    return values


def _env_lookup(*names: str, dotenv_map: dict[str, str]) -> str:
    for name in names:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    for name in names:
        val = (dotenv_map.get(name) or "").strip()
        if val:
            return val
    return ""


def _config_path(data_dir: Path) -> Path:
    path = Path(data_dir) / AI_CONFIG_FILE
    if path.exists() and path.is_symlink():
        raise ValueError(f"AI config path must not be a symlink: {path}")
    return path


def _load_local_config(data_dir: Path) -> dict[str, Any]:
    path = _config_path(data_dir)
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return dict(loaded) if isinstance(loaded, dict) else {}


def resolve_ai_config(data_dir: Path, *, dotenv_path: Path | None = None) -> dict[str, Any]:
    """Resolve effective AI configuration with local ai_config.json > env/.env > defaults."""
    local = _load_local_config(data_dir)
    dotenv_map = _read_dotenv_fallback(dotenv_path)

    env_base_url = _env_lookup("OPENAI_BASE_URL", "OPENAI_API_BASE", dotenv_map=dotenv_map)
    env_api_key = _env_lookup("OPENAI_API_KEY", dotenv_map=dotenv_map)
    env_model = _env_lookup("OPENAI_MODEL", dotenv_map=dotenv_map)

    local_base_url = str(local.get("base_url") or "").strip()
    local_api_key = str(local.get("api_key") or "").strip()
    local_model = str(local.get("model") or "").strip()
    local_stream = local.get("stream") if isinstance(local.get("stream"), bool) else None

    if local_base_url:
        base_url = local_base_url.rstrip("/")
        base_url_source = "local"
    elif env_base_url:
        base_url = env_base_url.rstrip("/")
        base_url_source = "env"
    else:
        base_url = DEFAULT_AI_BASE_URL
        base_url_source = "default"

    if local_api_key:
        api_key = local_api_key
        api_key_source = "local"
    elif env_api_key:
        api_key = env_api_key
        api_key_source = "env"
    else:
        api_key = ""
        api_key_source = "none"

    if local_model:
        model = local_model
        model_source = "local"
    elif env_model:
        model = env_model
        model_source = "env"
    else:
        model = DEFAULT_AI_MODEL
        model_source = "default"

    stream = local_stream if local_stream is not None else True

    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "stream": stream,
        "sources": {
            "base_url": base_url_source,
            "api_key": api_key_source,
            "model": model_source,
        },
        "local_overrides": {
            "has_base_url": bool(local_base_url),
            "has_api_key": bool(local_api_key),
            "has_model": bool(local_model),
            "has_stream": local_stream is not None,
        },
        "env_available": {
            "has_base_url": bool(env_base_url),
            "has_api_key": bool(env_api_key),
            "has_model": bool(env_model),
        },
    }


def public_ai_config(data_dir: Path, *, dotenv_path: Path | None = None) -> dict[str, Any]:
    """Return frontend-safe AI config summary without ever exposing the raw API key."""
    resolved = resolve_ai_config(data_dir, dotenv_path=dotenv_path)
    api_key = resolved["api_key"]
    return {
        "configured": bool(api_key and resolved["base_url"] and resolved["model"]),
        "base_url": resolved["base_url"],
        "model": resolved["model"],
        "stream": resolved["stream"],
        "api_key_set": bool(api_key),
        "api_key_masked": mask_api_key(api_key),
        "sources": dict(resolved["sources"]),
        "local_overrides": dict(resolved["local_overrides"]),
        "env_available": dict(resolved["env_available"]),
    }


def update_ai_config(
    data_dir: Path,
    payload: dict[str, Any],
    *,
    dotenv_path: Path | None = None,
) -> dict[str, Any]:
    """Persist local AI overrides cleanly; empty values fall back to env/default."""
    path = _config_path(data_dir)
    if payload.get("reset_to_env"):
        if path.is_file():
            path.unlink()
        return public_ai_config(data_dir, dotenv_path=dotenv_path)

    existing = _load_local_config(data_dir)
    updated: dict[str, Any] = dict(existing)

    if "base_url" in payload and payload["base_url"] is not None:
        raw_base = str(payload["base_url"]).strip()
        if raw_base:
            updated["base_url"] = validate_ai_base_url(raw_base)
        else:
            updated.pop("base_url", None)

    if payload.get("clear_api_key"):
        updated.pop("api_key", None)
    elif "api_key" in payload and payload["api_key"] is not None:
        raw_key = str(payload["api_key"]).strip()
        if raw_key:
            updated["api_key"] = raw_key
        else:
            updated.pop("api_key", None)

    if "model" in payload and payload["model"] is not None:
        raw_model = str(payload["model"]).strip()
        if raw_model:
            updated["model"] = raw_model
        else:
            updated.pop("model", None)

    if "stream" in payload and payload["stream"] is not None:
        updated["stream"] = bool(payload["stream"])

    clean_store = {
        key: val
        for key, val in updated.items()
        if key in {"base_url", "api_key", "model", "stream"}
        and ((isinstance(val, str) and val.strip()) or isinstance(val, bool))
    }
    if not clean_store:
        if path.is_file():
            path.unlink()
    else:
        _atomic_write_json(path, clean_store)

    return public_ai_config(data_dir, dotenv_path=dotenv_path)


def _find_card_in_runtime(runtime: Any, topic_id: str | None, card_id: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not card_id:
        topic = runtime.catalog.topics.get(topic_id) if topic_id else None
        return topic, None
    if topic_id and topic_id in runtime.catalog.topics:
        topic = runtime.catalog.topics[topic_id]
        for card in topic.get("flashcards") or []:
            if isinstance(card, dict) and card.get("id") == card_id:
                return topic, card
    for topic in runtime.catalog.topics.values():
        for card in topic.get("flashcards") or []:
            if isinstance(card, dict) and card.get("id") == card_id:
                return topic, card
    topic = runtime.catalog.topics.get(topic_id) if topic_id else None
    return topic, None


def _paper_item_status(runtime: Any, learner_id: str, paper_id: str | None, card_id: str | None) -> tuple[bool | None, dict[str, Any] | None]:
    if not paper_id:
        return None, None
    db_path = Path(runtime.data_dir) / "learning.sqlite3"
    if not db_path.is_file():
        return None, None
    try:
        with closing(sqlite3.connect(str(db_path), timeout=5.0)) as con:
            con.row_factory = sqlite3.Row
            row = con.execute(
                "SELECT id, title, phase, items FROM review_papers WHERE id=? AND learner=?",
                (paper_id, learner_id),
            ).fetchone()
    except sqlite3.Error:
        return None, None
    if row is None:
        return None, None
    phase = str(row["phase"] or "")
    try:
        items = json.loads(row["items"] or "[]")
    except ValueError:
        items = []
    matched_item = None
    if card_id:
        for item in items:
            if isinstance(item, dict) and (item.get("card_id") == card_id or item.get("item_id") == card_id):
                matched_item = item
                break
    if phase in {"done", "completed", "expired"}:
        return True, matched_item
    if matched_item is not None:
        return bool(matched_item.get("completed") or matched_item.get("result") is not None), matched_item
    return False, None


def extract_authoritative_learning_context(
    runtime: Any,
    learner_id: str,
    request_context: dict[str, Any],
) -> dict[str, Any]:
    """Assemble authoritative study context from local runtime state + safe UI metadata."""
    topic_id = request_context.get("topic_id")
    view = str(request_context.get("view") or "").strip().lower()
    req_card_id = request_context.get("card_id")
    paper_id = request_context.get("paper_id")
    step_index = request_context.get("step_index")
    step_total = request_context.get("step_total")
    step_title = str(request_context.get("step_title") or "").strip()
    step_text = str(request_context.get("step_text") or "").strip()
    user_draft = str(request_context.get("user_draft") or "").strip()

    topic: dict[str, Any] | None = (
        runtime.catalog.topics.get(topic_id) if topic_id and topic_id in runtime.catalog.topics else None
    )
    state: dict[str, Any] = {}
    if topic is not None:
        try:
            learner = runtime.service_for(learner_id, topic["id"])
            raw_state = learner.state()
            if isinstance(raw_state, dict):
                state = raw_state
        except Exception:
            state = {}

    display = str(state.get("display") or state.get("phase") or "").strip().lower()
    current = state.get("current") if isinstance(state.get("current"), dict) else None
    state_card_id = current.get("card_id") if current else None

    if view == "paper":
        is_paper_submitted, matched_item = _paper_item_status(runtime, learner_id, paper_id, req_card_id)
        active_card_id = req_card_id or (matched_item.get("card_id") if isinstance(matched_item, dict) else None)
        resolved_topic, card = _find_card_in_runtime(runtime, topic_id, active_card_id)
        topic = topic or resolved_topic
        is_submitted = bool(is_paper_submitted) if is_paper_submitted is not None else False
        effective_mode = "paper_submitted" if is_submitted else "paper_unsubmitted"
    elif display in {"answer", "feedback"} and current:
        active_card_id = state_card_id or req_card_id
        resolved_topic, card = _find_card_in_runtime(runtime, topic["id"] if topic else topic_id, active_card_id)
        topic = topic or resolved_topic
        is_submitted = display == "feedback" or current.get("phase") == "feedback" or bool(current.get("revealed"))
        effective_mode = "quiz_submitted" if is_submitted else "quiz_unsubmitted"
    elif display == "introduction" and isinstance(state.get("introduction"), dict):
        card = None
        is_submitted = True
        effective_mode = "introduction"
    elif display in {"chunk", "memory_chunk"} and (isinstance(state.get("memory_chunk"), dict) or isinstance(state.get("chunk"), dict)):
        card = None
        is_submitted = True
        effective_mode = "memory_chunk"
    else:
        resolved_topic, card = _find_card_in_runtime(runtime, topic["id"] if topic else topic_id, req_card_id)
        topic = topic or resolved_topic
        if view == "answer" and card is not None:
            is_submitted = False
            effective_mode = "quiz_unsubmitted"
        else:
            is_submitted = True
            effective_mode = view or display or "general"

    point_summaries: list[str] = []
    if topic and card:
        point_map: dict[str, str] = {}
        for p in topic.get("points") or []:
            if isinstance(p, dict) and p.get("id"):
                point_map[p["id"]] = str(p.get("title") or p.get("name") or p["id"])
        for chunk in topic.get("memory_chunks") or []:
            if isinstance(chunk, dict):
                for p in chunk.get("points") or []:
                    if isinstance(p, dict) and p.get("id"):
                        point_map.setdefault(p["id"], str(p.get("title") or p.get("name") or p["id"]))
        for pid in card.get("point_ids") or []:
            label = point_map.get(pid)
            if label:
                point_summaries.append(str(label))

    info: dict[str, Any] = {
        "effective_mode": effective_mode,
        "is_submitted": is_submitted,
        "topic_id": topic["id"] if topic else topic_id,
        "topic_title": topic.get("title") if topic else None,
        "user_draft": user_draft[:600],
        "point_summaries": point_summaries,
    }

    if card is not None:
        info["card_id"] = card.get("id")
        info["card_title"] = card.get("title")
        info["question_prompt"] = _strip_html(card.get("question"))
        info["question_stem"] = _strip_html(card.get("html"))
        info["reference_answer"] = card.get("reference_answer")
        info["explanation_text"] = _strip_html(card.get("explanation_html"))
    elif effective_mode == "introduction" and isinstance(state.get("introduction"), dict):
        intro = state["introduction"]
        info["intro_title"] = intro.get("title")
        info["step_index"] = step_index
        info["step_total"] = step_total
        info["step_title"] = step_title
        info["lecture_text"] = step_text or _strip_html(intro.get("html") or intro.get("body_html"))[:2200]
    elif effective_mode == "memory_chunk" and isinstance(state.get("memory_chunk") or state.get("chunk"), dict):
        chunk = state.get("memory_chunk") or state.get("chunk")
        info["chunk_title"] = chunk.get("title")
        info["lecture_text"] = _strip_html(chunk.get("body_html") or chunk.get("html"))[:2200]
    elif step_text:
        info["step_title"] = step_title
        info["lecture_text"] = step_text[:2200]

    return info


def build_tutor_system_prompt(context_info: dict[str, Any], *, attach_context: bool = True) -> str:
    """Build the Japanese grammar tutor system prompt enforcing Socratic unsubmitted guidance."""
    parts = [
        "你是 GraspMemoEdu 日语语法精练系统内置的「日语语法 AI 助教」。",
        "回答原则：",
        "- 用清晰准确的中文解释，关键日语词句可酌情附带平假名读音与罗马音帮助记忆；",
        "- 语言精炼、条理分明，紧扣学习者的当前疑惑与核心语法点，不做冗长寒暄；",
        "- 基于日语现代标准语法回答，重点区分简体/敬体、自他动词、格助词功能差异以及「は/が」「だ/の/な」等常见易错点。",
    ]

    if not attach_context:
        return "\n".join(parts)

    is_submitted = bool(context_info.get("is_submitted", True))
    topic_title = context_info.get("topic_title")
    if topic_title:
        parts.append(f"\n【当前学习章节】{topic_title}")

    if not is_submitted and context_info.get("card_id"):
        parts.extend(
            [
                "\n【教学约束：未交卷启发式助教模式】",
                "学员当前正在作答以下题目且尚未提交：",
                "- **严格禁止**在回答中直接写出、拼出或变相泄漏空白处的准确日语答案、假名答案或固定答案词形；",
                "- 请优先使用苏格拉底启发式引导：先点明句子语境、成分角色（主题 vs 标识、施动者 vs 对象、修饰关系、时态与体裁约束），或给出思考检查清单引导学员自行填出答案；",
                "- 唯一例外：如果学员在对话中明确强烈要求“直接告诉我答案 / 我放弃请直接给答案”，才可直接给出完整答案及详细解析。",
            ]
        )
    elif context_info.get("card_id"):
        parts.append(
            "\n【当前教学模式：已交卷题解辅导】\n学员已提交本题或处于讲评状态，可直接对比常见误区并详细讲解正确答案、句意与扩展用法。"
        )
    elif context_info.get("intro_title") or context_info.get("chunk_title") or context_info.get("lecture_text"):
        parts.append(
            "\n【当前教学模式：讲义概念答疑】\n学员正在阅读下方讲义片段，请结合该片段直观解答，必要时补充 1-2 个简洁生活例句与避坑提示。"
        )

    if context_info.get("point_summaries"):
        parts.append(f"涉及知识点：{'；'.join(context_info['point_summaries'])}")
    if context_info.get("intro_title"):
        parts.append(f"讲义标题：{context_info['intro_title']}")
    if context_info.get("step_title"):
        idx = context_info.get("step_index")
        tot = context_info.get("step_total")
        progress = f"（第 {idx}/{tot} 张）" if idx and tot else ""
        parts.append(f"当前卡片{progress}：{context_info['step_title']}")
    if context_info.get("chunk_title"):
        parts.append(f"语法组块：{context_info['chunk_title']}")
    if context_info.get("lecture_text"):
        parts.append(f"当前页面内容：\n{context_info['lecture_text'][:2200]}")

    if context_info.get("card_id"):
        if is_submitted and context_info.get("card_title"):
            parts.append(f"题目考点：{context_info['card_title']}")
        if context_info.get("question_prompt"):
            parts.append(f"题干要求：{context_info['question_prompt']}")
        if context_info.get("question_stem"):
            parts.append(f"题干句子：\n{context_info['question_stem']}")
        if context_info.get("user_draft"):
            parts.append(f"学员当前输入草稿：{context_info['user_draft']}")
        if is_submitted and context_info.get("reference_answer") is not None:
            ref_str = json.dumps(context_info["reference_answer"], ensure_ascii=False)
            parts.append(f"参考答案（内部对照）：{ref_str}")
        elif not is_submitted and context_info.get("reference_answer") is not None:
            ref_str = json.dumps(context_info["reference_answer"], ensure_ascii=False)
            parts.append(f"内部标准答案（仅供助教把控引导方向，绝不可直接告诉学员）：{ref_str}")
        if context_info.get("explanation_text"):
            parts.append(f"内部语法要点参考：{context_info['explanation_text']}")

    return "\n".join(parts)


def _sanitized_upstream_error(status_code: int, raw_body: str) -> DomainError:
    detail = ""
    try:
        parsed = json.loads(raw_body)
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict):
                detail = str(err.get("message") or err.get("code") or "")
            elif isinstance(parsed.get("message"), str):
                detail = parsed["message"]
            elif isinstance(parsed.get("detail"), str):
                detail = parsed["detail"]
    except ValueError:
        detail = raw_body.strip()
    detail = detail.strip().replace("\r", " ").replace("\n", " ")[:240]
    hint = f"：{detail}" if detail else ""
    if status_code in {401, 403}:
        return DomainError("ai_auth_failed", f"AI 接口鉴权失败（HTTP {status_code}）{hint}", 502)
    return DomainError("ai_upstream_error", f"AI 接口调用失败（HTTP {status_code}）{hint}", 502)


def _extract_choice_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    msg = choices[0].get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        return msg["content"]
    delta = choices[0].get("delta")
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        return delta["content"]
    return ""


def _require_configured(cfg: dict[str, Any]) -> tuple[str, str, str]:
    base_url = validate_ai_base_url(cfg.get("base_url") or "")
    api_key = str(cfg.get("api_key") or "").strip()
    model = str(cfg.get("model") or "").strip()
    if not api_key:
        raise DomainError(
            "ai_not_configured",
            "尚未配置 AI API Key。请先在「AI 接口设置」填写或配置环境变量 OPENAI_API_KEY。",
            400,
        )
    if not model:
        raise DomainError("ai_not_configured", "尚未配置 AI 模型名称（Model）。", 400)
    return base_url, api_key, model


def _build_chat_payload(
    model: str,
    messages: list[dict[str, str]],
    *,
    stream: bool,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Build an OpenAI-compatible chat payload, omitting optional sampling overrides unless explicitly supplied."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def _is_temperature_unsupported_error(status_code: int, raw_body: str) -> bool:
    if status_code not in {400, 422}:
        return False
    return "temperature" in str(raw_body or "").lower()


def _strip_key(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k != key}


def test_ai_connection(
    data_dir: Path,
    override: dict[str, Any] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
    dotenv_path: Path | None = None,
) -> dict[str, Any]:
    """Verify OpenAI-compatible connectivity using override > local config > env."""
    cfg = resolve_ai_config(data_dir, dotenv_path=dotenv_path)
    ov = override or {}
    if ov.get("base_url"):
        cfg["base_url"] = str(ov["base_url"]).strip()
    if ov.get("api_key"):
        cfg["api_key"] = str(ov["api_key"]).strip()
    if ov.get("model"):
        cfg["model"] = str(ov["model"]).strip()

    base_url, api_key, model = _require_configured(cfg)
    chat_url, models_url = _endpoint_urls(base_url)
    headers = {"Authorization": f"Bearer {api_key}"}

    started = time.perf_counter()
    try:
        with httpx.Client(transport=transport, timeout=TEST_AI_TIMEOUT_SECONDS) as client:
            resp = client.get(models_url, headers=headers)
            if resp.status_code in {404, 405, 501}:
                probe_payload = _build_chat_payload(
                    model,
                    [{"role": "user", "content": "ping"}],
                    stream=False,
                    max_tokens=8,
                )
                chat_headers = {**headers, "Content-Type": "application/json"}
                chat_resp = client.post(chat_url, headers=chat_headers, json=probe_payload)
                if (
                    chat_resp.status_code in {400, 422}
                    and "max_tokens" in probe_payload
                    and "max_tokens" in chat_resp.text.lower()
                ):
                    chat_resp = client.post(
                        chat_url,
                        headers=chat_headers,
                        json=_strip_key(probe_payload, "max_tokens"),
                    )
                latency_ms = round((time.perf_counter() - started) * 1000)
                if chat_resp.status_code >= 400:
                    raise _sanitized_upstream_error(chat_resp.status_code, chat_resp.text)
                try:
                    data = chat_resp.json()
                    preview = _extract_choice_text(data)[:80]
                except ValueError:
                    preview = ""
                return {
                    "ok": True,
                    "probe": "chat_completions",
                    "latency_ms": latency_ms,
                    "base_url": base_url,
                    "model": model,
                    "reply_preview": preview,
                }

            latency_ms = round((time.perf_counter() - started) * 1000)
            if resp.status_code >= 400:
                raise _sanitized_upstream_error(resp.status_code, resp.text)
            model_count = 0
            try:
                body = resp.json()
                if isinstance(body, dict) and isinstance(body.get("data"), list):
                    model_count = len(body["data"])
            except ValueError:
                pass
            return {
                "ok": True,
                "probe": "models",
                "latency_ms": latency_ms,
                "base_url": base_url,
                "model": model,
                "available_models_count": model_count,
            }
    except DomainError:
        raise
    except httpx.HTTPError as exc:
        raise DomainError("ai_network_error", f"连接 AI 接口失败：{type(exc).__name__}", 502) from exc


def complete_chat(
    data_dir: Path,
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float | None = None,
    transport: httpx.BaseTransport | None = None,
    dotenv_path: Path | None = None,
) -> dict[str, Any]:
    """Perform a non-streaming OpenAI-compatible chat completion."""
    cfg = resolve_ai_config(data_dir, dotenv_path=dotenv_path)
    base_url, api_key, model = _require_configured(cfg)
    chat_url, _ = _endpoint_urls(base_url)

    payload = _build_chat_payload(
        model,
        [{"role": "system", "content": system_prompt}, *messages],
        stream=False,
        temperature=temperature,
    )
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(transport=transport, timeout=DEFAULT_AI_TIMEOUT_SECONDS) as client:
            for attempt in range(2):
                resp = client.post(chat_url, headers=headers, json=payload)
                if (
                    attempt == 0
                    and "temperature" in payload
                    and _is_temperature_unsupported_error(resp.status_code, resp.text)
                ):
                    payload = _strip_key(payload, "temperature")
                    continue
                break
    except httpx.HTTPError as exc:
        raise DomainError("ai_network_error", f"请求 AI 接口网络异常：{type(exc).__name__}", 502) from exc

    if resp.status_code >= 400:
        raise _sanitized_upstream_error(resp.status_code, resp.text)

    try:
        data = resp.json()
    except ValueError as exc:
        raise DomainError("ai_invalid_response", "AI 接口返回了非 JSON 响应。", 502) from exc

    reply = _extract_choice_text(data)
    return {
        "reply": reply,
        "model": str(data.get("model") or model),
        "usage": data.get("usage") if isinstance(data.get("usage"), dict) else None,
    }


def open_chat_stream(
    data_dir: Path,
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    temperature: float | None = None,
    transport: httpx.BaseTransport | None = None,
    dotenv_path: Path | None = None,
) -> Iterator[bytes]:
    """Open an upstream SSE chat completion stream and yield normalized SSE events.

    Upstream HTTP >= 400 errors raise DomainError eagerly before yielding response chunks.
    """
    cfg = resolve_ai_config(data_dir, dotenv_path=dotenv_path)
    base_url, api_key, model = _require_configured(cfg)
    chat_url, _ = _endpoint_urls(base_url)

    payload = _build_chat_payload(
        model,
        [{"role": "system", "content": system_prompt}, *messages],
        stream=True,
        temperature=temperature,
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    client = httpx.Client(transport=transport, timeout=DEFAULT_AI_TIMEOUT_SECONDS)
    stream_cm = None
    resp = None
    try:
        for attempt in range(2):
            stream_cm = client.stream("POST", chat_url, headers=headers, json=payload)
            resp = stream_cm.__enter__()
            if resp.status_code < 400:
                break
            try:
                body_text = resp.read().decode("utf-8", errors="replace")
            finally:
                stream_cm.__exit__(None, None, None)
                stream_cm = None
            if (
                attempt == 0
                and "temperature" in payload
                and _is_temperature_unsupported_error(resp.status_code, body_text)
            ):
                payload = _strip_key(payload, "temperature")
                continue
            client.close()
            raise _sanitized_upstream_error(resp.status_code, body_text)
    except DomainError:
        raise
    except httpx.HTTPError as exc:
        if stream_cm is not None:
            stream_cm.__exit__(None, None, None)
        client.close()
        raise DomainError("ai_network_error", f"请求 AI 接口网络异常：{type(exc).__name__}", 502) from exc
    except Exception:
        if stream_cm is not None:
            stream_cm.__exit__(None, None, None)
        client.close()
        raise

    assert stream_cm is not None and resp is not None

    content_type = (resp.headers.get("content-type") or "").lower()
    if "application/json" in content_type and "text/event-stream" not in content_type:
        try:
            raw_json = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw_json)
        except ValueError as exc:
            stream_cm.__exit__(None, None, None)
            client.close()
            raise DomainError("ai_invalid_response", "AI 接口返回了无效 JSON。", 502) from exc
        stream_cm.__exit__(None, None, None)
        client.close()
        reply = _extract_choice_text(data)
        resolved_model = str(data.get("model") or model)

        def _single_json_sse() -> Iterator[bytes]:
            if reply:
                yield f"data: {json.dumps({'delta': reply, 'model': resolved_model}, ensure_ascii=False)}\n\n".encode("utf-8")
            yield f"data: {json.dumps({'done': True, 'model': resolved_model, 'usage': data.get('usage')}, ensure_ascii=False)}\n\n".encode("utf-8")

        return _single_json_sse()

    def _iter_sse() -> Iterator[bytes]:
        resolved_model = model
        usage: dict[str, Any] | None = None
        sent_done = False
        try:
            for raw_line in resp.iter_lines():
                line = raw_line.strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data_part = line[5:].strip()
                if data_part == "[DONE]":
                    sent_done = True
                    yield f"data: {json.dumps({'done': True, 'model': resolved_model, 'usage': usage}, ensure_ascii=False)}\n\n".encode("utf-8")
                    break
                try:
                    chunk = json.loads(data_part)
                except ValueError:
                    continue
                if not isinstance(chunk, dict):
                    continue
                if chunk.get("model"):
                    resolved_model = str(chunk["model"])
                if isinstance(chunk.get("usage"), dict):
                    usage = chunk["usage"]
                if isinstance(chunk.get("error"), dict):
                    err_msg = str(chunk["error"].get("message") or "上游模型返回流式错误")
                    yield f"data: {json.dumps({'error': err_msg}, ensure_ascii=False)}\n\n".encode("utf-8")
                    sent_done = True
                    break
                choices = chunk.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    delta = choices[0].get("delta") or {}
                    text_piece = ""
                    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                        text_piece = delta["content"]
                    elif isinstance((choices[0].get("message") or {}).get("content"), str):
                        text_piece = choices[0]["message"]["content"]
                    if text_piece:
                        yield f"data: {json.dumps({'delta': text_piece, 'model': resolved_model}, ensure_ascii=False)}\n\n".encode("utf-8")
            if not sent_done:
                yield f"data: {json.dumps({'done': True, 'model': resolved_model, 'usage': usage}, ensure_ascii=False)}\n\n".encode("utf-8")
        finally:
            stream_cm.__exit__(None, None, None)
            client.close()

    return _iter_sse()
