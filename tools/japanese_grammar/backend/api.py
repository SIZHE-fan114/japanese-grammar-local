"""FastAPI application assembly and local-personal loopback security for Japanese grammar."""

from __future__ import annotations

from contextlib import asynccontextmanager, closing
import json
import os
from pathlib import Path
import secrets
import threading
from typing import Any, Literal
from urllib.parse import unquote
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from graspmemoedu.admin_students import register_admin_student_routes
from graspmemoedu.atomic_api import register_atomic_routes
from graspmemoedu.presence import Presence, PresencePulse
from graspmemoedu.public_limits import PublicLimitError
from graspmemoedu.review_api import register_review_routes
from graspmemoedu.review_cards import load_paper_types
from graspmemoedu.review_paper_api import register_paper_routes
from graspmemoedu.service import DomainError

from .ai import (
    build_tutor_system_prompt,
    complete_chat,
    extract_authoritative_learning_context,
    open_chat_stream,
    public_ai_config,
    resolve_ai_config,
    test_ai_connection,
    update_ai_config,
)
from .judge import per_blank_results
from .runtime import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SUBJECT_ID,
    DEFAULT_TOPIC_ID,
    LOCAL_LEARNER_ID,
    LocalGuideReader,
    LocalRuntime,
    SERVER_SERVICE_ID,
    remove_server_metadata,
)

MAX_REQUEST_BODY_BYTES = 65536
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "media-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_ALLOWED_FETCH_SITES = frozenset({"same-origin", "same-site", "none"})
_ALLOWED_WEB_SUFFIXES = frozenset({
    ".html", ".js", ".mjs", ".css", ".json", ".svg",
    ".woff2", ".woff", ".ttf", ".png", ".jpg", ".jpeg", ".webp", ".ico",
})
_STATIC_MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}


def _media_type_for(path: Path) -> str | None:
    return _STATIC_MEDIA_TYPES.get(path.suffix.lower())


class BodyTooLargeError(Exception):
    """Raised before JSON parsing when streamed request bytes exceed limit."""


class BodyLimitMiddleware:
    """Enforce hard streamed byte ceiling on incoming request bodies."""

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers") or []}
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length.decode("ascii")) > self.max_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": {"code": "body_too_large", "message": "请求体超出允许大小限制。"}},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(
                    status_code=400,
                    content={"detail": {"code": "invalid_content_length", "message": "无效的 Content-Length。"}},
                )
                await response(scope, receive, send)
                return

        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message.get("type") == "http.request":
                chunk = message.get("body", b"")
                total += len(chunk)
                if total > self.max_bytes:
                    raise BodyTooLargeError()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except BodyTooLargeError:
            response = JSONResponse(
                status_code=413,
                content={"detail": {"code": "body_too_large", "message": "请求体超出允许大小限制。"}},
            )
            await response(scope, receive, send)


class AccessLoginPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invitation_code: str = Field(default="", max_length=256)


class CatalogSelectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: str = Field(min_length=1, max_length=128)
    subject_id: str | None = Field(default=None, max_length=64)
    subject: str | None = Field(default=None, max_length=64)


class ProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    selected_course_id: str | None = Field(default=None, min_length=1, max_length=128)


class FeedbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    course_id: str | None = Field(default=None, max_length=128)
    topic_id: str | None = Field(default=None, max_length=128)
    task_id: str | None = Field(default=None, max_length=160)
    question_id: str | None = Field(default=None, max_length=160)


class ChoosePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)
    topic_id: str | None = Field(default=None, max_length=128)
    attempt_id: str | None = Field(default=None, max_length=128)
    step_id: str | None = Field(default=None, max_length=128)
    choice: Literal["mastered", "unmastered", "learn", "review"]


class ContinuePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)
    topic_id: str | None = Field(default=None, max_length=128)
    attempt_id: str | None = Field(default=None, max_length=128)
    step_id: str | None = Field(default=None, max_length=128)


class SelectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str = Field(min_length=1, max_length=128)
    topic_id: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)
    expected_revision: int | None = Field(default=None, ge=0)
    attempt_id: str | None = Field(default=None, max_length=128)


class PausePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    topic_id: str | None = Field(default=None, max_length=128)
    attempt_id: str | None = Field(default=None, max_length=128)
    step_id: str | None = Field(default=None, max_length=128)
    expected_revision: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=500)


class SkipPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)
    topic_id: str | None = Field(default=None, max_length=128)
    attempt_id: str | None = Field(default=None, max_length=128)
    step_id: str | None = Field(default=None, max_length=128)
    module_id: str | None = Field(default=None, max_length=128)


class RevealPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)
    topic_id: str | None = Field(default=None, max_length=128)
    attempt_id: str | None = Field(default=None, max_length=128)
    step_id: str | None = Field(default=None, max_length=128)
    question_id: str | None = Field(default=None, max_length=160)


class SubmitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)
    topic_id: str | None = Field(default=None, max_length=128)
    attempt_id: str | None = Field(default=None, max_length=128)
    step_id: str | None = Field(default=None, max_length=128)
    answer: Any = None
    elapsed_ms: int | None = Field(default=None, ge=0, le=86400000)
    self_rating: int | None = Field(default=None, ge=1, le=5)
    question_id: str | None = Field(default=None, max_length=160)
    card_id: str | None = Field(default=None, max_length=160)


class SimplePresencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(min_length=1, max_length=128)
    active: bool = True
    kind: str = Field(default="topic", max_length=32)


class PauseUnlockPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(min_length=1, max_length=128)
    module_id: str | None = Field(default=None, max_length=128)
    pause_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    event_id: str | None = Field(default=None, min_length=1, max_length=128)


class AiConfigUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    model: str | None = Field(default=None, max_length=160)
    stream: bool | None = None
    clear_api_key: bool = False
    reset_to_env: bool = False


class AiTestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    model: str | None = Field(default=None, max_length=160)


class AiChatMessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class AiChatContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str | None = Field(default=None, max_length=128)
    view: str | None = Field(default=None, max_length=64)
    paper_id: str | None = Field(default=None, max_length=160)
    card_id: str | None = Field(default=None, max_length=160)
    step_index: int | None = Field(default=None, ge=1, le=200)
    step_total: int | None = Field(default=None, ge=1, le=200)
    step_title: str | None = Field(default=None, max_length=300)
    step_text: str | None = Field(default=None, max_length=4000)
    user_draft: str | None = Field(default=None, max_length=1000)


class AiChatPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[AiChatMessagePayload] = Field(min_length=1, max_length=24)
    attach_context: bool = True
    stream: bool | None = None
    context: AiChatContextPayload | None = None


def _resolve_topic_id(runtime: LocalRuntime, requested: str | None) -> str:
    if requested is not None and requested != "":
        if requested not in runtime.catalog.topics:
            raise DomainError("unknown_topic", f"未知 Topic：{requested}", 404)
        return requested
    if DEFAULT_TOPIC_ID in runtime.catalog.topics:
        return DEFAULT_TOPIC_ID
    return next(iter(runtime.catalog.topics))


def _resolve_subject(subject_id: str | None, subject: str | None) -> str | None:
    return subject_id if subject_id is not None else subject


def _attach_fill_blank_results(learner: Any, target: dict[str, Any], *, card_id: str | None = None, step: dict[str, Any] | None = None, answer: Any = None) -> None:
    if not isinstance(target, dict) or isinstance(target.get("blank_results"), dict):
        return
    question = None
    atomic = getattr(learner, "atomic", None)
    if atomic is not None and card_id and card_id in getattr(atomic, "questions", {}):
        question = atomic.questions[card_id]
    if question is None and step is not None:
        try:
            question = learner.question_for_step(step)
        except Exception:
            question = None
    if isinstance(question, dict):
        interaction = question.get("interaction")
        q_type = (
            interaction.get("type")
            if isinstance(interaction, dict)
            else question.get("type")
        )
        if str(q_type or "").strip() == "fill_blank":
            items = per_blank_results(question, answer)
            target["blank_results"] = {
                str(item["id"]): bool(item.get("correct"))
                for item in items
                if isinstance(item, dict) and item.get("id")
            }
            if "blank_feedback" not in target:
                target["blank_feedback"] = items
            if "choice_feedback" not in target or not isinstance(target.get("choice_feedback"), dict):
                target["choice_feedback"] = {"items": items}


