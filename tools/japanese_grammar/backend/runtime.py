"""Local-personal runtime, manifest synchronization, and single-learner SQLite store."""

from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import html as html_lib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import threading
import uuid
from typing import Any, Callable

from graspmemoedu.access import AccessStore, FEATURES
from graspmemoedu.atomic_content import is_atomic
from graspmemoedu.catalog import Catalog
from graspmemoedu.config import Settings
from graspmemoedu.content_bundle import content_root
from graspmemoedu.content_references import ContentReferenceIndex
from graspmemoedu.course_graph import GraphStore, validate_graph
from graspmemoedu.dashboard import DashboardStore
from graspmemoedu.dependencies import DependencyPolicy
from graspmemoedu.fsrs_engine import FSRSEngine
from graspmemoedu.guide import GuideReader
from graspmemoedu.public_limits import PublicLimits
from graspmemoedu.review import ReviewBackend
from graspmemoedu.review_cards import point_id
from graspmemoedu.review_papers import PaperService
from graspmemoedu.service import DomainError, create_learning_service
from graspmemoedu.source_content import trainable
from graspmemoedu.subjects import Subjects
from graspmemoedu.topic_runtime import is_introduction
from graspmemoedu.topic_structure import has_atomic, sectioned_training
from graspmemoedu.training import TrainingService
from graspmemoedu.training_content import TrainingCatalog

from .judge import JapaneseGrammarJudge

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME_DIR = REPO_ROOT / ".runtime" / "japanese-grammar"
DEFAULT_PACKAGES_DIR = REPO_ROOT / "tools" / "japanese_grammar" / "packages"
DEFAULT_WEB_DIR = REPO_ROOT / "tools" / "japanese_grammar" / "web"

LOCAL_LEARNER_ID = "local"
LOCAL_DISPLAY_NAME = "本地学习者"
LOCAL_IDENTITY_TOKEN = "local-personal-japanese-grammar"
DEFAULT_SUBJECT_ID = "japanese"
DEFAULT_COURSE_ID = "japanese-grammar-core"
DEFAULT_TOPIC_ID = "jp01-copula-particles"
DEFAULT_COURSE_TITLE = "日语核心语法精练"
DEFAULT_COURSE_DESCRIPTION = "面向直觉化日语语法掌握的本地个人原子训练与组卷复习系统。"
SERVER_SERVICE_ID = "graspmemoedu-japanese-grammar-local-v1"
SERVER_METADATA_FILE = "server.json"
LOCK_FILE_NAME = ".japanese-grammar.lock"

DATA_DIR_ENV = "GRASPMEMOEDU_JP_DATA_DIR"
PACKAGES_DIR_ENV = "GRASPMEMOEDU_JP_PACKAGES_DIR"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18782
FORBIDDEN_PORTS = frozenset({8765, 8767, 18768, 18769, 18780, 18781, 18789})
FORBIDDEN_PORT_REASONS = {
    8765: "AnkiConnect",
    8767: "GraspMemoEdu local development server",
    18768: "Tencent Cloud production backend tunnel/service",
    18769: "Hyperskill bridge",
    18780: "graspmemoedu_local personal server",
    18781: "topological_quantum local server",
    18789: "category_theory local tool",
}
FORBIDDEN_RUNTIME_DIRS = (
    REPO_ROOT / ".runtime" / "category-theory",
    REPO_ROOT / ".runtime" / "topological-quantum",
)

_RESET_TARGETS = (
    "learning.sqlite3",
    "learning.sqlite3-wal",
    "learning.sqlite3-shm",
    "judge-daily-quota.sqlite3",
    "judge-daily-quota.sqlite3-wal",
    "judge-daily-quota.sqlite3-shm",
    "server.json",
)
_LOG_RESET_TARGETS = (
    "logs/events.jsonl",
    "logs/.events.lock",
)
_WINDOWS_EPOCH_TICKS = 116444736000000000


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _norm_path(path: str | Path) -> Path:
    return Path(os.path.abspath(str(Path(path))))


def validate_loopback_host(host: str | None) -> str:
    """Validate host is strictly loopback and return canonical '127.0.0.1'."""
    raw = (host or DEFAULT_HOST).strip().lower()
    if raw not in {"127.0.0.1", "localhost"}:
        raise ValueError(
            f"Refusing non-loopback host {host!r}. Local-Personal server only allows 127.0.0.1/localhost."
        )
    return "127.0.0.1"


def validate_port(port: int) -> int:
    """Validate port range and ensure zero collision with reserved service ports."""
    value = int(port)
    if not 1 <= value <= 65535:
        raise ValueError(f"Port must be between 1 and 65535, got {port!r}.")
    if value in FORBIDDEN_PORTS:
        reason = FORBIDDEN_PORT_REASONS.get(value, "reserved port")
        raise ValueError(f"Port {value} is reserved for {reason}. Use another port (default {DEFAULT_PORT}).")
    return value


def validate_data_dir(path: str | Path) -> Path:
    """Resolve runtime directory and forbid symlinks or sibling app runtime folders."""
    raw_path = Path(path)
    if raw_path.exists() and raw_path.is_symlink():
        raise ValueError(f"Runtime directory must not be a symlink: {raw_path}")
    resolved = _norm_path(raw_path)
    for forbidden in FORBIDDEN_RUNTIME_DIRS:
        forbidden_resolved = _norm_path(forbidden)
        if os.path.normcase(str(resolved)) == os.path.normcase(str(forbidden_resolved)):
            raise ValueError(f"Runtime directory cannot reuse sibling tool folder: {forbidden_resolved}")
    return resolved


def resolve_data_dir(explicit: str | Path | None = None) -> Path:
    """Determine runtime data directory from CLI arg, env var, or default."""
    candidate = explicit if explicit is not None and str(explicit).strip() else os.environ.get(DATA_DIR_ENV)
    return validate_data_dir(candidate or DEFAULT_RUNTIME_DIR)


def resolve_packages_dir(explicit: str | Path | None = None) -> Path:
    """Determine packages source directory from CLI arg, env var, or default."""
    candidate = explicit if explicit is not None and str(explicit).strip() else os.environ.get(PACKAGES_DIR_ENV)
    path = Path(candidate or DEFAULT_PACKAGES_DIR)
    if path.exists() and path.is_symlink():
        raise ValueError(f"Packages directory must not be a symlink: {path}")
    return _norm_path(path)


def resolve_web_dir(explicit: str | Path | None = None) -> Path:
    """Determine frontend directory path."""
    path = Path(explicit) if explicit is not None and str(explicit).strip() else DEFAULT_WEB_DIR
    if path.exists() and path.is_symlink():
        raise ValueError(f"Web directory must not be a symlink: {path}")
    return _norm_path(path)


def process_started_at(pid: int | None = None) -> str:
    """Return kernel-exact process start timestamp in UTC ISO-8601 format."""
    target_pid = os.getpid() if pid is None else int(pid)
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        process_query_limited_info = 0x1000
        handle = None
        close_after = False
        if target_pid == os.getpid():
            handle = kernel32.GetCurrentProcess()
        else:
            handle = kernel32.OpenProcess(process_query_limited_info, False, target_pid)
            close_after = True
        try:
            if not handle:
                raise OSError(ctypes.get_last_error(), "OpenProcess failed")
            creation = wintypes.FILETIME()
            exit_t = wintypes.FILETIME()
            kernel_t = wintypes.FILETIME()
            user_t = wintypes.FILETIME()
            ok = kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_t),
                ctypes.byref(kernel_t),
                ctypes.byref(user_t),
            )
            if not ok:
                raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
            ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            unix_micros = (ticks - _WINDOWS_EPOCH_TICKS) / 10.0
            return datetime.fromtimestamp(unix_micros / 1_000_000.0, tz=timezone.utc).isoformat()
        finally:
            if close_after and handle:
                kernel32.CloseHandle(handle)
    return utc_now().isoformat()


