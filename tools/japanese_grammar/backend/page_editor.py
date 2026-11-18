"""Current-page editing for the local Japanese learning interface."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import json
import secrets
import threading
import time
from typing import Any, Callable, Literal

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from graspmemoedu.service import DomainError

from .ai import complete_chat
from .intro_pages import split_introduction_steps
from .page_edit_store import EditPage, PageEditStore, validate_fields


class EditorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OpenPage(EditorRequest):
    view_id: str = Field(min_length=1, max_length=128)
    sequence: int | None = Field(default=None, ge=1)
    kind: Literal["introduction", "chunk", "question", "explanation"]
    topic_id: str | None = Field(default=None, min_length=1, max_length=128)
    presentation_id: str | None = Field(default=None, min_length=1, max_length=128)
    step_index: int | None = Field(default=None, ge=0, le=1000)
    paper_id: str | None = Field(default=None, min_length=1, max_length=128)
    item_index: int | None = Field(default=None, ge=0, le=1000)


class PageToken(EditorRequest):
    token: str = Field(min_length=32, max_length=64)


class SuggestPage(PageToken):
    revision: int = Field(ge=0)
    instruction: str = Field(min_length=1, max_length=1500)


class SavePage(PageToken):
    revision: int = Field(ge=0)
    fields: dict[str, str] = Field(max_length=3)


@dataclass(frozen=True)
class EditorSession:
    selection: OpenPage
    page: EditPage
    context_id: str
    learner_id: str
    expires_at: float


def _not_editable() -> DomainError:
    return DomainError("page_not_editable", "该页已切换或当前不可编辑，请回到当前学习内容后重试。", 409)


def _stale() -> DomainError:
    return DomainError("page_edit_stale", "这页内容已更新，请重新打开编辑器后再保存。", 409)


@lru_cache(maxsize=128)
def _intro_parts(html: str, title: str) -> tuple[dict[str, str], ...]:
    return tuple(split_introduction_steps(html, title))


def _intro_pages(topic_id: str, intro: dict) -> list[EditPage]:
    parts = _intro_parts(intro.get("html") or intro.get("body_html") or "", intro.get("title") or "语法核心讲解")
    return [
        EditPage(topic_id=topic_id, kind="introduction", page_id=f"{intro['id']}:{index}",
                 fields={"title": part["title"], "html": part["html"]})
        for index, part in enumerate(parts)
    ]


def _chunk_page(topic_id: str, chunk: dict) -> EditPage:
    fields = {"title": chunk["title"], "html": chunk.get("content_html") or chunk["html"]}
    if chunk.get("mnemonic_html"):
        fields["mnemonic_html"] = chunk["mnemonic_html"]
    return EditPage(topic_id=topic_id, kind="chunk", page_id=chunk["id"], fields=fields)


def _card_page(topic_id: str, kind: str, card_id: str, presentation: str, html: str,
               presented_at: str | None = None) -> EditPage:
    return EditPage(topic_id=topic_id, kind=kind, page_id=card_id, fields={"html": html},
                    presentation_id=presentation, presented_at=presented_at)


def _paper_page(item: dict, kind: str, html: str) -> EditPage:
    return _card_page(item["topic_id"], kind, item["card_id"],
                      f"paper:{item['paper_id']}:{item['index']}", html, item.get("created_at"))


def _projection_fields(page: EditPage, store: PageEditStore, *, pin: bool = False) -> dict[str, str]:
    return store.view(page, pin=pin)["fields"]


def _original_explanation(learner: Any, current: dict) -> str:
    if current.get("content_version") not in (None, learner.course["version"]):
        return ""
    owner = getattr(learner, "atomic", learner)
    return (getattr(owner, "questions", {}).get(current["card_id"]) or {}).get("explanation_html", "")


def _topic_card_pages(topic_id: str, card: dict) -> dict[str, EditPage]:
    if not (card.get("card_id") and card.get("id") and isinstance(card.get("html"), str)):
        return {}
    presentation = f"topic:{card['id']}"
    pages = {"html": _card_page(topic_id, "question", card["card_id"], presentation,
                               card["html"], card.get("shown_at"))}
    if card.get("explanation_html"):
        pages["explanation_html"] = _card_page(topic_id, "explanation", card["card_id"], presentation,
                                               card["explanation_html"], card.get("shown_at"))
    return pages


def _project_history(store: PageEditStore, topic_id: str, state: dict) -> None:
    groups = {key: [(row, _topic_card_pages(topic_id, row) if isinstance(row, dict) else {})
                    for row in state[key]]
              for key in ("history", "atomic_history", "steps") if isinstance(state.get(key), list)}
    pages = [page for group in groups.values() for _, display in group for page in display.values()]
    if not pages:
        return
    revisions = iter(store.view_many(pages))
    for key, group in groups.items():
        state[key] = [
            {**row, **{field: next(revisions)["fields"]["html"] for field in display}} if display else row
            for row, display in group
        ]


class PageEditor:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.store = PageEditStore(runtime.data_dir, clock=runtime.clock)
        self._sessions: dict[str, EditorSession] = {}
        self._views: dict[tuple[str, str], str] = {}
        self._lock = threading.RLock()

    def project_topic(self, learner: Any, state: dict) -> None:
        topic_id = learner.course["id"]
        if state.get("dependency_blocked"):
            return
        intro = state.get("introduction") or {}
        if state.get("phase") == "introduction" and intro.get("id"):
            pages = [view["fields"] for view in self.store.view_many(_intro_pages(topic_id, intro))]
            state["introduction"] = {**intro, "pages": pages}
        chunk = state.get("chunk") or {}
        if state.get("phase") in ("chunk", "memory_chunk") and chunk.get("id"):
            fields = _projection_fields(_chunk_page(topic_id, chunk), self.store)
            state["chunk"] = {**chunk, "title": fields["title"], "editor_html": fields["html"]}
            if "mnemonic_html" in fields:
                state["chunk"]["editor_mnemonic_html"] = fields["mnemonic_html"]

        current = state.get("current")
        if current and current.get("card_id"):
            display = _topic_card_pages(topic_id, current)
            hidden_back = _original_explanation(learner, current)
            outputs = {field: _projection_fields(page, self.store, pin=True)["html"]
                       for field, page in display.items()}
            state["current"] = {**current, **outputs}
            if "explanation_html" not in display and hidden_back and current.get("id"):
                hidden_page = _card_page(topic_id, "explanation", current["card_id"], f"topic:{current['id']}",
                                         hidden_back, current.get("shown_at"))
                self.store.view(hidden_page, pin=True)
            if isinstance(state.get("feedback"), dict) and state["current"].get("explanation_html"):
                state["feedback"] = {**state["feedback"], "explanation_html": state["current"]["explanation_html"]}
        _project_history(self.store, topic_id, state)

    def project_paper_item(self, item: dict) -> dict[str, str]:
        live = item["phase"] in ("answer", "grading")
        face = _paper_page(item, "question", item["html"])
        display = {"html": _projection_fields(face, self.store, pin=live)["html"]}
        original_back = item.get("base_explanation_html") or item.get("explanation_html")
        if original_back:
            back = _paper_page(item, "explanation", original_back)
            html = _projection_fields(back, self.store, pin=live)["html"]
            if item.get("back_visible"):
                display["explanation_html"] = html
        return display

    def _forget(self, token: str) -> None:
        session = self._sessions.pop(token, None)
        if session is not None:
            self._views.pop((session.learner_id, session.selection.view_id), None)

    def _session(self, token: str, learner_id: str) -> EditorSession:
        session = self._sessions.get(token)
        if session is None or session.learner_id != learner_id:
            raise _not_editable()
        if session.expires_at <= time.monotonic():
            self._forget(token)
            raise _not_editable()
        return session

    def close(self, token: str, learner_id: str) -> None:
        with self._lock:
            self._session(token, learner_id)
            self._forget(token)

    def open(self, selection: OpenPage, page: EditPage, context_id: str, learner_id: str) -> dict:
        with self._lock:
            previous = self._views.get((learner_id, selection.view_id))
            if previous:
                opened = self._sessions[previous]
                if (opened.expires_at > time.monotonic()
                        and selection.sequence is not None and opened.selection.sequence is not None
                        and selection.sequence <= opened.selection.sequence):
                    raise _not_editable()
                self._forget(previous)
            expired = [key for key, item in self._sessions.items() if item.expires_at <= time.monotonic()]
            for token in expired:
                self._forget(token)
            if len(self._sessions) >= 128:
                self._forget(next(iter(self._sessions)))
            token = secrets.token_urlsafe(32)
            session = EditorSession(selection, page, context_id, learner_id, time.monotonic() + 1800)
            latest = self.store.view(replace(page, presentation_id=None))
            current = self.store.view(page, pin=True) if page.presentation_id else latest
            self._sessions[token] = session
            self._views[(learner_id, selection.view_id)] = token
            return {"token": token, "revision": latest["revision"], "fields": current["fields"],
                    "updated_elsewhere": current["revision"] != latest["revision"]}

    def selection(self, token: str, learner_id: str) -> OpenPage:
        with self._lock:
            return self._session(token, learner_id).selection

    def checked(self, token: str, revision: int, page: EditPage, context_id: str, learner_id: str) -> dict[str, str]:
        with self._lock:
            session = self._session(token, learner_id)
            if session.page != page or session.context_id != context_id:
                raise _not_editable()
            latest = self.store.view(replace(page, presentation_id=None))
            if revision != latest["revision"]:
                raise _stale()
            return self.store.view(page, pin=True)["fields"] if page.presentation_id else latest["fields"]

    def save(self, payload: SavePage, page: EditPage, context_id: str, learner_id: str) -> dict:
        with self._lock:
            self.checked(payload.token, payload.revision, page, context_id, learner_id)
            return self.store.save(page, payload.revision, payload.fields)

    def suggest(self, page: EditPage, fields: dict[str, str], instruction: str) -> dict[str, str]:
        instruction = instruction.strip()
        if not instruction:
            raise DomainError("empty_page_edit_instruction", "请输入需要修改的内容。", 422)
        context = {"kind": page.kind, "fields": fields, "instruction": instruction}
        result = complete_chat(
            self.runtime.data_dir,
            system_prompt=(
                "你是日语学习网站的单页内容编辑器。输入仅含这一页的可编辑字段及修改要求。"
                "只返回 JSON 对象，键与 fields 完全一致，每个值都是字符串。保持内容语言、日语注音、"
                "有意义的格式及所有 {{blank:id}} 原位、原序和数量，保留填空所在日语段落的标签与类名。"
                "保留题目要考查的语法和原答案含义。"
                "不要增加卡片、回答题目、添加脚本、表单、链接或其他外部资源。未修改的字段原样返回。"
            ),
            messages=[{"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
            transport=self.runtime.ai_transport,
            timeout_seconds=30.0,
        )
        raw = result["reply"].strip()
        if len(raw) > 30000:
            raise DomainError("invalid_page_suggestion", "AI 建议过长，请缩小修改范围后重试。", 502)
        if raw.startswith("```json\n") and raw.endswith("\n```"):
            raw = raw[8:-4]
        try:
            proposed = json.loads(raw, object_pairs_hook=_unique_fields)
        except (ValueError, RecursionError) as exc:
            raise DomainError("invalid_page_suggestion", "AI 没有返回可预览的页面内容，请重试。", 502) from exc
        return validate_fields(page, proposed)


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict:
    fields: dict[str, Any] = {}
    for name, value in pairs:
        if name in fields:
            raise ValueError("duplicate field")
        fields[name] = value
    return fields


def _resolve_topic_page(topic_id: str, state: dict, selection: OpenPage) -> tuple[EditPage, str]:
    if state.get("pause") or state.get("pending_submission_id"):
        raise _not_editable()
    phase = state.get("phase")
    if selection.kind == "introduction" and phase == "introduction":
        intro = state.get("introduction") or {}
        if not intro.get("id") or selection.presentation_id not in (None, intro["id"]):
            raise _not_editable()
        pages = _intro_pages(topic_id, intro)
        if selection.step_index is None or selection.step_index >= len(pages):
            raise _not_editable()
        return pages[selection.step_index], str(state.get("current_step_id") or state.get("active_step_id") or intro["id"])
    if selection.kind == "chunk" and phase in ("chunk", "memory_chunk"):
        chunk = state.get("chunk") or {}
        if not chunk.get("id") or selection.presentation_id not in (None, chunk["id"]):
            raise _not_editable()
        return _chunk_page(topic_id, chunk), str(state.get("active_step_id") or chunk["id"])
    if selection.kind in ("question", "explanation") and phase in ("answer", "feedback"):
        current = state.get("current") or {}
        if not current.get("card_id") or not current.get("id") or selection.presentation_id != current["id"]:
            raise _not_editable()
        field = "html" if selection.kind == "question" else "explanation_html"
        if not current.get(field):
            raise _not_editable()
        presentation = f"topic:{current['id']}"
        return _card_page(topic_id, selection.kind, current["card_id"], presentation,
                          current[field], current.get("shown_at")), presentation
    raise _not_editable()


def register_page_editor_routes(app: Any, editor: PageEditor, identity: Callable, resolve_access: Callable,
                                normalize_topic_state: Callable, with_editable_paper_page: Callable) -> None:
    def with_page(request: Request, selection: OpenPage, action: Callable):
        if selection.paper_id is not None:
            if (selection.item_index is None or selection.kind not in ("question", "explanation")
                    or selection.topic_id is not None or selection.presentation_id is not None
                    or selection.step_index is not None):
                raise _not_editable()

            def on_item(item: dict):
                field = "html" if selection.kind == "question" else "explanation_html"
                if not item.get(field):
                    raise _not_editable()
                page = _paper_page(item, selection.kind, item[field])
                return action(page, page.presentation_id)

            return with_editable_paper_page(request, selection.paper_id, selection.item_index, on_item)

        if (selection.topic_id is None or selection.item_index is not None
                or (selection.kind != "introduction" and selection.step_index is not None)):
            raise _not_editable()
        access, learner = identity(request, topic_id=selection.topic_id, feature="learn")
        editor.runtime.dependency_policy.require(access, selection.topic_id)
        with learner._transaction() as con:
            state = learner._public(learner._load(con))
            normalize_topic_state(state)
            page, context_id = _resolve_topic_page(selection.topic_id, state, selection)
            return action(page, context_id)

    @app.post("/api/page-edits/open")
    def open_page(payload: OpenPage, request: Request):
        learner_id = resolve_access(request)["learner_id"]
        return with_page(request, payload, lambda page, ctx: editor.open(payload, page, ctx, learner_id))

    @app.post("/api/page-edits/close")
    def close_page(payload: PageToken, request: Request):
        editor.close(payload.token, resolve_access(request)["learner_id"])
        return {"closed": True}

    @app.post("/api/page-edits/suggest")
    def suggest_page(payload: SuggestPage, request: Request):
        learner_id = resolve_access(request)["learner_id"]
        selection = editor.selection(payload.token, learner_id)

        def read_page(page: EditPage, ctx: str):
            return page, editor.checked(payload.token, payload.revision, page, ctx, learner_id)

        page, fields = with_page(request, selection, read_page)
        proposed = editor.suggest(page, fields, payload.instruction)
        with_page(request, selection, read_page)
        return {"fields": proposed}

    @app.put("/api/page-edits/current")
    def save_page(payload: SavePage, request: Request):
        learner_id = resolve_access(request)["learner_id"]
        selection = editor.selection(payload.token, learner_id)
        return with_page(request, selection, lambda page, ctx: editor.save(payload, page, ctx, learner_id))