def _public_state(access: dict[str, Any], runtime: LocalRuntime, topic_id: str) -> dict[str, Any]:
    learner = runtime.service_for(access["learner_id"], topic_id)
    state = dict(learner.state())
    with closing(runtime.access_store._connect()) as con:
        now_iso = runtime.clock().isoformat()
        ready = bool(runtime.dependency_policy.ready(con, access, topic_id, current_time=now_iso))
        blockers: list[dict[str, Any]] = []
        if not ready:
            for parent_id in runtime.dependency_policy.required_parents(topic_id):
                described = runtime.dependency_policy.describe(con, access, parent_id)
                if described is not None:
                    title = described.get("title") or runtime.catalog.topics.get(parent_id, {}).get("title", parent_id)
                    blockers.append({
                        "id": described.get("id", parent_id),
                        "topic_id": described.get("id", parent_id),
                        "title": title,
                        **described,
                    })
    state["dependency_ready"] = ready
    state["dependency_blocked"] = not ready
    if blockers:
        state["blocking_topics"] = blockers

    if state.get("pause") is None and not learner.course.get("modules"):
        with closing(learner._connect()) as con:
            t_row = (
                con.execute(
                    "SELECT body FROM topics WHERE learner=? AND topic=?",
                    (access["learner_id"], topic_id),
                ).fetchone()
                if runtime._table_exists(con, "topics")
                else None
            )
        if t_row is not None:
            raw_body = __import__("json").loads(t_row["body"])
            raw_pause = (raw_body.get("atomic") or {}).get("pause") or raw_body.get("pause")
            if isinstance(raw_pause, dict):
                state["pause"] = raw_pause
    if learner.review_backend is not None:
        state["schedule"] = runtime.schedule(learner)
        state["topic_pause"] = state.get("pause")
        with closing(learner._connect()) as con:
            row = (
                con.execute(
                    "SELECT event_id, module_id, reason, created_at FROM review_topic_pauses WHERE learner=? AND topic=?",
                    (access["learner_id"], topic_id),
                ).fetchone()
                if runtime._table_exists(con, "review_topic_pauses")
                else None
            )
        state["review_pause"] = dict(row) if row is not None else None
    else:
        state["schedule"] = None
        state["topic_pause"] = state.get("pause")
        state["review_pause"] = None
    state["outstanding_submissions"] = runtime.outstanding_count(access["learner_id"], topic_id)
    state["content_references"] = runtime.references_for(access, topic_id)
    state["access"] = access

    # Project UnifiedLearningService step-based section introductions and completions
    # into top-level phase/introduction/actions expected by web/app.js.
    if (
        not state.get("phase")
        and isinstance(state.get("steps"), list)
        and state["steps"]
    ):
        active_step_id = state.get("active_step_id") or state.get("current_step_id")
        latest = next(
            (
                step
                for step in reversed(state["steps"])
                if isinstance(step, dict)
                and (
                    (active_step_id and step.get("id") == active_step_id)
                    or step.get("current")
                    or step.get("active")
                )
            ),
            state["steps"][-1],
        )
        if isinstance(latest, dict):
            kind = latest.get("kind")
            if kind == "introduction" and not state.get("current") and not state.get("chunk"):
                intro = {
                    key: latest[key]
                    for key in ("introduction_id", "title", "html", "explanation_html", "example", "footnotes", "section")
                    if key in latest
                }
                intro["id"] = latest.get("introduction_id") or latest.get("id")
                state["phase"] = "introduction"
                state["introduction"] = intro
                if not state.get("actions") and isinstance(latest.get("actions"), list):
                    state["actions"] = list(latest["actions"])
            elif kind == "completion" or state.get("completed_at"):
                state["phase"] = latest.get("phase") or "completed"
                if not state.get("actions") and isinstance(latest.get("actions"), list):
                    state["actions"] = list(latest["actions"])
    elif not state.get("phase") and state.get("completed_at"):
        state["phase"] = "completed"

    current = state.get("current")
    if isinstance(current, dict):
        if current.get("phase") == "feedback" or current.get("correct") is not None:
            current_copy = dict(current)
            _attach_fill_blank_results(
                learner,
                current_copy,
                card_id=current_copy.get("card_id"),
                answer=current_copy.get("answer", state.get("submitted_answer")),
            )
            state["current"] = current_copy
            current = current_copy
        if isinstance(state.get("feedback"), dict):
            fb = dict(state["feedback"])
            _attach_fill_blank_results(
                learner,
                fb,
                card_id=current.get("card_id"),
                answer=state.get("submitted_answer", current.get("answer")),
            )
            state["feedback"] = fb
    if isinstance(state.get("steps"), list):
        enriched_steps = []
        for step in state["steps"]:
            if isinstance(step, dict) and isinstance(step.get("feedback"), dict):
                step_copy = dict(step)
                fb_copy = dict(step_copy["feedback"])
                _attach_fill_blank_results(
                    learner,
                    fb_copy,
                    card_id=step_copy.get("card_id"),
                    step=step_copy,
                    answer=step_copy.get("answer"),
                )
                step_copy["feedback"] = fb_copy
                enriched_steps.append(step_copy)
            else:
                enriched_steps.append(step)
        state["steps"] = enriched_steps

    app_services = getattr(runtime, "_app_services_view", None)
    if app_services is not None:
        app_services[access["learner_id"]] = learner
    return state


