"""Local, versioned display edits kept outside the learning database."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import TypedDict

from graspmemoedu.service import DomainError

from .intro_pages import HtmlNode, parse_fragment


PAGE_EDIT_DB = "page-edits.sqlite3"
MAX_PAGE_EDIT_BYTES = 24_576

_HTML_FIELDS = frozenset(("html", "explanation_html", "mnemonic_html"))
_ALLOWED_TAGS = frozenset("""
    b blockquote br caption code div em h2 h3 h4 i li ol p pre rp rt ruby span strong
    table tbody td th thead tr u ul
""".split())
_ALLOWED_CLASSES = frozenset("""
    jp-bad jp-bad-ex jp-card jp-ex jp-expl jp-ja jp-note jp-prompt jp-romaji jp-table
    jp-term jp-tip jp-zh
""".split())
_NO_BLANK_TEXT = frozenset(("ruby", "rt", "rp", "code", "pre"))
_BLANK = re.compile(r"\{\{blank:([A-Za-z][A-Za-z0-9_-]{0,39})\}\}")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS revisions (
    topic_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    page_id TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    fields TEXT NOT NULL,
    saved_at TEXT,
    PRIMARY KEY (topic_id, kind, page_id, source_hash, revision)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS presentations (
    topic_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    page_id TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    presentation_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 0),
    PRIMARY KEY (topic_id, kind, page_id, source_hash, presentation_id)
) WITHOUT ROWID;
"""