@contextmanager
def data_lock(data_dir: Path):
    """Acquire an exclusive OS advisory lock per runtime directory without sleeping."""
    target_dir = validate_data_dir(data_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    lock_path = target_dir / LOCK_FILE_NAME
    if lock_path.is_symlink():
        raise ValueError(f"Lock file must not be a symlink: {lock_path}")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt

            if os.path.getsize(lock_path) == 0:
                os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(
                    f"Another japanese-grammar server instance already holds {lock_path}."
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(
                    f"Another japanese-grammar server instance already holds {lock_path}."
                ) from exc
        yield lock_path
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _atomic_write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_server_metadata(
    data_dir: Path,
    *,
    port: int,
    instance_id: str,
    host: str = DEFAULT_HOST,
    started_at: str | None = None,
) -> Path:
    """Atomically write server.json identifying this running loopback instance."""
    meta_path = data_dir / SERVER_METADATA_FILE
    payload = {
        "service": SERVER_SERVICE_ID,
        "service_id": SERVER_SERVICE_ID,
        "mode": "local-personal",
        "host": host,
        "port": int(port),
        "pid": os.getpid(),
        "instance_id": instance_id,
        "process_started_at": started_at or process_started_at(),
    }
    _atomic_write_json(meta_path, payload)
    return meta_path


def remove_server_metadata(data_dir: Path, *, instance_id: str | None = None) -> None:
    """Remove server.json only when it belongs to this instance (or unconditionally if unspecified)."""
    meta_path = data_dir / SERVER_METADATA_FILE
    if not meta_path.exists() or meta_path.is_symlink():
        return
    if instance_id is not None:
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}
        if data.get("instance_id") != instance_id:
            return
    try:
        meta_path.unlink()
    except OSError:
        pass


def reset_runtime_state(data_dir: Path) -> list[str]:
    """Explicitly clear SQLite progress, daily quota, event logs, and server marker."""
    resolved = validate_data_dir(data_dir)
    if not resolved.exists():
        return []
    removed: list[str] = []
    for rel in (*_RESET_TARGETS, *_LOG_RESET_TARGETS):
        target = resolved / rel
        if target.exists() and not target.is_symlink():
            target.unlink()
            removed.append(rel)
    return removed


class LocalGuideReader(GuideReader):
    """GuideReader subclass degrading cleanly offline when Node/MathJax is absent."""

    def _compile(self, text: str) -> dict[str, Any]:
        try:
            return super()._compile(text)
        except Exception:
            paragraphs = [
                f"<p>{html_lib.escape(line.strip())}</p>"
                for line in str(text or "").splitlines()
                if line.strip()
            ]
            return {
                "html": "\n".join(paragraphs),
                "resources": [],
                "math_css": "",
            }


class ClockAwareDependencyPolicy(DependencyPolicy):
    """DependencyPolicy defaulting current_time checks to the runtime clock."""

    def __init__(
        self,
        catalog,
        access_store,
        *,
        subjects=None,
        training=None,
        clock=utc_now,
    ) -> None:
        super().__init__(
            catalog,
            access_store,
            subjects=subjects,
            training=training,
            clock=clock,
        )
        self._clock = clock

    def _now_iso(self) -> str:
        return self._clock().isoformat()

    def missing_count(
        self,
        con,
        access,
        topic_id,
        dependencies=None,
        current_time=None,
    ):
        return super().missing_count(
            con,
            access,
            topic_id,
            dependencies=dependencies,
            current_time=current_time or self._now_iso(),
        )

    def group_point_status(self, con, access, node_id, current_time=None):
        return super().group_point_status(
            con,
            access,
            node_id,
            current_time=current_time or self._now_iso(),
        )


def _copy_non_symlink_tree(src_dir: Path, dst_dir: Path) -> None:
    """Sync package directory files (topic.json + assets) safely without touching SQLite."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    expected_entries = set()
    for root, dirs, files in os.walk(src_dir, followlinks=False):
        root_path = Path(root)
        rel_root = root_path.relative_to(src_dir)
        clean_dirs = []
        for dirname in dirs:
            sub = root_path / dirname
            if sub.is_symlink():
                raise ValueError(f"Symlinks are forbidden inside topic packages: {sub}")
            clean_dirs.append(dirname)
            (dst_dir / rel_root / dirname).mkdir(parents=True, exist_ok=True)
        dirs[:] = clean_dirs
        for filename in files:
            src_file = root_path / filename
            if src_file.is_symlink():
                raise ValueError(f"Symlinks are forbidden inside topic packages: {src_file}")
            rel_file = rel_root / filename
            expected_entries.add(rel_file.as_posix())
            target_file = dst_dir / rel_file
            data = src_file.read_bytes()
            if not target_file.exists() or target_file.read_bytes() != data:
                tmp = target_file.with_name(f".{target_file.name}.{uuid.uuid4().hex}.tmp")
                try:
                    tmp.write_bytes(data)
                    os.replace(tmp, target_file)
                finally:
                    if tmp.exists():
                        try:
                            tmp.unlink()
                        except OSError:
                            pass
    for existing in sorted(dst_dir.rglob("*"), reverse=True):
        if existing.is_file() and not existing.is_symlink():
            rel_pos = existing.relative_to(dst_dir).as_posix()
            if rel_pos not in expected_entries:
                existing.unlink()
        elif existing.is_dir() and not any(existing.iterdir()):
            existing.rmdir()


def _topic_prereqs(topic: dict[str, Any], discovered_ids: set[str], topic_id: str) -> list[str]:
    raw = topic.get("prerequisites") or []
    result: list[str] = []
    for item in raw:
        if isinstance(item, str) and item in discovered_ids and item != topic_id and item not in result:
            result.append(item)
    return result


def _build_graph_payload(
    *,
    packages_dir: Path,
    topics_by_id: dict[str, dict[str, Any]],
    subject_id: str,
    course_id: str,
    course_title: str,
) -> dict[str, Any]:
    discovered_ids = set(topics_by_id)
    graph_src = packages_dir / "course_graph.json"
    if graph_src.is_symlink():
        raise ValueError(f"course_graph.json must not be a symlink: {graph_src}")

    raw_graph: dict[str, Any] = {}
    if graph_src.is_file():
        loaded = json.loads(graph_src.read_text(encoding="utf-8-sig"))
        if isinstance(loaded, dict):
            raw_graph = loaded

    schema_version = raw_graph.get("schema_version")
    if schema_version not in (1, 2, 3):
        schema_version = 2

    nodes_by_id: dict[str, dict[str, Any]] = {}
    ordered_nodes: list[dict[str, Any]] = []
    for raw_node in raw_graph.get("nodes") or []:
        if not isinstance(raw_node, dict):
            continue
        tid = raw_node.get("topic_id")
        if not isinstance(tid, str) or tid not in discovered_ids or tid in nodes_by_id:
            continue
        node: dict[str, Any] = {
            "topic_id": tid,
            "title": str(raw_node.get("title") or topics_by_id[tid].get("title") or tid),
        }
        if schema_version >= 2:
            node["member"] = True
        if raw_node.get("source") is not None:
            node["source"] = raw_node["source"]
        nodes_by_id[tid] = node
        ordered_nodes.append(node)

    for tid, topic in topics_by_id.items():
        if tid in nodes_by_id:
            continue
        node = {
            "topic_id": tid,
            "title": str(topic.get("title") or tid),
        }
        if schema_version >= 2:
            node["member"] = True
        nodes_by_id[tid] = node
        ordered_nodes.append(node)

    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    for raw_edge in raw_graph.get("edges") or []:
        if not isinstance(raw_edge, dict):
            continue
        src = raw_edge.get("from")
        dst = raw_edge.get("to")
        if (
            isinstance(src, str)
            and isinstance(dst, str)
            and src in discovered_ids
            and dst in discovered_ids
            and src != dst
            and (src, dst) not in seen_edges
        ):
            edge: dict[str, Any] = {
                "from": src,
                "to": dst,
                "type": "prerequisite",
            }
            if raw_edge.get("reason"):
                edge["reason"] = str(raw_edge["reason"])
            if raw_edge.get("source") is not None:
                edge["source"] = raw_edge["source"]
            edges.append(edge)
            seen_edges.add((src, dst))

    for tid, topic in topics_by_id.items():
        for prereq in _topic_prereqs(topic, discovered_ids, tid):
            if (prereq, tid) not in seen_edges:
                edges.append({"from": prereq, "to": tid, "type": "prerequisite"})
                seen_edges.add((prereq, tid))

    candidate = {
        "schema_version": schema_version,
        "subject_id": subject_id,
        "course_id": course_id,
        "title": str(raw_graph.get("title") or course_title),
        "nodes": ordered_nodes,
        "edges": edges,
    }
    return validate_graph(candidate)


def ensure_runtime_manifests(
    packages_dir: Path,
    data_dir: Path,
    *,
    subject_id: str = DEFAULT_SUBJECT_ID,
    course_id: str = DEFAULT_COURSE_ID,
) -> dict[str, Any]:
    """Synchronize packages/<topic_id>/topic.json and course_graph.json into data_dir.

    Strictly preserves SQLite databases, quotas, and event logs in data_dir.
    """
    src_root = resolve_packages_dir(packages_dir)
    dst_root = validate_data_dir(data_dir)
    if not src_root.is_dir():
        raise FileNotFoundError(f"Packages directory does not exist: {src_root}")

    topics_by_id: dict[str, dict[str, Any]] = {}
    package_dirs: dict[str, Path] = {}
    for entry in sorted(src_root.iterdir(), key=lambda p: p.name):
        if entry.name.startswith(".") or entry.name == "training_banks":
            continue
        if entry.is_symlink():
            raise ValueError(f"Symlinks are forbidden inside packages directory: {entry}")
        if not entry.is_dir():
            continue
        topic_file = entry / "topic.json"
        if not topic_file.is_file() or topic_file.is_symlink():
            continue
        topic = json.loads(topic_file.read_text(encoding="utf-8-sig"))
        topic_id = str(topic.get("id") or entry.name)
        if topic_id != entry.name:
            raise ValueError(
                f"Package folder {entry.name!r} does not match topic.json id {topic_id!r}."
            )
        if topic_id in topics_by_id:
            raise ValueError(f"Duplicate topic id detected in packages directory: {topic_id}")
        topics_by_id[topic_id] = topic
        package_dirs[topic_id] = entry

    if not topics_by_id:
        raise FileNotFoundError(f"No valid <topic_id>/topic.json packages found in {src_root}")

    dst_root.mkdir(parents=True, exist_ok=True)
    topics_dst = dst_root / "topics"
    if topics_dst.is_symlink():
        raise ValueError(f"Runtime topics directory must not be a symlink: {topics_dst}")
    topics_dst.mkdir(parents=True, exist_ok=True)

    for existing_dir in list(topics_dst.iterdir()):
        if existing_dir.is_dir() and existing_dir.name not in topics_by_id and not existing_dir.is_symlink():
            shutil.rmtree(existing_dir)

    for topic_id, pkg_dir in package_dirs.items():
        _copy_non_symlink_tree(pkg_dir, topics_dst / topic_id)

    # Optional package-bundled training banks are synced if provided without disturbing SQLite.
    banks_src = src_root / "training_banks"
    if banks_src.is_dir() and not banks_src.is_symlink():
        _copy_non_symlink_tree(banks_src, dst_root / "training_banks")

    course_title = DEFAULT_COURSE_TITLE
    course_description = DEFAULT_COURSE_DESCRIPTION
    pkg_catalog_file = src_root / "catalog.json"
    raw_catalog: dict[str, Any] = {}
    if pkg_catalog_file.is_file() and not pkg_catalog_file.is_symlink():
        loaded_cat = json.loads(pkg_catalog_file.read_text(encoding="utf-8-sig"))
        if isinstance(loaded_cat, dict):
            raw_catalog = loaded_cat

    source_course: dict[str, Any] = {}
    for candidate_course in raw_catalog.get("courses") or []:
        if isinstance(candidate_course, dict) and candidate_course.get("id") == course_id:
            source_course = candidate_course
            break
    if source_course:
        course_title = str(source_course.get("title") or course_title)
        course_description = str(source_course.get("description") or course_description)

    graph_payload = _build_graph_payload(
        packages_dir=src_root,
        topics_by_id=topics_by_id,
        subject_id=subject_id,
        course_id=course_id,
        course_title=course_title,
    )
    _atomic_write_json(dst_root / "graphs" / f"{course_id}.json", graph_payload)

    edge_prereqs: dict[str, list[str]] = {tid: [] for tid in topics_by_id}
    for edge in graph_payload["edges"]:
        target = edge["to"]
        source = edge["from"]
        if source not in edge_prereqs[target]:
            edge_prereqs[target].append(source)

    discovered_ids = list(topics_by_id.keys())
    units: list[dict[str, Any]] = []
    assigned: set[str] = set()
    for raw_unit in source_course.get("units") or []:
        if not isinstance(raw_unit, dict):
            continue
        unit_topics = [
            tid for tid in (raw_unit.get("topic_ids") or [])
            if isinstance(tid, str) and tid in topics_by_id and tid not in assigned
        ]
        if unit_topics:
            assigned.update(unit_topics)
            units.append(
                {
                    "id": str(raw_unit.get("id") or f"unit-{len(units) + 1}"),
                    "title": str(raw_unit.get("title") or f"单元 {len(units) + 1}"),
                    "topic_ids": unit_topics,
                }
            )

    remaining = [tid for tid in discovered_ids if tid not in assigned]
    if remaining:
        grouped: dict[tuple[str, str], list[str]] = {}
        for tid in remaining:
            topic = topics_by_id[tid]
            u_id = str(topic.get("unit_id") or "core-grammar")
            u_title = str(topic.get("unit_title") or "核心语法")
            grouped.setdefault((u_id, u_title), []).append(tid)
        for (u_id, u_title), tids in grouped.items():
            if any(u["id"] == u_id for u in units):
                u_id = f"{u_id}-{len(units) + 1}"
            units.append({"id": u_id, "title": u_title, "topic_ids": tids})

    ordered_ids = [tid for unit in units for tid in unit["topic_ids"]]
    catalog_topics = [
        {
            "id": tid,
            "path": f"topics/{tid}/topic.json",
            "prerequisites": edge_prereqs.get(tid, []),
        }
        for tid in ordered_ids
    ]
    catalog_payload = {
        "courses": [
            {
                "id": course_id,
                "title": course_title,
                "description": course_description,
                "units": units,
                "topics": catalog_topics,
            }
        ]
    }
    _atomic_write_json(dst_root / "catalog.json", catalog_payload)

    subject_entry: dict[str, Any] = {
        "id": subject_id,
        "course_ids": [course_id],
    }
    for rel_guide in ("guide.md", f"{subject_id}/guide.md"):
        guide_src = src_root / rel_guide
        if guide_src.is_file() and not guide_src.is_symlink():
            guide_dst = dst_root / rel_guide
            guide_dst.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(guide_dst, guide_src.read_text(encoding="utf-8-sig"))
            subject_entry["guide_path"] = rel_guide
            break
    _atomic_write_json(dst_root / "subjects.json", {"subjects": [subject_entry]})

    return {
        "topic_ids": ordered_ids,
        "course_id": course_id,
        "subject_id": subject_id,
        "graph": graph_payload,
    }


def _load_existing_topics(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Snapshot installed topic manifests before ensure_runtime_manifests overwrites them."""
    topics_dir = data_dir / "topics"
    result: dict[str, dict[str, Any]] = {}
    if not topics_dir.is_dir() or topics_dir.is_symlink():
        return result
    for topic_dir in topics_dir.iterdir():
        if not topic_dir.is_dir() or topic_dir.is_symlink():
            continue
        topic_file = topic_dir / "topic.json"
        if not topic_file.is_file() or topic_file.is_symlink():
            continue
        try:
            payload = json.loads(topic_file.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("id"), str):
            result[payload["id"]] = payload
    return result


def _topic_point_ids(topic: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for p in topic.get("points") or []:
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            ids.add(p["id"])
    for chunk in topic.get("memory_chunks") or []:
        if isinstance(chunk, dict):
            for p in chunk.get("points") or []:
                if isinstance(p, dict) and isinstance(p.get("id"), str):
                    ids.add(p["id"])
    return ids


def _topic_intro_ids(topic: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    top_intro = topic.get("introduction")
    if isinstance(top_intro, dict) and isinstance(top_intro.get("id"), str):
        ids.add(top_intro["id"])
    for item in topic.get("introductions") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.add(item["id"])
    for sec in topic.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        if isinstance(sec.get("id"), str):
            ids.add(sec["id"])
        sec_intro = sec.get("introduction")
        if isinstance(sec_intro, dict) and isinstance(sec_intro.get("id"), str):
            ids.add(sec_intro["id"])
    return ids


def _card_snapshot(card: dict[str, Any], version: str) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "title": card.get("title"),
        "point_ids": list(card.get("point_ids") or []),
        "question": card.get("question"),
        "html": card.get("html"),
        "reference_answer": card.get("reference_answer"),
        "explanation_html": card.get("explanation_html"),
        "interaction": card.get("interaction"),
        "version": version,
    }


def reconcile_compatible_topic_revisions(
    data_dir: Path,
    *,
    catalog: Catalog,
    previous_topics: dict[str, dict[str, Any]] | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Safely migrate compatible topic revisions in SQLite after backing up first.

    Preserves mastered points, FSRS schedules, attempts, sections_finished,
    read_introductions, history (attaching prior card snapshots), and review_points.
    """
    db_path = Path(data_dir) / "learning.sqlite3"
    if not db_path.is_file() or db_path.is_symlink():
        return {"migrated_topics": [], "backup_path": None}

    prev_map = previous_topics or {}
    stamp = now_iso or utc_now().isoformat()
    safe_stamp = re.sub(r"[^0-9A-Za-z_-]", "", stamp.replace(":", "").replace("-", ""))[:18] or utc_now().strftime("%Y%m%dT%H%M%SZ")

    con = sqlite3.connect(str(db_path), timeout=30.0)
    con.row_factory = sqlite3.Row
    with closing(con):
        existing_tables = {
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "topics" not in existing_tables:
            return {"migrated_topics": [], "backup_path": None}

        migrations: list[tuple[str, str, str, str, dict[str, Any]]] = []
        for row in con.execute("SELECT learner, topic, version, body FROM topics").fetchall():
            tid = str(row["topic"])
            if tid not in catalog.topics:
                continue
            new_topic = catalog.topic(tid)
            if row["version"] != new_topic["version"]:
                migrations.append((str(row["learner"]), tid, str(row["version"]), str(row["body"]), new_topic))

        if not migrations:
            return {"migrated_topics": [], "backup_path": None}

        # Pre-flight compatibility & in-flight safety checks before backing up or mutating.
        for learner, tid, old_version, raw_body, new_topic in migrations:
            try:
                body = json.loads(raw_body)
            except ValueError as exc:
                raise DomainError("incompatible_topic_revision", f"Topic {tid} 学习状态 JSON 损坏，已中止迁移。", 409) from exc
            atomic = body.get("atomic") if isinstance(body.get("atomic"), dict) else {}
            new_points = _topic_point_ids(new_topic)
            new_intros = _topic_intro_ids(new_topic)
            new_sections = {s["id"] for s in (new_topic.get("sections") or []) if isinstance(s, dict) and isinstance(s.get("id"), str)} | new_intros

            old_points = atomic.get("points") or {}
            if isinstance(old_points, dict):
                missing_pts = sorted(set(old_points.keys()) - new_points)
                if missing_pts:
                    raise DomainError(
                        "incompatible_topic_revision",
                        f"Topic {tid} 缺少已学习的知识点 {missing_pts}，无法无损迁移。",
                        409,
                    )

            finished = body.get("sections_finished") or []
            if isinstance(finished, list):
                missing_secs = sorted({str(item) for item in finished} - new_sections)
                if missing_secs:
                    raise DomainError(
                        "incompatible_topic_revision",
                        f"Topic {tid} 缺少已完成小节 {missing_secs}，无法无损迁移。",
                        409,
                    )

            read_intros = body.get("read_introductions") or []
            read_intro_keys = list(read_intros.keys()) if isinstance(read_intros, dict) else list(read_intros) if isinstance(read_intros, list) else []
            missing_intros = sorted({str(item) for item in read_intro_keys} - new_intros)
            if missing_intros:
                raise DomainError(
                    "incompatible_topic_revision",
                    f"Topic {tid} 缺少已阅读指导 {missing_intros}，无法无损迁移。",
                    409,
                )

            if body.get("pending_submission_id") or atomic.get("pending_submission_id"):
                raise DomainError(
                    "incompatible_topic_revision",
                    f"Topic {tid} 存在未完成判题提交，请等待判题完成后重启迁移。",
                    409,
                )
            if "submissions" in existing_tables:
                pending_row = con.execute(
                    "SELECT COUNT(*) FROM submissions WHERE learner=? AND topic=? AND status='pending'",
                    (learner, tid),
                ).fetchone()
                if pending_row and int(pending_row[0]) > 0:
                    raise DomainError(
                        "incompatible_topic_revision",
                        f"Topic {tid} 存在排队中的判题任务，已保护现场未迁移。",
                        409,
                    )

            if "review_points" in existing_tables:
                rp_check = con.execute(
                    "SELECT id, source_point FROM review_points WHERE kind='atomic' AND container=? AND version=?",
                    (tid, old_version),
                ).fetchall()
                missing_rp = sorted({str(r["source_point"]) for r in rp_check} - new_points)
                if missing_rp:
                    raise DomainError(
                        "incompatible_topic_revision",
                        f"Topic {tid} 的复习点 {missing_rp} 在新版本中不存在，无法无损迁移。",
                        409,
                    )
                old_rp_ids = {str(r["id"]) for r in rp_check}
                if old_rp_ids and "review_reservations" in existing_tables:
                    res = con.execute(
                        """SELECT r.point FROM review_reservations r
                        JOIN review_points p ON p.id = r.point
                        WHERE r.learner=? AND p.kind='atomic' AND p.container=? AND p.version=?""",
                        (learner, tid, old_version),
                    ).fetchone()
                    if res is not None:
                        raise DomainError(
                            "incompatible_topic_revision",
                            f"Topic {tid} 有进行中的组卷复习预约，请完成该试卷后再更新版本。",
                            409,
                        )
                if old_rp_ids and "review_papers" in existing_tables:
                    for paper_row in con.execute(
                        "SELECT id, phase, items FROM review_papers WHERE learner=? AND phase NOT IN ('done', 'completed', 'expired', 'cancelled')",
                        (learner,),
                    ).fetchall():
                        try:
                            paper_items = json.loads(paper_row["items"] or "[]")
                        except ValueError:
                            paper_items = []
                        if any(isinstance(it, dict) and it.get("point_id") in old_rp_ids for it in paper_items):
                            raise DomainError(
                                "incompatible_topic_revision",
                                f"Topic {tid} 存在未完结复习试卷 {paper_row['id']}，已中止自动版本迁移。",
                                409,
                            )

        backups_dir = Path(data_dir) / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backups_dir / f"learning-pre-migrate-{safe_stamp}-{uuid.uuid4().hex[:8]}.sqlite3"
        with closing(sqlite3.connect(str(backup_path))) as bkp_con:
            con.backup(bkp_con)

        migrated_topics: list[dict[str, str]] = []
        migrated_review_versions: set[tuple[str, str]] = set()
        con.execute("BEGIN IMMEDIATE")
        try:
            for learner, tid, old_version, raw_body, new_topic in migrations:
                new_version = str(new_topic["version"])
                new_cv = new_topic.get("content_version")
                old_topic = prev_map.get(tid)
                old_cards = (
                    {c.get("id"): c for c in (old_topic.get("flashcards") or []) if isinstance(c, dict)}
                    if isinstance(old_topic, dict)
                    else {}
                )
                body = json.loads(raw_body)
                if new_cv is not None:
                    old_cv = old_topic.get("content_version") if isinstance(old_topic, dict) else body.get("content_version")
                    if body.get("read_content_version") and body.get("read_content_version") == old_cv:
                        body["read_content_version"] = new_cv
                    body["content_version"] = new_cv

                atomic = body.get("atomic")
                if isinstance(atomic, dict) and isinstance(atomic.get("history"), list):
                    for entry in atomic["history"]:
                        if not isinstance(entry, dict):
                            continue
                        cid = entry.get("card_id")
                        if "snapshot" not in entry and isinstance(cid, str) and cid in old_cards:
                            entry["snapshot"] = _card_snapshot(old_cards[cid], old_version)
                            entry["snapshot_version"] = old_version

                con.execute(
                    "UPDATE topics SET version=?, body=? WHERE learner=? AND topic=?",
                    (new_version, json.dumps(body, ensure_ascii=False), learner, tid),
                )
                if "practice_queues" in existing_tables:
                    con.execute(
                        "UPDATE practice_queues SET version=? WHERE learner=? AND topic=? AND version=?",
                        (new_version, learner, tid, old_version),
                    )
                if (tid, old_version) not in migrated_review_versions and "review_points" in existing_tables:
                    migrated_review_versions.add((tid, old_version))
                    rp_rows = con.execute(
                        "SELECT id, subject, source_point, created_at FROM review_points WHERE kind='atomic' AND container=? AND version=?",
                        (tid, old_version),
                    ).fetchall()
                    for rp in rp_rows:
                        old_pid = str(rp["id"])
                        new_pid = point_id("atomic", tid, new_version, str(rp["source_point"]))
                        if con.execute("SELECT 1 FROM review_points WHERE id=?", (new_pid,)).fetchone() is None:
                            con.execute(
                                """INSERT INTO review_points
                                (id, subject, kind, container, version, source_point, created_at)
                                VALUES (?,?,?,?,?,?,?)""",
                                (new_pid, rp["subject"], "atomic", tid, new_version, rp["source_point"], rp["created_at"]),
                            )
                        if "review_variants" in existing_tables:
                            con.execute("UPDATE review_variants SET point=? WHERE point=?", (new_pid, old_pid))
                        if old_pid != new_pid:
                            con.execute("DELETE FROM review_points WHERE id=?", (old_pid,))

                migrated_topics.append(
                    {
                        "learner": learner,
                        "topic_id": tid,
                        "from_version": old_version,
                        "to_version": new_version,
                    }
                )
            con.commit()
        except Exception:
            con.rollback()
            raise

    return {"migrated_topics": migrated_topics, "backup_path": str(backup_path)}


def _access_topic_entries(catalog: Catalog, subject_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for course in catalog.courses.values():
        for entry in course["topics"]:
            topic = catalog.topic(entry["id"])
            entries.append(
                {
                    "id": topic["id"],
                    "title": topic.get("title", topic["id"]),
                    "description": topic.get("description", ""),
                    "subject": topic.get("subject", subject_id),
                    "course_id": course["id"],
                    "course_title": course.get("title", course["id"]),
                    "prerequisites": list(entry.get("prerequisites") or []),
                    "topic_format_version": topic.get("topic_format_version", 1),
                    "type": topic.get("type", "topic"),
                }
            )
    return entries


class LocalAccessStore(AccessStore):
    """Single-learner SQLite store bypassing invitation ACLs while preserving learner state."""

    def __init__(
        self,
        data_dir: Path,
        topics: list[dict[str, Any]],
        *,
        test_materials: TestMaterials | None = None,
    ) -> None:
        super().__init__(
            data_dir,
            topics,
            guest_topic_ids=[item["id"] for item in topics],
            test_materials=test_materials,
        )
        self._local_access = self._ensure_local_principal()

    def _ensure_local_principal(self) -> dict[str, Any]:
        with self._transaction() as con:
            row = con.execute(
                "SELECT * FROM access_principals WHERE learner_id=?",
                (LOCAL_LEARNER_ID,),
            ).fetchone()
            now_iso = utc_now().isoformat()
            all_topics = list(self.topics)
            all_features = list(FEATURES)
            if row is None:
                con.execute(
                    """INSERT INTO access_principals
                    (learner_id,role,display_name,features,topic_ids,invitation_digest,
                     created_at,updated_at,purpose,batch_id,topics_default,features_default,
                     is_admin,is_advanced_learner,is_student,admin_name,enabled)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        LOCAL_LEARNER_ID,
                        "account",
                        LOCAL_DISPLAY_NAME,
                        json.dumps(all_features),
                        json.dumps(all_topics),
                        None,
                        now_iso,
                        now_iso,
                        "learner",
                        None,
                        1,
                        1,
                        0,
                        1,
                        1,
                        LOCAL_DISPLAY_NAME,
                        1,
                    ),
                )
            else:
                con.execute(
                    """UPDATE access_principals
                    SET role='account', enabled=1, purpose='learner',
                        topics_default=1, features_default=1,
                        is_admin=0, is_advanced_learner=1, is_student=1,
                        updated_at=?
                    WHERE learner_id=?""",
                    (now_iso, LOCAL_LEARNER_ID),
                )
            refreshed = con.execute(
                "SELECT * FROM access_principals WHERE learner_id=?",
                (LOCAL_LEARNER_ID,),
            ).fetchone()
        return self._public(refreshed)

    def local_access(self) -> dict[str, Any]:
        return {
            **self._local_access,
            "features": list(FEATURES),
            "topics": [dict(meta) for meta in self.topics.values()],
        }

    def resolve(self, token: str | None = None) -> dict[str, Any]:
        return self.local_access()

    def create_guest(self) -> dict[str, Any]:
        return {"identity_token": LOCAL_IDENTITY_TOKEN, "access": self.local_access()}

    def login(self, invitation_code: str, current_token: str | None = None) -> dict[str, Any]:
        return {"identity_token": LOCAL_IDENTITY_TOKEN, "access": self.local_access()}

    def logout(self, token: str | None = None) -> dict[str, str]:
        return {"status": "local"}

    def authorize(self, access: dict[str, Any], topic_id: str, feature: str | None = None) -> None:
        if topic_id not in self.topics:
            raise DomainError("unknown_topic", f"未知 Topic：{topic_id}", 404)


class LocalRuntime:
    """Coordinated local-personal engine wrapping shared graspmemoedu components."""

    def __init__(
        self,
        *,
        packages_dir: str | Path | None = None,
        data_dir: str | Path | None = None,
        web_dir: str | Path | None = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        reset: bool = False,
        clock: Callable[[], datetime] | None = None,
        subject_id: str = DEFAULT_SUBJECT_ID,
        course_id: str = DEFAULT_COURSE_ID,
        ai_transport: Any | None = None,
    ) -> None:
        self.host = validate_loopback_host(host)
        self.port = validate_port(port)
        self.packages_dir = resolve_packages_dir(packages_dir)
        self.data_dir = resolve_data_dir(data_dir)
        self.web_dir = resolve_web_dir(web_dir)
        self.subject_id = subject_id
        self.course_id = course_id
        self.instance_id = uuid.uuid4().hex
        self.process_started_at = process_started_at()
        self.clock = clock or utc_now
        self.ai_transport = ai_transport
        self._services: dict[tuple[str, str], Any] = {}
        self._services_lock = threading.Lock()
        self._admission_lock = threading.RLock()
        self._in_flight: set[str] = set()
        self._in_flight_jobs: dict[str, tuple[str, str]] = {}
        self._judge_threads: set[threading.Thread] = set()

        if reset:
            reset_runtime_state(self.data_dir)

        previous_topics = _load_existing_topics(self.data_dir)
        self.manifests = ensure_runtime_manifests(
            self.packages_dir,
            self.data_dir,
            subject_id=self.subject_id,
            course_id=self.course_id,
        )
        self.settings = Settings(
            data_dir=self.data_dir,
            catalog_path=self.data_dir / "catalog.json",
            host=self.host,
            port=self.port,
            instance_id=self.instance_id,
        )
        self.catalog = Catalog.load(self.settings)
        self.subjects = Subjects(self.settings, self.catalog)
        self.training = TrainingCatalog(content_root(self.data_dir))
        self.training.validate_ownership(self.catalog, self.subjects)
        self.revision_migration = reconcile_compatible_topic_revisions(
            self.data_dir,
            catalog=self.catalog,
            previous_topics=previous_topics,
            now_iso=self.clock().isoformat(),
        )
        self.reference_index = ContentReferenceIndex(self.catalog.topics)
        self.fsrs_engine = FSRSEngine()
        self.judge = JapaneseGrammarJudge()
        self.default_topic_id = (
            DEFAULT_TOPIC_ID
            if DEFAULT_TOPIC_ID in self.catalog.topics
            else next(iter(self.catalog.topics))
        )
        # Seed SQLite learning tables before AccessStore/DashboardStore query them.
        self.default_service = self._create_service_for(LOCAL_LEARNER_ID, self.default_topic_id)
        self._services[(LOCAL_LEARNER_ID, self.default_topic_id)] = self.default_service
        self.test_materials = self.subjects.test_materials
        self.access_store = LocalAccessStore(
            self.data_dir,
            _access_topic_entries(self.catalog, self.subject_id)
            + self.training.permissions(self.catalog.topics),
            test_materials=self.subjects.test_materials,
        )
        self.dashboard_store = DashboardStore(
            self.catalog,
            self.access_store,
            subjects=self.subjects,
            atomic_clock=self.clock,
            training=self.training,
        )
        self._seed_default_course_selection()
        self.dependency_policy = ClockAwareDependencyPolicy(
            self.catalog,
            self.access_store,
            subjects=self.subjects,
            training=self.training,
            clock=self.clock,
        )
        self.graph_store = GraphStore(
            self.settings,
            catalog=self.catalog,
            subjects=self.subjects,
            training=self.training,
        )
        self.public_limits = PublicLimits(clock=self.clock, data_dir=self.data_dir)
        self.default_service.resume_due()

    def _seed_default_course_selection(self) -> None:
        if self.course_id not in self.catalog.courses:
            return
        with self.access_store._transaction() as con:
            now_iso = self.clock().isoformat()
            row = con.execute(
                "SELECT selected_course_id FROM learner_subject_preferences WHERE learner_id=? AND subject_id=?",
                (LOCAL_LEARNER_ID, self.subject_id),
            ).fetchone()
            if row is None or row["selected_course_id"] not in self.catalog.courses:
                con.execute(
                    """INSERT INTO learner_subject_preferences (learner_id, subject_id, selected_course_id, updated_at)
                    VALUES (?,?,?,?)
                    ON CONFLICT(learner_id, subject_id) DO UPDATE SET
                        selected_course_id=excluded.selected_course_id,
                        updated_at=excluded.updated_at""",
                    (LOCAL_LEARNER_ID, self.subject_id, self.course_id, now_iso),
                )
            pref = con.execute(
                "SELECT selected_course_id FROM learner_preferences WHERE learner_id=?",
                (LOCAL_LEARNER_ID,),
            ).fetchone()
            if pref is None or pref["selected_course_id"] not in self.catalog.courses:
                con.execute(
                    """INSERT INTO learner_preferences (learner_id, selected_course_id, timezone, updated_at)
                    VALUES (?,?,?,?)
                    ON CONFLICT(learner_id) DO UPDATE SET
                        selected_course_id=excluded.selected_course_id,
                        updated_at=excluded.updated_at""",
                    (LOCAL_LEARNER_ID, self.course_id, None, now_iso),
                )

    def _create_service_for(self, learner_id: str, topic_id: str):
        topic = self.catalog.topic(topic_id)
        options: dict[str, Any] = {}
        if (has_atomic(topic) or is_atomic(topic) or sectioned_training(topic)) and self.clock is not None:
            options["clock"] = self.clock
        service = create_learning_service(
            topic,
            self.data_dir,
            judge=self.judge,
            learner_id=learner_id,
            **options,
        )
        if (
            trainable(service.course)
            and getattr(service, "review_backend", None) is None
            and not is_atomic(service.course)
            and not is_introduction(service.course)
        ):
            service.review_backend = ReviewBackend(
                service,
                engine=self.fsrs_engine,
                clock=self.clock,
            )
        else:
            service.review_backend = None
        return service

    def service_for(
        self,
        learner_id: str,
        topic_id: str | None = None,
        session_scope: str | None = None,
        *,
        scope_digest: str | None = None,
    ):
        del session_scope, scope_digest
        resolved_topic = topic_id or self.default_topic_id
        key = (learner_id, resolved_topic)
        with self._services_lock:
            service = self._services.get(key)
            if service is None:
                service = self._create_service_for(learner_id, resolved_topic)
                self._services[key] = service
        service.resume_due()
        return service

    def services_snapshot(self) -> dict[str, Any]:
        with self._services_lock:
            return {
                topic_id: service
                for (learner_id, topic_id), service in self._services.items()
                if learner_id == LOCAL_LEARNER_ID
            }

    @staticmethod
    def schedule(service) -> dict[str, Any] | None:
        backend = getattr(service, "review_backend", None)
        if backend is None:
            return None
        due = backend.due()
        return {
            "due_reviews": due,
            "due_review_count": len(due),
            "next_due_at": backend.next_due_at(),
        }

    def begin_in_flight(self, submission_id: str, learner_id: str, topic_id: str) -> bool:
        with self._admission_lock:
            if submission_id in self._in_flight:
                return False
            self._in_flight.add(submission_id)
            self._in_flight_jobs[submission_id] = (learner_id, topic_id)
            return True

    def finish_in_flight(self, submission_id: str) -> None:
        with self._admission_lock:
            self._in_flight.discard(submission_id)
            self._in_flight_jobs.pop(submission_id, None)

    def outstanding_count(self, learner_id: str, topic_id: str) -> int:
        with self._admission_lock:
            return sum(
                1 for lid, tid in self._in_flight_jobs.values()
                if lid == learner_id and tid == topic_id
            )

    def outstanding_submissions(self, con) -> int:
        """Count active pending/running submissions across all shared submission tables."""
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        db_total = sum(
            con.execute(f"SELECT COUNT(*) FROM {table} WHERE status IN ('pending','running')").fetchone()[0]
            for table in ("submissions", "review_submissions", "training_submissions", "paper_submissions")
            if table in tables
        )
        with self._admission_lock:
            in_flight_total = len(self._in_flight)
        return max(in_flight_total, db_total)

    def schedule_submission(self, target: Any, submission_id: str, review: bool = False) -> None:
        """Schedule synchronous instant judging or background thread judging for review/paper routes."""
        worker = getattr(target, "review_backend", None) if review else target
        if worker is None:
            return
        instant = getattr(worker, "instant_submission", None)
        if callable(instant) and instant(submission_id):
            worker.process_submission(submission_id)
            return
        learner_id = str(getattr(worker, "learner_id", None) or getattr(target, "learner_id", None) or LOCAL_LEARNER_ID)
        topic_id = str(getattr(target, "topic_id", None) or self.default_topic_id)
        if self.begin_in_flight(submission_id, learner_id, topic_id):
            def run_job() -> None:
                try:
                    worker.process_submission(submission_id)
                finally:
                    self.finish_in_flight(submission_id)

            prefix = "review-judge" if review else "submission-judge"
            self.spawn_judge_thread(run_job, name=f"{prefix}-{submission_id[:12]}")

    def recover_interrupted(self) -> None:
        """Mark interrupted pending/running submissions as retryable errors after startup."""
        TrainingService(self.training, self.settings.data_dir, "recovery").recover_interrupted()
        with self.access_store._transaction() as con:
            PaperService.recover(con)
            topic_rows = (
                con.execute("SELECT DISTINCT learner, topic FROM topics").fetchall()
                if self._table_exists(con, "topics")
                else []
            )
        recovered_keys: set[tuple[str, str]] = set()
        for row in topic_rows:
            tid = row["topic"]
            if tid not in self.catalog.topics:
                continue
            lid = row["learner"]
            recovered_keys.add((lid, tid))
            svc = self.service_for(lid, tid)
            svc.recover_interrupted()
            if svc.review_backend is not None:
                svc.review_backend.recover_interrupted()
        if (LOCAL_LEARNER_ID, self.default_topic_id) not in recovered_keys:
            self.default_service.recover_interrupted()
            if self.default_service.review_backend is not None:
                self.default_service.review_backend.recover_interrupted()

    def recover_cooldowns(self, access: dict[str, Any]) -> None:
        """Advance expired topic/atomic cooldowns for active learner topics."""
        learner_id = access["learner_id"]
        with closing(self.access_store._connect()) as con:
            rows = (
                con.execute(
                    "SELECT topic, body FROM topics WHERE learner=?",
                    (learner_id,),
                ).fetchall()
                if self._table_exists(con, "topics")
                else []
            )
            review_pauses = (
                {
                    r["topic"]
                    for r in con.execute(
                        "SELECT DISTINCT topic FROM review_topic_pauses WHERE learner=?",
                        (learner_id,),
                    ).fetchall()
                }
                if self._table_exists(con, "review_topic_pauses")
                else set()
            )
        for row in rows:
            tid = row["topic"]
            if tid not in self.catalog.topics:
                continue
            try:
                body = json.loads(row["body"])
            except ValueError:
                body = {}
            atomic_state = body.get("atomic") if isinstance(body.get("atomic"), dict) else {}
            if (
                body.get("cooldown")
                or body.get("pause")
                or atomic_state.get("cooldown")
                or atomic_state.get("pause")
                or tid in review_pauses
            ):
                self.service_for(learner_id, tid)

    def spawn_judge_thread(self, target: Callable[[], None], name: str) -> None:
        def runner() -> None:
            try:
                target()
            finally:
                with self._admission_lock:
                    self._judge_threads.discard(threading.current_thread())

        thread = threading.Thread(target=runner, name=name, daemon=True)
        with self._admission_lock:
            self._judge_threads.add(thread)
        thread.start()

    def join_judge_threads(self, timeout: float = 5.0) -> None:
        with self._admission_lock:
            threads = list(self._judge_threads)
        for thread in threads:
            thread.join(timeout)

    def references_for(self, access: dict[str, Any], topic_id: str) -> dict[str, Any]:
        learner_id = access["learner_id"]
        snapshots: dict[str, Any] = {}
        allowed_ids = {t["id"] for t in access.get("topics", [])}
        with closing(self.access_store._connect()) as con:
            rows = con.execute(
                "SELECT topic, version, body FROM topics WHERE learner=?",
                (learner_id,),
            ).fetchall()
        for row in rows:
            tid = row["topic"]
            if tid not in allowed_ids or tid not in self.catalog.topics:
                continue
            try:
                snapshots[tid] = json.loads(row["body"])
            except ValueError:
                continue
        if topic_id in self.catalog.topics and topic_id not in snapshots:
            svc = self.service_for(learner_id, topic_id)
            snapshots[topic_id] = svc.state()

        def subject_for(tid: str) -> str:
            return self.subjects.topic_subject(tid)

        def root_ready(tid: str) -> bool:
            with closing(self.access_store._connect()) as con:
                return bool(
                    self.dependency_policy.ready(
                        con,
                        access,
                        tid,
                        current_time=self.clock().isoformat(),
                    )
                )

        return self.reference_index.view(
            access,
            topic_id,
            snapshots,
            subject_for,
            root_ready=root_ready,
        )

    def pause_rows(
        self,
        learner_id: str,
        *,
        topic_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List active pause and skip records across installed topics for local unlock."""
        items: list[dict[str, Any]] = []
        with closing(self.access_store._connect()) as con:
            reviews: dict[str, dict[str, Any]] = {}
            if self._table_exists(con, "review_topic_pauses"):
                for row in con.execute(
                    "SELECT * FROM review_topic_pauses WHERE learner=?",
                    (learner_id,),
                ).fetchall():
                    reviews[row["topic"]] = dict(row)

            has_events = self._table_exists(con, "events")
            topic_rows = con.execute(
                "SELECT topic, version, body FROM topics WHERE learner=? ORDER BY topic",
                (learner_id,),
            ).fetchall() if self._table_exists(con, "topics") else []

            seen_topics: set[str] = set()
            for row in topic_rows:
                tid = row["topic"]
                seen_topics.add(tid)
                if topic_id and tid != topic_id:
                    continue
                if tid not in self.catalog.topics:
                    continue
                topic = self.catalog.topic(tid)
                course = self.catalog.course_context(tid)
                state = json.loads(row["body"])

                for mod_id, record in (state.get("skipped_modules") or {}).items():
                    module = next(
                        (m for m in topic.get("modules", []) if m.get("id") == mod_id),
                        None,
                    )
                    items.append(
                        {
                            "learner_id": learner_id,
                            "topic_id": tid,
                            "topic_title": topic.get("title", tid),
                            "course_title": course.get("title", course.get("id", "")),
                            "subject_id": self.subjects.topic_subject(tid),
                            "module_id": mod_id,
                            "module_title": (module or {}).get("title", mod_id),
                            "pause_event_id": record["event_id"],
                            "event_id": record["event_id"],
                            "kind": "skip",
                            "reason": "module_skipped",
                            "paused_at": record.get("created_at"),
                            "released": record.get("released"),
                            "review_only": False,
                            "version_current": row["version"] == topic.get("version"),
                        }
                    )

                pause = state.get("pause") or (state.get("atomic") or {}).get("pause") or reviews.get(tid)
                if not pause:
                    continue
                event_row = (
                    con.execute("SELECT created_at FROM events WHERE id=?", (pause["event_id"],)).fetchone()
                    if has_events
                    else None
                )
                mod_id = pause.get("module_id")
                module = next(
                    (m for m in topic.get("modules", []) if m.get("id") == mod_id),
                    None,
                )
                items.append(
                    {
                        "learner_id": learner_id,
                        "topic_id": tid,
                        "topic_title": topic.get("title", tid),
                        "course_title": course.get("title", course.get("id", "")),
                        "subject_id": self.subjects.topic_subject(tid),
                        "module_id": mod_id,
                        "module_title": (module or {}).get("title", mod_id or ""),
                        "pause_event_id": pause["event_id"],
                        "event_id": pause["event_id"],
                        "kind": "review" if not state.get("pause") else "topic",
                        "reason": pause.get("reason") or "",
                        "paused_at": pause.get("created_at") or (event_row["created_at"] if event_row else None),
                        "review_only": not bool(state.get("pause")),
                        "version_current": row["version"] == topic.get("version"),
                    }
                )

            for tid, rpause in reviews.items():
                if tid in seen_topics or (topic_id and tid != topic_id) or tid not in self.catalog.topics:
                    continue
                topic = self.catalog.topic(tid)
                course = self.catalog.course_context(tid)
                items.append(
                    {
                        "learner_id": learner_id,
                        "topic_id": tid,
                        "topic_title": topic.get("title", tid),
                        "course_title": course.get("title", course.get("id", "")),
                        "subject_id": self.subjects.topic_subject(tid),
                        "module_id": rpause.get("module_id"),
                        "module_title": rpause.get("module_id") or "",
                        "pause_event_id": rpause["event_id"],
                        "event_id": rpause["event_id"],
                        "kind": "review",
                        "reason": rpause.get("reason") or "",
                        "paused_at": rpause.get("created_at"),
                        "review_only": True,
                        "version_current": True,
                    }
                )

        items.sort(key=lambda item: (item.get("paused_at") or "", item["pause_event_id"]), reverse=True)
        total = len(items)
        page = items[offset : offset + limit]
        return {
            "items": page,
            "events": page,
            "total": total,
            "offset": offset,
            "limit": limit,
            "next_offset": offset + limit if offset + limit < total else None,
        }

    def unlock_pause(
        self,
        learner_id: str,
        *,
        topic_id: str,
        module_id: str | None,
        pause_event_id: str,
    ) -> dict[str, Any]:
        """Unlock a specific paused topic, module, skip, or review event via shared services."""
        if topic_id not in self.catalog.topics:
            raise DomainError("unknown_topic", f"未知 Topic：{topic_id}", 404)
        topic = self.catalog.topic(topic_id)
        review_pause = None
        review_replay = False
        skip_event = False
        with closing(self.access_store._connect()) as con:
            row = con.execute(
                "SELECT version, body FROM topics WHERE learner=? AND topic=?",
                (learner_id, topic_id),
            ).fetchone() if self._table_exists(con, "topics") else None
            if row is not None and row["version"] != topic.get("version"):
                raise DomainError("course_version_mismatch", "该暂停对应旧版内容，不能直接解锁。", 409)
            state = json.loads(row["body"]) if row is not None else {}
            atomic_pause = (state.get("atomic") or {}).get("pause")
            pause = state.get("pause") or atomic_pause
            if pause and pause.get("event_id") == pause_event_id:
                expected_module = pause.get("module_id")
                if (
                    expected_module is not None
                    and module_id is not None
                    and module_id not in (expected_module, "atomic")
                ):
                    raise DomainError("unlock_mismatch", "暂停模块不匹配，请刷新后重试。", 409)
                if expected_module is not None:
                    module_id = expected_module
            if self._table_exists(con, "review_topic_pauses"):
                review_pause = con.execute(
                    "SELECT * FROM review_topic_pauses WHERE learner=? AND topic=?",
                    (learner_id, topic_id),
                ).fetchone()
            if self._table_exists(con, "review_unlocks"):
                review_replay = bool(
                    con.execute(
                        "SELECT 1 FROM review_unlocks WHERE learner=? AND topic=? AND event_id=?",
                        (learner_id, topic_id, pause_event_id),
                    ).fetchone()
                )
            skip_record = (state.get("skipped_modules") or {}).get(module_id) if module_id else None
            skip_event = bool(skip_record and skip_record.get("event_id") == pause_event_id)

        learner = self.service_for(learner_id, topic_id)
        if not skip_event and learner.review_backend is not None and (review_pause or review_replay):
            learner.review_backend.unlock_topic(pause_event_id=pause_event_id)
        elif getattr(learner, "atomic", None) is not None and (
            atomic_pause is not None or not learner.course.get("modules")
        ):
            learner.atomic.unlock(topic_id, "atomic", pause_event_id)
        else:
            learner.unlock(topic_id, module_id, pause_event_id)
        return {
            "unlocked": True,
            "topic_id": topic_id,
            "module_id": module_id,
            "pause_event_id": pause_event_id,
        }

    @staticmethod
    def _table_exists(con, table_name: str) -> bool:
        row = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None


__all__ = [
    "DATA_DIR_ENV",
    "DEFAULT_COURSE_DESCRIPTION",
    "DEFAULT_COURSE_ID",
    "DEFAULT_COURSE_TITLE",
    "DEFAULT_HOST",
    "DEFAULT_PACKAGES_DIR",
    "DEFAULT_PORT",
    "DEFAULT_RUNTIME_DIR",
    "DEFAULT_SUBJECT_ID",
    "DEFAULT_TOPIC_ID",
    "DEFAULT_WEB_DIR",
    "FORBIDDEN_PORTS",
    "FORBIDDEN_RUNTIME_DIRS",
    "LOCAL_DISPLAY_NAME",
    "LOCAL_IDENTITY_TOKEN",
    "LOCAL_LEARNER_ID",
    "LocalAccessStore",
    "LocalRuntime",
    "PACKAGES_DIR_ENV",
    "REPO_ROOT",
    "SERVER_METADATA_FILE",
    "SERVER_SERVICE_ID",
    "data_lock",
    "ensure_runtime_manifests",
    "process_started_at",
    "remove_server_metadata",
    "reset_runtime_state",
    "resolve_data_dir",
    "resolve_packages_dir",
    "resolve_web_dir",
    "validate_data_dir",
    "validate_loopback_host",
    "validate_port",
    "write_server_metadata",
]