def _public_submission(
    access: dict[str, Any],
    runtime: LocalRuntime,
    topic_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    learner = runtime.service_for(access["learner_id"], topic_id)
    payload = dict(record)
    state = _public_state(access, runtime, topic_id)
    if payload.get("status") == "judged":
        sub_meta = getattr(runtime, "_submission_meta", {}).get(payload.get("submission_id"))
        if sub_meta is not None:
            meta_card_id, meta_answer = sub_meta
            _attach_fill_blank_results(
                learner,
                payload,
                card_id=meta_card_id,
                answer=meta_answer,
            )
        if not isinstance(payload.get("blank_results"), dict):
            fb = state.get("feedback")
            if isinstance(fb, dict) and isinstance(fb.get("blank_results"), dict):
                payload["blank_results"] = fb["blank_results"]
                if "blank_feedback" in fb and "blank_feedback" not in payload:
                    payload["blank_feedback"] = fb["blank_feedback"]
                if "choice_feedback" in fb and "choice_feedback" not in payload:
                    payload["choice_feedback"] = fb["choice_feedback"]
            elif isinstance(state.get("current"), dict):
                _attach_fill_blank_results(
                    learner,
                    payload,
                    card_id=state["current"].get("card_id"),
                    answer=payload.get("answer", state.get("submitted_answer")),
                )
    payload["state"] = state
    return payload


def _resolve_static_asset(web_dir: Path, relative_path: str) -> Path | None:
    """Resolve static web assets strictly inside web_dir, rejecting symlinks and dotfiles."""
    if not web_dir.is_dir():
        return None
    decoded = unquote(relative_path)
    if "\x00" in decoded or "\\" in decoded or ":" in decoded:
        return None
    clean = decoded.lstrip("/")
    if not clean:
        clean = "index.html"
    parts = clean.split("/")
    if not parts or any(not part or part in {".", ".."} or part.startswith(".") for part in parts):
        return None
    root_resolved = web_dir.resolve()
    current = root_resolved
    for part in parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        resolved = current.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(root_resolved):
        return None
    if resolved.is_dir():
        index = resolved / "index.html"
        if index.is_file() and not index.is_symlink():
            return index
        return None
    if not resolved.is_file() or resolved.suffix.lower() not in _ALLOWED_WEB_SUFFIXES:
        return None
    return resolved


def create_app(
    runtime: LocalRuntime | None = None,
    *,
    packages_dir: str | Path | None = None,
    data_dir: str | Path | None = None,
    web_dir: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    reset: bool = False,
    allow_hosts: tuple[str, ...] = (),
) -> FastAPI:
    """Create the thin-adapter FastAPI app over LocalRuntime and shared routers."""
    active_runtime = runtime or LocalRuntime(
        packages_dir=packages_dir,
        data_dir=data_dir,
        web_dir=web_dir,
        host=host,
        port=port,
        reset=reset,
    )
    session_nonce = secrets.token_urlsafe(24)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        active_runtime.recover_interrupted()
        try:
            yield
        finally:
            active_runtime.join_judge_threads(timeout=5.0)
            remove_server_metadata(
                active_runtime.data_dir,
                instance_id=active_runtime.instance_id,
            )

    app = FastAPI(
        title="GraspMemoEdu Japanese Grammar (Local Personal)",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)

    allowed_hosts = {
        f"127.0.0.1:{active_runtime.port}",
        f"localhost:{active_runtime.port}",
        *(h.lower() for h in allow_hosts),
    }
    allowed_origins = {
        f"http://127.0.0.1:{active_runtime.port}",
        f"http://localhost:{active_runtime.port}",
    }

    @app.middleware("http")
    async def loopback_security_middleware(request: Request, call_next):
        request.state.public_transport = False
        host_header = (request.headers.get("host") or "").strip().lower()
        if host_header not in allowed_hosts:
            return JSONResponse(
                status_code=403,
                content={"detail": {"code": "invalid_host", "message": "仅允许本机回环地址访问。"}},
            )

        origin_header = (request.headers.get("origin") or "").strip().lower()
        if origin_header and origin_header not in allowed_origins:
            return JSONResponse(
                status_code=403,
                content={"detail": {"code": "invalid_origin", "message": "禁止跨来源请求。"}},
            )

        fetch_site = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if request.method in _MUTATING_METHODS and fetch_site and fetch_site not in _ALLOWED_FETCH_SITES:
            return JSONResponse(
                status_code=403,
                content={"detail": {"code": "invalid_fetch_site", "message": "禁止跨站写入请求。"}},
            )

        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError):
        headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, PublicLimitError) else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(_request: Request, _exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "invalid_request", "message": "请求字段不完整或格式错误，请刷新后重试。"}},
        )

    app.state.runtime = active_runtime
    app.state.settings = active_runtime.settings
    app.state.service = active_runtime.default_service
    app.state.access_store = active_runtime.access_store
    app.state.catalog = active_runtime.catalog
    app.state.dashboard_store = active_runtime.dashboard_store
    app.state.subjects = active_runtime.subjects
    app.state.training_catalog = active_runtime.training
    app.state.public_limits = active_runtime.public_limits
    app.state.review_paper_types = load_paper_types()
    app.state.learning_services = {LOCAL_LEARNER_ID: active_runtime.default_service}
    active_runtime._app_services_view = app.state.learning_services

    def resolve_access(request: Request) -> dict[str, Any]:
        return active_runtime.access_store.resolve(request.headers.get("x-learning-identity"))

    def identity(
        request: Request,
        topic_id: str | None = None,
        feature: str | None = None,
        **_extra: Any,
    ):
        access = resolve_access(request)
        resolved_subject = _resolve_subject(
            request.query_params.get("subject_id"),
            request.query_params.get("subject"),
        )
        if resolved_subject is not None:
            active_runtime.subjects.authorize_subject(access, resolved_subject)
        resolved_topic = _resolve_topic_id(
            active_runtime,
            topic_id if topic_id is not None else request.query_params.get("topic_id"),
        )
        if resolved_subject is not None:
            active_runtime.subjects.authorize_topic(resolved_subject, resolved_topic)
        active_runtime.access_store.authorize(access, resolved_topic, feature)
        learner = active_runtime.service_for(
            access["learner_id"],
            resolved_topic,
            request.headers.get("x-learning-identity"),
        )
        app.state.learning_services[access["learner_id"]] = learner
        return access, learner

    @app.get("/api/health")
    def health():
        topics = list(active_runtime.catalog.topics)
        return {
            "ok": True,
            "status": "ok",
            "service": SERVER_SERVICE_ID,
            "service_id": SERVER_SERVICE_ID,
            "mode": "local-personal",
            "learner_id": LOCAL_LEARNER_ID,
            "host": active_runtime.host,
            "port": active_runtime.port,
            "pid": os.getpid(),
            "instance_id": active_runtime.instance_id,
            "process_started_at": active_runtime.process_started_at,
            "subject_id": active_runtime.subject_id or DEFAULT_SUBJECT_ID,
            "course_id": active_runtime.course_id,
            "topic_ids": topics,
            "topics": topics,
        }

    @app.get("/api/session")
    def session():
        return {
            "mode": "local-personal",
            "session_nonce": session_nonce,
            "subject_id": active_runtime.subject_id,
            "course_id": active_runtime.course_id,
        }

    @app.get("/api/access")
    def get_access(request: Request):
        return {
            "access": resolve_access(request),
            "mode": "local-personal",
        }

    @app.post("/api/access/guest")
    def post_guest():
        return active_runtime.access_store.create_guest()

    @app.post("/api/access/login")
    def post_login(payload: AccessLoginPayload, request: Request):
        return active_runtime.access_store.login(
            payload.invitation_code,
            request.headers.get("x-learning-identity"),
        )

    @app.post("/api/access/logout")
    def post_logout(request: Request):
        return active_runtime.access_store.logout(request.headers.get("x-learning-identity"))

    @app.get("/api/subjects")
    def list_subjects(request: Request):
        access = resolve_access(request)
        return active_runtime.subjects.public(access)

    @app.get("/api/catalog")
    def get_catalog(
        request: Request,
        subject_id: str | None = Query(default=None, max_length=64),
        subject: str | None = Query(default=None, max_length=64),
    ):
        access = resolve_access(request)
        return active_runtime.dashboard_store.catalog_view(
            access,
            subject_id=_resolve_subject(subject_id, subject),
        )

    @app.post("/api/catalog/select")
    def select_catalog_course(payload: CatalogSelectPayload, request: Request):
        access = resolve_access(request)
        return active_runtime.dashboard_store.select_course(
            access,
            payload.course_id,
            subject_id=_resolve_subject(payload.subject_id, payload.subject),
        )

    @app.get("/api/dashboard")
    def get_dashboard(
        request: Request,
        course_id: str | None = Query(default=None, max_length=128),
        cursor: str | None = Query(default=None, max_length=256),
        limit: int = Query(default=25, ge=1, le=50),
        subject_id: str | None = Query(default=None, max_length=64),
        subject: str | None = Query(default=None, max_length=64),
        root_id: str | None = Query(default=None, max_length=128),
    ):
        access = resolve_access(request)
        active_runtime.recover_cooldowns(access)
        return active_runtime.dashboard_store.dashboard(
            access,
            course_id=course_id,
            cursor=cursor,
            limit=limit,
            subject_id=_resolve_subject(subject_id, subject),
            root_id=root_id,
        )

    @app.get("/api/tasks/{task_id}/answers")
    def get_task_answers(
        task_id: str,
        request: Request,
        subject_id: str | None = Query(default=None, max_length=64),
        subject: str | None = Query(default=None, max_length=64),
    ):
        access = resolve_access(request)
        return active_runtime.dashboard_store.answers(
            access,
            task_id,
            subject_id=_resolve_subject(subject_id, subject),
        )

    @app.get("/api/profile")
    def get_profile(request: Request):
        access = resolve_access(request)
        return active_runtime.dashboard_store.profile(access)

    @app.post("/api/profile")
    def update_profile(payload: ProfilePayload, request: Request):
        access = resolve_access(request)
        return active_runtime.dashboard_store.update_profile(
            access,
            payload.model_dump(exclude_none=True),
        )

    @app.post("/api/feedback")
    def save_feedback(payload: FeedbackPayload, request: Request):
        access = resolve_access(request)
        return active_runtime.dashboard_store.save_feedback(
            access,
            payload.model_dump(exclude_none=True),
        )

    @app.get("/api/guide")
    def get_guide(
        request: Request,
        subject_id: str | None = Query(default=None, max_length=64),
        subject: str | None = Query(default=None, max_length=64),
    ):
        access = resolve_access(request)
        resolved_subject = _resolve_subject(subject_id, subject) or active_runtime.subject_id
        active_runtime.subjects.authorize_subject(access, resolved_subject)
        if resolved_subject in active_runtime.subjects.test_materials.guides:
            active_runtime.subjects.test_materials.require_guide(resolved_subject, access)
        source = active_runtime.subjects.guide_paths.get(resolved_subject)
        if source is None or not source.is_file():
            return {
                "status": "empty",
                "html": "",
                "math_css": "",
                "version": "none",
                "modified_at": None,
            }
        reader = LocalGuideReader(source)
        return reader.read(f"/guide-assets/{resolved_subject}", access=access)

    @app.get("/api/graphs")
    def list_graphs(
        request: Request,
        subject_id: str | None = Query(default=None, max_length=64),
        subject: str | None = Query(default=None, max_length=64),
    ):
        access = resolve_access(request)
        resolved_subject = _resolve_subject(subject_id, subject)
        if resolved_subject is not None:
            active_runtime.subjects.authorize_subject(access, resolved_subject)
        raw_all = active_runtime.graph_store.all()
        graphs = list(raw_all.values()) if isinstance(raw_all, dict) else list(raw_all)
        public_graphs = []
        for graph in graphs:
            if resolved_subject is not None and graph.get("subject_id") != resolved_subject:
                continue
            item = active_runtime.graph_store.public(graph, access)
            if item is not None:
                public_graphs.append(item)
        return {"graphs": public_graphs}

    @app.get("/api/graphs/{course_id}")
    def get_graph(
        course_id: str,
        request: Request,
        subject_id: str | None = Query(default=None, max_length=64),
        subject: str | None = Query(default=None, max_length=64),
    ):
        access = resolve_access(request)
        resolved_subject = _resolve_subject(subject_id, subject)
        if resolved_subject is not None:
            active_runtime.subjects.authorize_subject(access, resolved_subject)
        graph = active_runtime.graph_store.load(course_id)
        if resolved_subject is not None and graph.get("subject_id") != resolved_subject:
            raise DomainError("graph_not_found", "未找到该学科下的课程知识图谱。", 404)
        result = active_runtime.graph_store.public(graph, access)
        if result is None:
            raise DomainError("graph_not_found", "未找到可访问的课程知识图谱。", 404)
        return result

    @app.get("/api/state")
    def get_state(request: Request, topic_id: str | None = Query(default=None, max_length=128)):
        access, learner = identity(request, topic_id=topic_id, feature="learn")
        return _public_state(access, active_runtime, learner.course["id"])

    @app.get("/api/reviews")
    def list_reviews(
        request: Request,
        subject_id: str | None = Query(default=None, max_length=64),
        subject: str | None = Query(default=None, max_length=64),
    ):
        access = resolve_access(request)
        resolved_subject = _resolve_subject(subject_id, subject)
        if resolved_subject is not None:
            active_runtime.subjects.authorize_subject(access, resolved_subject)
        items: list[dict[str, Any]] = []
        for topic_meta in access.get("topics", []):
            tid = topic_meta["id"]
            if resolved_subject is not None and active_runtime.subjects.topic_subject(tid) != resolved_subject:
                continue
            learner = active_runtime.service_for(access["learner_id"], tid)
            backend = getattr(learner, "review_backend", None)
            if backend is not None:
                items.extend(backend.due())
        return {"reviews": items, "items": items}

    @app.post("/api/choose")
    def post_choose(
        payload: ChoosePayload,
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
    ):
        target_topic = topic_id or payload.topic_id
        access, learner = identity(request, topic_id=target_topic, feature="learn")
        active_runtime.dependency_policy.require(access, learner.course["id"])
        action_data = payload.model_dump(exclude_none=True)
        action_data.pop("topic_id", None)
        learner.choose(action_data)
        return _public_state(access, active_runtime, learner.course["id"])

    @app.post("/api/continue")
    def post_continue(
        payload: ContinuePayload,
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
    ):
        target_topic = topic_id or payload.topic_id
        access, learner = identity(request, topic_id=target_topic, feature="learn")
        active_runtime.dependency_policy.require(access, learner.course["id"])
        action_data = payload.model_dump(exclude_none=True)
        action_data.pop("topic_id", None)
        learner.advance(action_data)
        return _public_state(access, active_runtime, learner.course["id"])

    @app.post("/api/select")
    def post_select(
        payload: SelectPayload,
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
    ):
        target_topic = topic_id or payload.topic_id
        access, learner = identity(request, topic_id=target_topic, feature="review_history")
        action_data = payload.model_dump(exclude_none=True)
        action_data.pop("topic_id", None)
        learner.select(action_data)
        return _public_state(access, active_runtime, learner.course["id"])

    @app.post("/api/pause")
    def post_pause(
        payload: PausePayload,
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
    ):
        target_topic = topic_id or payload.topic_id
        access, learner = identity(request, topic_id=target_topic, feature="pause_topic")
        action_data = payload.model_dump(exclude_none=True)
        action_data.pop("topic_id", None)
        action_data.setdefault("request_id", uuid.uuid4().hex)
        if getattr(learner, "atomic", None) is not None and not learner.course.get("modules"):
            learner.atomic.pause(action_data)
        else:
            learner.pause(action_data)
        return _public_state(access, active_runtime, learner.course["id"])

    @app.post("/api/skip")
    def post_skip(
        payload: SkipPayload,
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
    ):
        target_topic = topic_id or payload.topic_id
        access, learner = identity(request, topic_id=target_topic, feature="skip_module")
        active_runtime.dependency_policy.require(access, learner.course["id"])
        action_data = payload.model_dump(exclude_none=True)
        action_data.pop("topic_id", None)
        learner.skip_module(action_data)
        return _public_state(access, active_runtime, learner.course["id"])

    @app.post("/api/reveal")
    def post_reveal(
        payload: RevealPayload,
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
    ):
        target_topic = topic_id or payload.topic_id
        access, learner = identity(request, topic_id=target_topic, feature="training_self_rating")
        action_data = payload.model_dump(exclude_none=True)
        action_data.pop("topic_id", None)
        learner.reveal(action_data)
        return _public_state(access, active_runtime, learner.course["id"])

    @app.post("/api/submit")
    def post_submit(
        payload: SubmitPayload,
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
    ):
        target_topic = topic_id or payload.topic_id
        access, learner = identity(request, topic_id=target_topic, feature="submit_answer")
        resolved_topic = learner.course["id"]
        active_runtime.dependency_policy.require(access, resolved_topic)
        pre_state = learner.state()
        pre_current = pre_state.get("current") if isinstance(pre_state, dict) else None
        pre_card_id = pre_current.get("card_id") if isinstance(pre_current, dict) else None
        sub_data = payload.model_dump(exclude_none=True)
        sub_data.pop("topic_id", None)
        with active_runtime._admission_lock:
            record = learner.submit(sub_data)
        submission_id = record["submission_id"]
        if not hasattr(active_runtime, "_submission_meta"):
            active_runtime._submission_meta = {}
        active_runtime._submission_meta[submission_id] = (pre_card_id, payload.answer)
        if record.get("status") == "pending":
            if learner.instant_submission(submission_id):
                learner.process_submission(submission_id)
            elif active_runtime.begin_in_flight(submission_id, access["learner_id"], resolved_topic):
                def run_judge() -> None:
                    try:
                        learner.process_submission(submission_id)
                    finally:
                        active_runtime.finish_in_flight(submission_id)

                active_runtime.spawn_judge_thread(
                    run_judge,
                    name=f"answer-judge-{submission_id[:12]}",
                )
            record = learner.submission(submission_id)
        return _public_submission(access, active_runtime, resolved_topic, record)

    @app.get("/api/submissions/{submission_id}")
    def get_submission(
        submission_id: str,
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
    ):
        access, learner = identity(request, topic_id=topic_id, feature="learn")
        record = learner.submission(submission_id)
        return _public_submission(access, active_runtime, learner.course["id"], record)

    @app.get("/api/pauses")
    def list_pauses(
        request: Request,
        topic_id: str | None = Query(default=None, max_length=128),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=1000000),
    ):
        access = resolve_access(request)
        if topic_id is not None:
            active_runtime.access_store.authorize(access, topic_id)
        return active_runtime.pause_rows(
            access["learner_id"],
            topic_id=topic_id,
            limit=limit,
            offset=offset,
        )

    @app.post("/api/pauses/unlock")
    def unlock_pause(payload: PauseUnlockPayload, request: Request):
        access = resolve_access(request)
        active_runtime.access_store.authorize(access, payload.topic_id)
        event_id = payload.pause_event_id or payload.event_id
        if not event_id:
            raise DomainError("invalid_pause_event", "缺少暂停事件标识 pause_event_id。", 422)
        return active_runtime.unlock_pause(
            access["learner_id"],
            topic_id=payload.topic_id,
            module_id=payload.module_id,
            pause_event_id=event_id,
        )

    register_atomic_routes(
        app,
        active_runtime.catalog,
        active_runtime.access_store,
        active_runtime.subjects,
        active_runtime.dependency_policy,
        clock=active_runtime.clock,
    )
    register_review_routes(
        app,
        identity,
        active_runtime._admission_lock,
        active_runtime.public_limits,
        active_runtime.schedule_submission,
        active_runtime.outstanding_submissions,
        active_runtime.dependency_policy,
        active_runtime.references_for,
    )
    register_paper_routes(
        app,
        active_runtime.training,
        active_runtime.catalog,
        active_runtime.dependency_policy,
        active_runtime.access_store,
        active_runtime.subjects,
        active_runtime.service_for,
        active_runtime._admission_lock,
        active_runtime.public_limits,
        active_runtime.schedule_submission,
        active_runtime.outstanding_submissions,
        clock=active_runtime.clock,
    )
    register_admin_student_routes(
        app,
        active_runtime.catalog,
        active_runtime.access_store,
        active_runtime.subjects,
        active_runtime.dashboard_store,
        active_runtime.training,
        active_runtime.clock,
    )
    presence_store = Presence(active_runtime.access_store, active_runtime.catalog, active_runtime.clock)
    app.state.presence = presence_store
    presence_seq_lock = threading.Lock()
    presence_sequences: dict[tuple[str, str], int] = {}

    @app.post("/api/presence")
    def record_presence(payload: dict[str, Any], request: Request):
        access = resolve_access(request)
        if "stream_id" in payload:
            try:
                pulse = PresencePulse.model_validate(payload)
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail=exc.errors()) from exc
            return presence_store.pulse(access, pulse)
        try:
            simple = SimplePresencePayload.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        stream_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{access['learner_id']}:{simple.topic_id}"))
        with presence_seq_lock:
            seq = presence_sequences.get((access["learner_id"], simple.topic_id), 0) + 1
            presence_sequences[(access["learner_id"], simple.topic_id)] = seq
        pulse = PresencePulse(
            stream_id=stream_id,
            sequence=seq,
            visible=bool(simple.active),
            topic_ids=[simple.topic_id],
        )
        return presence_store.pulse(access, pulse)

    @app.get("/api/ai/config")
    def get_ai_config(request: Request):
        resolve_access(request)
        return public_ai_config(active_runtime.data_dir)

    @app.put("/api/ai/config")
    def put_ai_config(payload: AiConfigUpdatePayload, request: Request):
        resolve_access(request)
        return update_ai_config(
            active_runtime.data_dir,
            payload.model_dump(exclude_unset=True),
        )

    @app.post("/api/ai/test")
    def post_ai_test(payload: AiTestPayload, request: Request):
        resolve_access(request)
        return test_ai_connection(
            active_runtime.data_dir,
            payload.model_dump(exclude_none=True),
            transport=getattr(active_runtime, "ai_transport", None),
        )

    @app.post("/api/ai/chat")
    def post_ai_chat(payload: AiChatPayload, request: Request):
        access = resolve_access(request)
        ctx_dict = payload.context.model_dump(exclude_none=True) if payload.context else {}
        req_topic = ctx_dict.get("topic_id")
        if req_topic and req_topic in active_runtime.catalog.topics:
            active_runtime.access_store.authorize(access, req_topic)
        ctx_info = extract_authoritative_learning_context(
            active_runtime,
            access["learner_id"],
            ctx_dict,
        )
        system_prompt = build_tutor_system_prompt(
            ctx_info,
            attach_context=payload.attach_context,
        )
        chat_messages = [
            {"role": item.role, "content": item.content}
            for item in payload.messages
        ]
        cfg = resolve_ai_config(active_runtime.data_dir)
        want_stream = cfg["stream"] if payload.stream is None else bool(payload.stream)
        meta = {
            "heuristic_mode": bool(not ctx_info.get("is_submitted", True) and ctx_info.get("card_id")),
            "effective_mode": ctx_info.get("effective_mode"),
        }
        transport = getattr(active_runtime, "ai_transport", None)
        if want_stream:
            upstream_iter = open_chat_stream(
                active_runtime.data_dir,
                system_prompt=system_prompt,
                messages=chat_messages,
                transport=transport,
            )

            def _event_stream():
                yield f"data: {json.dumps({'meta': meta}, ensure_ascii=False)}\n\n".encode("utf-8")
                yield from upstream_iter

            return StreamingResponse(
                _event_stream(),
                media_type="text/event-stream",
                headers={"X-Accel-Buffering": "no"},
            )
        result = complete_chat(
            active_runtime.data_dir,
            system_prompt=system_prompt,
            messages=chat_messages,
            transport=transport,
        )
        return {**result, **meta}

    @app.get("/deployment.json")
    def deployment_config():
        return {
            "api_origin": "",
            "mode": "local-personal",
            "service_id": SERVER_SERVICE_ID,
            "subject_id": active_runtime.subject_id,
            "course_id": active_runtime.course_id,
        }

    @app.api_route("/api/{unknown:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def api_not_found(unknown: str):
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": f"未知接口路径：/api/{unknown}"},
        )

    def _serve_static_asset(request: Request, target: Path):
        media_type = _media_type_for(target)
        headers: dict[str, str] = {}
        if media_type:
            headers["Content-Type"] = media_type
        if target.suffix.lower() in {".html", ".js", ".css"}:
            headers["Cache-Control"] = "no-cache"
        if request.method == "HEAD":
            return Response(status_code=200, headers=headers or None)
        return FileResponse(target, media_type=media_type, headers=headers or None)

    @app.api_route("/", methods=["GET", "HEAD"])
    def web_root(request: Request):
        target = _resolve_static_asset(active_runtime.web_dir, "index.html")
        if target is None:
            return JSONResponse(
                status_code=200,
                content={
                    "service_id": SERVER_SERVICE_ID,
                    "mode": "local-personal",
                    "web_ready": False,
                    "message": "Frontend directory tools/japanese_grammar/web has not landed yet.",
                },
            )
        return _serve_static_asset(request, target)

    @app.api_route("/{asset_path:path}", methods=["GET", "HEAD"])
    def web_asset(asset_path: str, request: Request):
        target = _resolve_static_asset(active_runtime.web_dir, asset_path)
        if target is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "asset_not_found", "message": "静态资源不存在或无权访问。"},
            )
        return _serve_static_asset(request, target)

    return app


__all__ = [
    "BodyLimitMiddleware",
    "CONTENT_SECURITY_POLICY",
    "MAX_REQUEST_BODY_BYTES",
    "create_app",
]