def _json(fields: Mapping[str, str]) -> str:
    return json.dumps(dict(fields), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _utc_stamp(value: str | datetime) -> str:
    timestamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class EditPage:
    """An editable field allowlist resolved by the server from authored content."""

    topic_id: str
    kind: str
    page_id: str
    fields: Mapping[str, str]
    presentation_id: str | None = None
    presented_at: str | None = None

    @property
    def source_hash(self) -> str:
        return hashlib.sha256(_json(self.fields).encode("utf-8")).hexdigest()

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.topic_id, self.kind, self.page_id, self.source_hash


class PageEditView(TypedDict):
    revision: int
    fields: dict[str, str]


def _validate_node(node: HtmlNode) -> None:
    if node.tag not in _ALLOWED_TAGS:
        raise ValueError("Unsupported element")
    if node.attrs:
        if len(node.attrs) != 1 or node.attrs[0][0] != "class" or not node.classes <= _ALLOWED_CLASSES:
            raise ValueError("Unsupported attribute")


def _blank_signature(root: HtmlNode) -> list[tuple[str, bool]]:
    ordered = []

    def visit(node: HtmlNode, blocked: bool, in_sentence: bool) -> None:
        blocked = blocked or node.tag in _NO_BLANK_TEXT
        in_sentence = in_sentence or "jp-ja" in node.classes
        for child in node.children:
            if isinstance(child, HtmlNode):
                visit(child, blocked, in_sentence)
            else:
                found = _BLANK.findall(child)
                if blocked and found:
                    raise ValueError("Blank marker inside code or ruby")
                ordered.extend((blank_id, in_sentence) for blank_id in found)

    visit(root, False, False)
    if root.raw_text().count("{{blank:") != len(ordered):
        raise ValueError("Invalid blank marker")
    return ordered


def validate_fields(page: EditPage, fields: Mapping[str, str]) -> dict[str, str]:
    """Canonicalize only safe display markup and preserve the interaction tokens."""
    if not isinstance(fields, Mapping) or set(fields) != set(page.fields):
        raise DomainError("invalid_page_edit", "只能编辑当前页显示的字段。", 422)
    if any(not isinstance(value, str) or _CONTROL.search(value) for value in fields.values()):
        raise DomainError("invalid_page_edit", "编辑内容必须为有效文字。", 422)
    try:
        size = sum(len(value.encode("utf-8")) for value in fields.values())
    except UnicodeEncodeError as error:
        raise DomainError("invalid_page_edit", "编辑内容包含无效字符。", 422) from error
    if size > MAX_PAGE_EDIT_BYTES:
        raise DomainError("page_edit_too_large", "当前页的编辑内容太长。", 413)

    result = {}
    for name, raw in fields.items():
        value = raw.strip()
        if name == "title":
            if not value or len(value) > 200 or "{{blank:" in value or "\n" in value or "\r" in value:
                raise DomainError("invalid_page_edit_title", "标题须为一行，且最多 200 字。", 422)
            result[name] = value
            continue
        if name not in _HTML_FIELDS:
            raise DomainError("invalid_page_edit", "只能编辑当前页显示的字段。", 422)
        try:
            fragment = parse_fragment(value, _validate_node)
        except ValueError as error:
            raise DomainError("invalid_page_edit_html", "正文包含不支持的格式，请使用编辑器内的排版选项。", 422) from error
        try:
            current_blanks = _blank_signature(fragment)
            original_blanks = _blank_signature(parse_fragment(page.fields[name]))
            if current_blanks != original_blanks:
                raise ValueError("Blank markers changed")
        except ValueError as error:
            raise DomainError("invalid_page_edit_blanks", "请保持填空标记的数量、标识和顺序，并将标记留在原句正文中。", 422) from error
        if name == "html" and page.fields[name].strip() and not fragment.text():
            raise DomainError("invalid_page_edit", "正文不能为空。", 422)
        result[name] = fragment.html()

    if sum(len(value.encode("utf-8")) for value in result.values()) > MAX_PAGE_EDIT_BYTES:
        raise DomainError("page_edit_too_large", "当前页的编辑内容太长。", 413)
    return result


class PageEditStore:
    """Store display revisions and keep each exercise presentation stable."""

    def __init__(self, data_dir: Path, *, clock: Callable[[], datetime] = _utc_now):
        self.path = data_dir / PAGE_EDIT_DB
        self.clock = clock
        with closing(self._connect()) as con, con:
            con.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA)
            if "saved_at" not in {row[1] for row in con.execute("PRAGMA table_info(revisions)")}:
                con.execute("ALTER TABLE revisions ADD COLUMN saved_at TEXT")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    @staticmethod
    def _latest(
        con: sqlite3.Connection, key: tuple[str, ...], presented_at: str | None = None,
    ) -> tuple[int, str | None]:
        cap = ""
        params = key
        if presented_at is not None:
            try:
                params = (*key, _utc_stamp(presented_at))
            except ValueError:
                return 0, None
            cap = " AND (saved_at IS NULL OR saved_at<=?)"
        row = con.execute(
            "SELECT revision, fields FROM revisions WHERE topic_id=? AND kind=? AND page_id=? AND source_hash=?"
            + cap + " ORDER BY revision DESC LIMIT 1",
            params,
        ).fetchone()
        return row if row is not None else (0, None)

    @staticmethod
    def _pinned(
        con: sqlite3.Connection, key: tuple[str, ...], presentation_id: str,
    ) -> tuple[int, str | None] | None:
        return con.execute(
            "SELECT p.revision, r.fields FROM presentations p LEFT JOIN revisions r "
            "USING (topic_id,kind,page_id,source_hash,revision) "
            "WHERE p.topic_id=? AND p.kind=? AND p.page_id=? AND p.source_hash=? AND p.presentation_id=?",
            (*key, presentation_id),
        ).fetchone()

    @staticmethod
    def _set_pin(
        con: sqlite3.Connection, key: tuple[str, ...], presentation_id: str, revision: int,
    ) -> None:
        con.execute(
            "INSERT INTO presentations VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(topic_id,kind,page_id,source_hash,presentation_id) DO UPDATE SET revision=excluded.revision",
            (*key, presentation_id, revision),
        )

    @staticmethod
    def _view(page: EditPage, revision: int, fields: str | None) -> PageEditView:
        return {"revision": revision, "fields": json.loads(fields) if fields is not None else dict(page.fields)}

    def _read_view(self, con: sqlite3.Connection, page: EditPage, pin: bool) -> PageEditView:
        key = page.key
        if page.presentation_id is None:
            return self._view(page, *self._latest(con, key))

        stored = self._pinned(con, key, page.presentation_id)
        if stored is not None:
            return self._view(page, *stored)
        if not pin:
            return self._view(page, 0, None)

        if not con.in_transaction:
            # Another request can pin or save this presentation between the
            # first read and BEGIN. Batch callers already hold the write lock.
            con.execute("BEGIN IMMEDIATE")
            stored = self._pinned(con, key, page.presentation_id)
            if stored is not None:
                return self._view(page, *stored)
        revision, fields = self._latest(con, key, page.presented_at)
        self._set_pin(con, key, page.presentation_id, revision)
        return self._view(page, revision, fields)

    def view(self, page: EditPage, *, pin: bool = False) -> PageEditView:
        with closing(self._connect()) as con, con:
            return self._read_view(con, page, pin)

    def view_many(self, pages: Sequence[EditPage], *, pin: bool = False) -> list[PageEditView]:
        if not pages:
            return []
        with closing(self._connect()) as con, con:
            con.execute("BEGIN IMMEDIATE" if pin else "BEGIN")
            return [self._read_view(con, page, pin) for page in pages]

    def save(self, page: EditPage, expected_revision: int, fields: Mapping[str, str]) -> PageEditView:
        clean = validate_fields(page, fields)
        key = page.key
        with closing(self._connect()) as con, con:
            con.execute("BEGIN IMMEDIATE")
            revision, current = self._latest(con, key)
            if revision != expected_revision:
                raise DomainError("page_edit_stale", "本页已有更新，请重新打开编辑器后再保存。", 409)
            if clean != self._view(page, revision, current)["fields"]:
                revision += 1
                con.execute(
                    "INSERT INTO revisions(topic_id,kind,page_id,source_hash,revision,fields,saved_at) VALUES (?,?,?,?,?,?,?)",
                    (*key, revision, _json(clean), _utc_stamp(self.clock())),
                )
            if page.presentation_id is not None:
                self._set_pin(con, key, page.presentation_id, revision)
            return {"revision": revision, "fields": clean}
