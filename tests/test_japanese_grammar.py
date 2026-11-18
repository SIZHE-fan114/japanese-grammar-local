"""Verification & E2E tests for the GraspMemoEdu Japanese Grammar local-personal adapter."""
from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import uuid

from fastapi.testclient import TestClient
import httpx

from graspmemoedu.service import DomainError
from graspmemoedu.question_types import demo_answer
from tools.japanese_grammar.backend import (
    DEFAULT_COURSE_ID,
    DEFAULT_SUBJECT_ID,
    FORBIDDEN_PORTS,
    LOCAL_LEARNER_ID,
    MAX_REQUEST_BODY_BYTES,
    JapaneseGrammarJudge,
    LocalRuntime,
    SERVER_SERVICE_ID,
    canonical_japanese,
    complete_chat,
    create_app,
    ensure_runtime_manifests,
    open_chat_stream,
    per_blank_results,
    reconcile_compatible_topic_revisions,
)
from tools.japanese_grammar.backend.page_edit_store import EditPage, PageEditStore


REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "tools" / "japanese_grammar" / "packages"
WEB_DIR = REPO_ROOT / "tools" / "japanese_grammar" / "web"

JP01 = "jp01-copula-particles"
JP02 = "jp02-spo-object-particles"
JP03 = "jp03-adjectives-and-mo"
JP04 = "jp04-verbs-existence-past"
JP05 = "jp05-negation-system"
JP06 = "jp06-modifiers-and-listing"
ALL_TOPICS = (JP01, JP02, JP03, JP04, JP05, JP06)

FORBIDDEN_CONTENT_TOKENS = (
    "[Untitled]",
    "beta.remnote.com",
    "file:///",
    "私が高学生",
    "映画で見たた銀行",
    "ちょうど",
    "thought",
)


class MutableClock:
    """Deterministic UTC clock for testing FSRS schedules and chunk spacing."""

    def __init__(self, initial: datetime | None = None) -> None:
        self.now = initial or datetime(2026, 11, 14, 0, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> datetime:
        self.now += timedelta(**kwargs)
        return self.now


def _pick_free_loopback_port() -> int:
    """Return an ephemeral loopback TCP port outside reserved service ports."""
    import socket

    for _ in range(25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if port not in FORBIDDEN_PORTS:
            return port
    raise AssertionError("Failed to obtain a free non-forbidden loopback port.")


def _load_topic(topic_id: str) -> dict:
    path = PACKAGES_DIR / topic_id / "topic.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _all_flashcards() -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for tid in ALL_TOPICS:
        for fc in _load_topic(tid).get("flashcards", []):
            cards[fc["id"]] = fc
    return cards


def _wrong_fill_blank_answer(question: dict) -> str:
    blanks = (question.get("interaction") or {}).get("blanks") or []
    return json.dumps({str(b["id"]): "__WRONG_JP__" for b in blanks}, ensure_ascii=False)


class JapaneseGrammarCurriculumAndJudgeTests(unittest.TestCase):
    """Curriculum package schema invariants and offline JapaneseGrammarJudge contracts."""

    def test_page_revision_freezes_existing_presentations_and_applies_to_later_ones(self) -> None:
        with tempfile.TemporaryDirectory(prefix="jp_page_revision_") as temporary:
            clock = MutableClock()
            store = PageEditStore(Path(temporary), clock=clock)
            original = EditPage(JP01, "question", "test-card", {"html": "<p>原文 {{blank:b1}}</p>"})
            existing = replace(original, presentation_id="previous-paper", presented_at=clock().isoformat())
            clock.advance(seconds=1)
            live_lesson = replace(original, presentation_id="current-lesson", presented_at=clock().isoformat())
            edit = store.save(live_lesson, 0, {"html": "<p>新版 {{blank:b1}}</p>"})
            self.assertEqual(store.view(live_lesson)["fields"], edit["fields"])
            # A paper opened before the edit keeps its original even on its first read.
            self.assertEqual(store.view(existing, pin=True)["fields"], dict(original.fields))
            clock.advance(seconds=1)
            future = replace(original, presentation_id="next-paper", presented_at=clock().isoformat())
            self.assertEqual(store.view(future, pin=True)["fields"], edit["fields"])
            self.assertEqual(store.view(existing)["fields"], dict(original.fields))

    def test_course_graph_and_pure_fill_blank_romaji_curriculum(self) -> None:
        graph_path = PACKAGES_DIR / "course_graph.json"
        self.assertTrue(graph_path.is_file())
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        self.assertEqual(graph["course_id"], DEFAULT_COURSE_ID)
        self.assertEqual(graph["subject_id"], DEFAULT_SUBJECT_ID)
        self.assertEqual([n["topic_id"] for n in graph["nodes"]], list(ALL_TOPICS))
        self.assertEqual(len(graph["edges"]), 7)

        total_intros = 0
        total_chunks = 0
        total_points = 0
        total_cards = 0
        single_cards = 0
        multi_cards = 0

        for tid in ALL_TOPICS:
            with self.subTest(topic_id=tid):
                raw = (PACKAGES_DIR / tid / "topic.json").read_text(encoding="utf-8")
                topic = json.loads(raw)
                self.assertEqual(topic["id"], tid)
                self.assertEqual(topic["subject_id"], DEFAULT_SUBJECT_ID)
                self.assertEqual(topic["course_id"], DEFAULT_COURSE_ID)
                self.assertEqual(topic["training_mode"], "atomic_retrieval")
                self.assertEqual(topic["modules"], [])
                self.assertGreaterEqual(raw.count("<ruby>"), 1)
                self.assertGreaterEqual(raw.count("jp-romaji"), 1)

                lowered = raw.lower()
                for token in FORBIDDEN_CONTENT_TOKENS:
                    self.assertNotIn(token.lower(), lowered)

                intros = topic.get("introductions", [])
                chunks = topic.get("memory_chunks", [])
                cards = topic.get("flashcards", [])
                total_intros += len(intros)
                total_chunks += len(chunks)
                for chunk in chunks:
                    self.assertTrue(chunk.get("anchors"))
                    total_points += len(chunk.get("points", []))
                total_cards += len(cards)

                for card in cards:
                    with self.subTest(card_id=card["id"]):
                        point_ids = card.get("point_ids", [])
                        self.assertGreaterEqual(len(point_ids), 1)
                        if len(point_ids) == 1:
                            single_cards += 1
                        else:
                            multi_cards += 1

                        inter = card.get("interaction") or {}
                        self.assertEqual(inter.get("type"), "fill_blank")
                        self.assertEqual(inter.get("grading"), "exact")
                        blanks = inter.get("blanks") or []
                        self.assertGreaterEqual(len(blanks), 1)

                        q_text = card.get("question", "")
                        h_text = card.get("html", "")
                        clean_html = re.sub(r"<ruby>.*?</ruby>|<code>.*?</code>", "", h_text, flags=re.S)

                        for blank in blanks:
                            marker = f"{{{{blank:{blank['id']}}}}}"
                            self.assertIn(marker, q_text)
                            self.assertIn(marker, h_text)
                            self.assertIn(marker, clean_html)
                            answers = blank.get("answers") or []
                            self.assertGreaterEqual(len(answers), 1)
                            for ans in answers:
                                self.assertNotIn("|", str(ans))

                for sec_name in ("introductions", "memory_chunks", "flashcards"):
                    for item in topic.get(sec_name, []):
                        for field in ("title", "html", "question", "explanation_html"):
                            text_val = item.get(field) or ""
                            self.assertIsNone(
                                re.search(r"(?<!\{)\{(?!\{)[^}]*\}", text_val),
                                f"{tid}/{sec_name}/{item.get('id')}.{field} contains unexpanded single-brace expression",
                            )

        self.assertEqual(total_intros, 13)
        self.assertEqual(total_chunks, 25)
        self.assertEqual(total_points, 47)
        self.assertEqual(total_cards, 206)
        self.assertEqual(single_cards, 188)
        self.assertEqual(multi_cards, 18)

    def test_japanese_grammar_judge_accepts_all_variants_and_rejects_wrong(self) -> None:
        judge = JapaneseGrammarJudge()
        self.assertTrue(judge.is_offline)
        self.assertTrue(judge.available())
        self.assertEqual(canonical_japanese("　がくせい です "), "がくせいです")

        all_cards = _all_flashcards()
        self.assertEqual(len(all_cards), 206)

        checked_multi_partial = False
        for cid, card in all_cards.items():
            blanks = card["interaction"]["blanks"]
            with self.subTest(card_id=cid):
                max_variants = max(len(b["answers"]) for b in blanks)
                for idx in range(max_variants):
                    payload = {
                        b["id"]: b["answers"][min(idx, len(b["answers"]) - 1)]
                        for b in blanks
                    }
                    passed, reason = judge(card, json.dumps(payload, ensure_ascii=False))
                    self.assertIs(passed, True, f"{cid} variant {idx} rejected: {reason}")

                # Fullwidth/ASCII space normalization keeps Japanese grading deterministic
                spaced_payload = {b["id"]: f"　{b['answers'][0]} " for b in blanks}
                passed_ws, _ = judge(card, json.dumps(spaced_payload, ensure_ascii=False))
                self.assertIs(passed_ws, True)

                wrong_payload = _wrong_fill_blank_answer(card)
                passed_wrong, wrong_reason = judge(card, wrong_payload)
                self.assertIs(passed_wrong, False)
                self.assertIn("✗", wrong_reason)

                if len(blanks) >= 2 and not checked_multi_partial:
                    checked_multi_partial = True
                    partial = {
                        blanks[0]["id"]: blanks[0]["answers"][0],
                        blanks[1]["id"]: "__WRONG_JP__",
                    }
                    for rest in blanks[2:]:
                        partial[rest["id"]] = rest["answers"][0]
                    detail = judge.grade_fill_blank(card, json.dumps(partial, ensure_ascii=False))
                    self.assertIs(detail["passed"], False)
                    by_id = {row["id"]: row for row in per_blank_results(card, json.dumps(partial))}
                    self.assertTrue(by_id[blanks[0]["id"]]["correct"])
                    self.assertFalse(by_id[blanks[1]["id"]]["correct"])

        self.assertTrue(checked_multi_partial)


class JapaneseGrammarBackendE2ETests(unittest.TestCase):
    """End-to-end TestClient flows: DAG gates, progression, FSRS review papers, pauses, security."""

    def _make_env(self, *, clock: MutableClock | None = None) -> tuple[Path, MutableClock, int]:
        tmp = tempfile.TemporaryDirectory(prefix="jp_grammar_test_")
        self.addCleanup(tmp.cleanup)
        data_dir = Path(tmp.name) / "data"
        use_clock = clock or MutableClock()
        port = _pick_free_loopback_port()
        return data_dir, use_clock, port

    def _make_client(
        self,
        data_dir: Path,
        clock: MutableClock,
        port: int,
    ) -> tuple[LocalRuntime, TestClient]:
        runtime = LocalRuntime(
            packages_dir=PACKAGES_DIR,
            data_dir=data_dir,
            web_dir=WEB_DIR,
            host="127.0.0.1",
            port=port,
            clock=clock,
        )
        app = create_app(runtime)
        client = TestClient(app, base_url=f"http://127.0.0.1:{port}")
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        return runtime, client

    def _complete_jp01(
        self,
        client: TestClient,
        clock: MutableClock,
        *,
        test_wrong_and_self_rating: bool = True,
    ) -> list[str]:
        fc_map = {fc["id"]: fc for fc in _load_topic(JP01)["flashcards"]}
        s = client.get("/api/state", params={"topic_id": JP01}).json()
        self.assertEqual(s["phase"], "introduction")
        self.assertIn("intro", s["introduction"]["id"])

        seen_intros: list[str] = []
        seen_chunk_anchors: list[str] = []
        tested_wrong = False
        tested_self_rating = False
        tested_chunk_spacing = False

        for _ in range(300):
            if s.get("status") == "completed" or s.get("phase") == "completed":
                break
            phase = s.get("phase")
            if phase == "introduction":
                intro_id = (s.get("introduction") or {}).get("id")
                if intro_id and intro_id not in seen_intros:
                    seen_intros.append(intro_id)
                s = client.post(
                    "/api/continue",
                    params={"topic_id": JP01},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                    },
                ).json()
                continue
            if phase == "chunk":
                chunk = s.get("chunk") or {}
                if chunk.get("anchors"):
                    seen_chunk_anchors.append(chunk["id"])
                s = client.post(
                    "/api/continue",
                    params={"topic_id": JP01},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                    },
                ).json()
                continue
            if phase == "answer":
                cur = s["current"]
                cid = cur["card_id"]
                fc = fc_map[cid]

                if test_wrong_and_self_rating and not tested_self_rating:
                    tested_self_rating = True
                    sr_resp = client.post(
                        "/api/submit",
                        params={"topic_id": JP01},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s["revision"],
                            "attempt_id": s["attempt_id"],
                            "step_id": s["active_step_id"],
                            "answer": demo_answer(fc),
                            "self_rating": 4,
                        },
                    )
                    self.assertEqual(sr_resp.status_code, 403)
                    self.assertEqual(sr_resp.json()["detail"]["code"], "self_rating_forbidden")

                if test_wrong_and_self_rating and not tested_wrong:
                    tested_wrong = True
                    wrong_resp = client.post(
                        "/api/submit",
                        params={"topic_id": JP01},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s["revision"],
                            "attempt_id": s["attempt_id"],
                            "step_id": s["active_step_id"],
                            "answer": _wrong_fill_blank_answer(fc),
                        },
                    )
                    self.assertEqual(wrong_resp.status_code, 200, wrong_resp.text)
                    wj = wrong_resp.json()
                    self.assertFalse(wj["correct"])
                    self.assertIsInstance(wj.get("blank_results"), dict)
                    self.assertTrue(all(v is False for v in wj["blank_results"].values()))
                    s = wj["state"]
                    self.assertEqual(s["phase"], "feedback")
                    continue

                right_resp = client.post(
                    "/api/submit",
                    params={"topic_id": JP01},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                        "answer": demo_answer(fc),
                        "elapsed_ms": 1200,
                    },
                )
                self.assertEqual(right_resp.status_code, 200, right_resp.text)
                rj = right_resp.json()
                self.assertTrue(rj["correct"])
                self.assertIsInstance(rj.get("blank_results"), dict)
                self.assertTrue(all(v is True for v in rj["blank_results"].values()))
                s = rj["state"]
                continue
            if phase == "feedback":
                if s.get("next_available_at"):
                    tested_chunk_spacing = True
                    clock.advance(seconds=180)
                s = client.post(
                    "/api/continue",
                    params={"topic_id": JP01},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                    },
                ).json()
                continue
            if phase == "waiting" or s.get("next_available_at"):
                tested_chunk_spacing = True
                # Verify premature continue before 180s cannot bypass chunk spacing
                early = client.post(
                    "/api/continue",
                    params={"topic_id": JP01},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                    },
                )
                self.assertEqual(early.status_code, 409)
                clock.advance(seconds=180)
                s = client.post(
                    "/api/continue",
                    params={"topic_id": JP01},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                    },
                ).json()
                continue
            self.fail(f"Unexpected jp01 state phase={phase!r}: {s}")

        self.assertEqual(s.get("status"), "completed")
        self.assertEqual(seen_intros, ["intro-jp01-copula", "intro-jp01-wa-ga"])
        self.assertEqual(len(seen_chunk_anchors), 4)
        if test_wrong_and_self_rating:
            self.assertTrue(tested_wrong)
            self.assertTrue(tested_self_rating)
            self.assertTrue(tested_chunk_spacing)
        return seen_intros

    def test_page_editor_suggests_only_the_current_intro_and_saves_without_touching_progress(self) -> None:
        data_dir, clock, port = self._make_env()
        runtime, client = self._make_client(data_dir, clock, port)
        state = client.get("/api/state", params={"topic_id": JP01}).json()
        intro = state["introduction"]
        pages = intro["pages"]
        self.assertGreater(len(pages), 1)
        target = {"view_id": "intro-tab", "sequence": 1, "kind": "introduction", "topic_id": JP01,
                  "presentation_id": intro["id"], "step_index": 0}

        with closing(sqlite3.connect(data_dir / "learning.sqlite3")) as connection:
            before = connection.execute("SELECT version, body FROM topics WHERE topic=?", (JP01,)).fetchone()

        opened = client.post("/api/page-edits/open", json=target)
        self.assertEqual(opened.status_code, 200, opened.text)
        editor = opened.json()
        self.assertEqual(editor["fields"], pages[0])
        suggestion = {**pages[0], "title": "更清楚的语法指导"}
        sent = []

        def upstream(request):
            payload = json.loads(request.content)
            sent.append(payload)
            self.assertFalse(payload["stream"])
            self.assertEqual(len(payload["messages"]), 2)
            context = json.loads(payload["messages"][1]["content"])
            self.assertEqual(context, {"kind": "introduction", "fields": pages[0], "instruction": "简化标题"})
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(suggestion)}}]})

        runtime.ai_transport = httpx.MockTransport(upstream)
        edit_request = {"token": editor["token"], "revision": editor["revision"]}
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://example.invalid/v1",
                                     "OPENAI_API_KEY": "fake-page-editor-key", "OPENAI_MODEL": "mock"}):
            result = client.post("/api/page-edits/suggest", json={**edit_request, "instruction": "简化标题"})
            runtime.ai_transport = httpx.MockTransport(lambda _request: httpx.Response(
                200, json={"choices": [{"message": {"content": '{"point_ids": ["other-page"]}'}}]},
            ))
            invalid_suggestion = client.post("/api/page-edits/suggest", json={**edit_request, "instruction": "简化标题"})

            def time_out(_request):
                raise httpx.ReadTimeout("synthetic timeout")

            runtime.ai_transport = httpx.MockTransport(time_out)
            timed_out = client.post("/api/page-edits/suggest", json={**edit_request, "instruction": "简化标题"})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["fields"]["title"], suggestion["title"])
        self.assertEqual(len(sent), 1)
        self.assertNotIn("fake-page-editor-key", json.dumps(sent))
        self.assertEqual(invalid_suggestion.status_code, 422)
        self.assertEqual(timed_out.status_code, 502)
        unchanged = client.get("/api/state", params={"topic_id": JP01}).json()
        self.assertEqual(unchanged["introduction"]["pages"], pages)

        other_view = client.post("/api/page-edits/open", json={**target, "view_id": "second-tab"}).json()
        blocked = client.post("/api/page-edits/open", json={**target, "topic_id": JP02})
        self.assertEqual(blocked.status_code, 409)
        invalid = client.put("/api/page-edits/current", json={
            **edit_request, "fields": {**suggestion, "html": '<p onclick="alert(1)">无效内容</p>'},
        })
        self.assertEqual(invalid.status_code, 422)
        saved = client.put("/api/page-edits/current", json={**edit_request, "fields": result.json()["fields"]})
        self.assertEqual(saved.status_code, 200, saved.text)
        stale = client.put("/api/page-edits/current", json={
            "token": other_view["token"], "revision": other_view["revision"], "fields": pages[0],
        })
        self.assertEqual(stale.status_code, 409)

        # Switching subpages in the same view invalidates the previous token.
        second = client.post("/api/page-edits/open", json={**target, "step_index": 1, "sequence": 2})
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["fields"], pages[1])
        self.assertEqual(client.post("/api/page-edits/open", json=target).status_code, 409)
        retired = client.put("/api/page-edits/current", json={
            "token": edit_request["token"], "revision": saved.json()["revision"], "fields": suggestion,
        })
        self.assertEqual(retired.status_code, 409)
        with closing(sqlite3.connect(data_dir / "learning.sqlite3")) as connection:
            self.assertEqual(connection.execute("SELECT version, body FROM topics WHERE topic=?", (JP01,)).fetchone(), before)

        client.__exit__(None, None, None)
        _, restarted = self._make_client(data_dir, clock, _pick_free_loopback_port())
        refreshed = restarted.get("/api/state", params={"topic_id": JP01}).json()["introduction"]["pages"]
        self.assertEqual(refreshed[0]["title"], suggestion["title"])
        self.assertEqual(refreshed[1:], pages[1:])

    def test_current_card_edits_preserve_blanks_grading_and_feedback_history(self) -> None:
        data_dir, clock, port = self._make_env()
        _, client = self._make_client(data_dir, clock, port)
        params = {"topic_id": JP01}

        def next_step(state):
            response = client.post("/api/continue", params=params, json={
                "request_id": str(uuid.uuid4()), "expected_revision": state["revision"],
                "attempt_id": state["attempt_id"], "step_id": state["active_step_id"],
            })
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()

        state = next_step(client.get("/api/state", params=params).json())
        chunk = state["chunk"]
        self.assertEqual(state["phase"], "chunk")
        edit_chunk = client.post("/api/page-edits/open", json={
            "view_id": "learning-tab", "kind": "chunk", "topic_id": JP01, "presentation_id": chunk["id"],
        }).json()
        updated_chunk = client.put("/api/page-edits/current", json={
            "token": edit_chunk["token"], "revision": edit_chunk["revision"],
            "fields": {**edit_chunk["fields"], "html": "<p>组块讲解测试</p>"},
        })
        self.assertEqual(updated_chunk.status_code, 200, updated_chunk.text)
        new_chunk = client.get("/api/state", params=params).json()["chunk"]
        self.assertEqual(new_chunk["editor_html"], "<p>组块讲解测试</p>")
        self.assertEqual(new_chunk["anchors"], chunk["anchors"])
        self.assertEqual(new_chunk["introduction"], chunk["introduction"])

        state = next_step(state)
        self.assertEqual(state["phase"], "answer")
        card = state["current"]
        target = {"view_id": "learning-tab", "topic_id": JP01, "presentation_id": card["id"]}
        hidden = client.post("/api/page-edits/open", json={**target, "kind": "explanation"})
        self.assertEqual(hidden.status_code, 409)
        opened = client.post("/api/page-edits/open", json={**target, "kind": "question"}).json()
        edit_request = {"token": opened["token"], "revision": opened["revision"]}
        removed_blank = re.sub(r"\{\{blank:[^}]*\}\}", "", opened["fields"]["html"])
        rejected = client.put("/api/page-edits/current", json={**edit_request, "fields": {"html": removed_blank}})
        self.assertEqual(rejected.status_code, 422)
        new_stem = "<p>补充题面提示</p>" + opened["fields"]["html"]
        saved = client.put("/api/page-edits/current", json={**edit_request, "fields": {"html": new_stem}})
        self.assertEqual(saved.status_code, 200, saved.text)
        refreshed = client.get("/api/state", params=params).json()
        self.assertEqual(refreshed["revision"], state["revision"])
        for key in ("id", "card_id", "point_ids", "shown_at", "interaction"):
            self.assertEqual(refreshed["current"][key], card[key])
        self.assertIn("补充题面提示", refreshed["current"]["html"])
        self.assertNotIn("reference_answer", refreshed["current"])

        authored = next(item for item in _load_topic(JP01)["flashcards"] if item["id"] == card["card_id"])
        submitted = client.post("/api/submit", params=params, json={
            "request_id": str(uuid.uuid4()), "expected_revision": state["revision"], "attempt_id": state["attempt_id"],
            "step_id": state["active_step_id"], "answer": demo_answer(authored), "elapsed_ms": 1100,
        }).json()
        self.assertTrue(submitted["correct"])
        feedback = submitted["state"]
        self.assertEqual(feedback["phase"], "feedback")
        back = client.post("/api/page-edits/open", json={**target, "kind": "explanation"}).json()
        explanation = "<p>修订后的解析</p>" + back["fields"]["html"]
        saved_back = client.put("/api/page-edits/current", json={
            "token": back["token"], "revision": back["revision"], "fields": {"html": explanation},
        })
        self.assertEqual(saved_back.status_code, 200, saved_back.text)
        visible = client.get("/api/state", params=params).json()["current"]
        self.assertEqual(visible["reference_answer"], feedback["current"]["reference_answer"])
        self.assertIn("修订后的解析", visible["explanation_html"])

        if feedback.get("next_available_at"):
            clock.advance(seconds=180)
        later = next_step(feedback)
        history = next(item for item in later["history"] if item["id"] == card["id"])
        self.assertEqual(history["html"], visible["html"])
        self.assertEqual(history["explanation_html"], visible["explanation_html"])
        self.assertEqual(client.post("/api/page-edits/open", json={**target, "kind": "explanation"}).status_code, 409)

    def test_jp01_progression_prereq_409_chunk_spacing_restart_and_review_papers(self) -> None:
        data_dir, clock, port = self._make_env()
        _rt1, client = self._make_client(data_dir, clock, port)

        # Subject/course/graph registry discovery
        subjects = client.get("/api/subjects").json()
        subject_map = {item["id"]: item for item in subjects["subjects"]}
        self.assertIn(DEFAULT_SUBJECT_ID, subject_map)
        graph = client.get(f"/api/graphs/{DEFAULT_COURSE_ID}", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
        self.assertEqual([n["topic_id"] for n in graph["nodes"]], list(ALL_TOPICS))
        self.assertEqual(len(graph["edges"]), 7)

        # Prerequisite gate blocks jp02 mutations with 409 until jp01 completes
        jp02_state = client.get("/api/state", params={"topic_id": JP02})
        self.assertEqual(jp02_state.status_code, 200)
        jp02_json = jp02_state.json()
        self.assertFalse(jp02_json["dependency_ready"])
        self.assertTrue(jp02_json["dependency_blocked"])

        blocked_cont = client.post(
            "/api/continue",
            params={"topic_id": JP02},
            json={
                "request_id": str(uuid.uuid4()),
                "expected_revision": jp02_json["revision"],
                "attempt_id": jp02_json["attempt_id"],
                "step_id": jp02_json["active_step_id"],
            },
        )
        self.assertEqual(blocked_cont.status_code, 409)
        self.assertEqual(blocked_cont.json()["detail"]["code"], "prerequisites_not_ready")

        # Complete jp01 end-to-end
        self._complete_jp01(client, clock, test_wrong_and_self_rating=True)

        # jp02 is now unlocked in the prerequisite DAG
        unlocked_jp02 = client.get("/api/state", params={"topic_id": JP02}).json()
        self.assertTrue(unlocked_jp02["dependency_ready"])
        self.assertFalse(unlocked_jp02["dependency_blocked"])
        cont_jp02 = client.post(
            "/api/continue",
            params={"topic_id": JP02},
            json={
                "request_id": str(uuid.uuid4()),
                "expected_revision": unlocked_jp02["revision"],
                "attempt_id": unlocked_jp02["attempt_id"],
                "step_id": unlocked_jp02["active_step_id"],
            },
        )
        self.assertEqual(cont_jp02.status_code, 200)

        # Simulate process restart on the SAME data_dir after closing client 1
        client.__exit__(None, None, None)
        ensure_runtime_manifests(PACKAGES_DIR, data_dir)
        _rt2, client2 = self._make_client(data_dir, clock, _pick_free_loopback_port())

        jp01_restarted = client2.get("/api/state", params={"topic_id": JP01}).json()
        self.assertEqual(jp01_restarted["status"], "completed")
        self.assertTrue(client2.get("/api/state", params={"topic_id": JP02}).json()["dependency_ready"])

        # FSRS point records persist in SQLite across restart
        with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
            row = con.execute(
                "SELECT body FROM topics WHERE learner=? AND topic=?",
                (LOCAL_LEARNER_ID, JP01),
            ).fetchone()
        self.assertIsNotNone(row)
        expected_jp01_points = sum(
            len(chunk.get("points", []))
            for chunk in _load_topic(JP01).get("memory_chunks", [])
        )
        persisted_points = json.loads(row[0])["atomic"]["points"]
        self.assertEqual(len(persisted_points), expected_jp01_points)
        self.assertTrue(all(p.get("mastered") and p.get("due_at") for p in persisted_points.values()))

        # Advance clock +2d -> due /api/atomic/reviews & full /api/review-papers flow
        clock.advance(days=2)
        due = client2.get("/api/atomic/reviews", params={"subject_id": DEFAULT_SUBJECT_ID})
        self.assertEqual(due.status_code, 200, due.text)
        due_items = due.json()["items"]
        self.assertTrue(any(item["topic_id"] == JP01 and item["due_count"] >= 1 for item in due_items))

        client2.app.state.review_paper_types = [{
            "id": "jp-two-card-edit-test", "title": "隔离双题复习卷", "subject": DEFAULT_SUBJECT_ID,
            "enabled": True, "requirements": {"fill_blank": 2},
        }]
        paper_scope = {"subject_id": DEFAULT_SUBJECT_ID}
        inbox_resp = client2.get("/api/review-papers/inbox", params=paper_scope)
        self.assertEqual(inbox_resp.status_code, 200, inbox_resp.text)
        inbox = inbox_resp.json()
        self.assertGreaterEqual(inbox["due_count"], 1)
        self.assertGreaterEqual(len(inbox["items"]), 1)

        candidate = next(item for item in inbox["items"] if item["kind"] == "paper")
        opened = client2.post(
            "/api/review-papers/open",
            params=paper_scope,
            json={"request_id": str(uuid.uuid4()), "candidate_id": candidate["id"]},
        )
        self.assertEqual(opened.status_code, 200, opened.text)
        paper = opened.json()
        self.assertEqual(paper["phase"], "answer")
        self.assertEqual(len(paper["items"]), 2)

        all_cards = _all_flashcards()
        rev = paper["revision"]
        draft_entries = [
            {
                "index": item["index"],
                "answer": demo_answer(all_cards[item["content_context"]["question_id"]]),
                "elapsed_ms": 900,
            }
            for item in paper["items"]
        ]
        # Schema enforces max 2 answers per /draft call
        for start in range(0, len(draft_entries), 2):
            draft_resp = client2.post(
                "/api/review-papers/draft",
                params={"subject_id": DEFAULT_SUBJECT_ID},
                json={
                    "paper_id": paper["id"],
                    "expected_revision": rev,
                    "answers": draft_entries[start:start + 2],
                },
            )
            self.assertEqual(draft_resp.status_code, 200, draft_resp.text)
            rev = draft_resp.json()["revision"]

        before_edit = draft_resp.json()
        edit_request = {
            "view_id": str(uuid.uuid4()), "kind": "question", "paper_id": paper["id"], "item_index": 0,
        }
        back_request = {**edit_request, "kind": "explanation"}
        hidden = client2.post("/api/page-edits/open", params=paper_scope, json=back_request)
        self.assertEqual(hidden.status_code, 409, hidden.text)
        edit_resp = client2.post("/api/page-edits/open", params=paper_scope, json=edit_request)
        self.assertEqual(edit_resp.status_code, 200, edit_resp.text)
        edit = edit_resp.json()
        self.assertEqual(edit["fields"], {"html": before_edit["items"][0]["html"]})
        edit_text = "修改后的作答提示"
        save_resp = client2.put("/api/page-edits/current", params=paper_scope, json={
            "token": edit["token"], "revision": edit["revision"],
            "fields": {"html": f"<p>{edit_text}</p>" + edit["fields"]["html"]},
        })
        self.assertEqual(save_resp.status_code, 200, save_resp.text)
        revised_html = save_resp.json()["fields"]["html"]
        self.assertIn(edit_text, revised_html)
        state_scope = {**paper_scope, "paper_id": paper["id"]}
        edited_paper = {
            **before_edit,
            "items": [{**before_edit["items"][0], "html": revised_html}, before_edit["items"][1]],
        }
        self.assertEqual(client2.get("/api/review-papers/state", params=state_scope).json(), edited_paper)

        # The saved display and existing answers survive another process restart.
        client2.__exit__(None, None, None)
        _rt3, client2 = self._make_client(data_dir, clock, _pick_free_loopback_port())
        self.assertEqual(client2.get("/api/review-papers/state", params=state_scope).json(), edited_paper)
        reopened = client2.post("/api/page-edits/open", params=paper_scope, json=edit_request)
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertEqual(reopened.json()["fields"], {"html": revised_html})

        sub_resp = client2.post(
            "/api/review-papers/submit",
            params={"subject_id": DEFAULT_SUBJECT_ID},
            json={
                "paper_id": paper["id"],
                "request_id": str(uuid.uuid4()),
                "expected_revision": rev,
            },
        )
        self.assertEqual(sub_resp.status_code, 200, sub_resp.text)
        done_paper = sub_resp.json()
        self.assertEqual(done_paper["phase"], "done")
        self.assertTrue(all(item["result"]["correct"] for item in done_paper["items"]))
        self.assertEqual(done_paper["items"][0]["html"], revised_html)
        self.assertTrue(done_paper["items"][0]["explanation_html"])
        terminal_open = client2.post("/api/page-edits/open", params=paper_scope, json=back_request)
        self.assertEqual(terminal_open.status_code, 409, terminal_open.text)
        terminal_save = client2.put("/api/page-edits/current", params=paper_scope, json={
            key: reopened.json()[key] for key in ("token", "revision", "fields")
        })
        self.assertEqual(terminal_save.status_code, 409, terminal_save.text)

    def test_manual_pause_exact_unlock_and_security_boundaries(self) -> None:
        data_dir, clock, port = self._make_env()
        _rt, client = self._make_client(data_dir, clock, port)

        # Manual pause + exact pause_event_id unlock
        s = client.get("/api/state", params={"topic_id": JP01}).json()
        paused = client.post(
            "/api/pause",
            params={"topic_id": JP01},
            json={
                "request_id": str(uuid.uuid4()),
                "expected_revision": s["revision"],
                "attempt_id": s["attempt_id"],
                "step_id": s["active_step_id"],
                "reason": "manual test pause",
            },
        )
        self.assertEqual(paused.status_code, 200, paused.text)
        paused_json = paused.json()
        self.assertIsNotNone(paused_json.get("pause"))

        pauses = client.get("/api/pauses").json()
        self.assertEqual(pauses["total"], 1)
        event_id = pauses["items"][0]["pause_event_id"]

        wrong_unlock = client.post(
            "/api/pauses/unlock",
            json={"topic_id": JP01, "module_id": "atomic", "pause_event_id": "wrong-event-id"},
        )
        self.assertEqual(wrong_unlock.status_code, 409)
        self.assertEqual(wrong_unlock.json()["detail"]["code"], "unlock_mismatch")

        ok_unlock = client.post(
            "/api/pauses/unlock",
            json={"topic_id": JP01, "module_id": "atomic", "pause_event_id": event_id},
        )
        self.assertEqual(ok_unlock.status_code, 200, ok_unlock.text)
        self.assertTrue(ok_unlock.json()["unlocked"])
        self.assertEqual(client.get("/api/pauses").json()["total"], 0)

        # Security headers & CSP
        root = client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertIn("script-src 'self'", root.headers["content-security-policy"])
        self.assertEqual(root.headers["x-content-type-options"], "nosniff")
        self.assertEqual(root.headers["referrer-policy"], "no-referrer")
        self.assertEqual(root.headers["x-frame-options"], "DENY")
        self.assertEqual(root.headers["cache-control"], "no-store")

        # Bad Host & Origin rejections
        self.assertEqual(
            client.get("/api/health", headers={"Host": f"evil.example:{port}"}).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                "/api/continue",
                params={"topic_id": JP01},
                headers={"Origin": "https://evil.example"},
                json={"request_id": "r1", "expected_revision": 0},
            ).status_code,
            403,
        )

        # Path traversal & disallowed extension rejections
        self.assertEqual(client.get("/../packages/course_graph.json").status_code, 404)
        self.assertEqual(client.get("/..%2Fbackend/api.py").status_code, 404)
        self.assertEqual(client.get("/vendor/katex/katex.js").status_code, 200)
        self.assertEqual(client.get("/vendor/mermaid/index.js").status_code, 200)

        # Body size limit (MAX_REQUEST_BODY_BYTES = 65536)
        oversized = '{"request_id":"r1","expected_revision":0,"answer":"' + ("a" * (MAX_REQUEST_BODY_BYTES + 256)) + '"}'
        too_big = client.post(
            "/api/submit",
            params={"topic_id": JP01},
            headers={"Content-Type": "application/json"},
            content=oversized,
        )
        self.assertEqual(too_big.status_code, 413)
        self.assertEqual(too_big.json()["detail"]["code"], "body_too_large")

    def test_subprocess_live_server_smoke_and_clean_shutdown(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="jp_grammar_live_")
        self.addCleanup(tmp.cleanup)
        data_dir = Path(tmp.name) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        port = _pick_free_loopback_port()

        popen_kwargs: dict = {
            "cwd": str(REPO_ROOT),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "tools.japanese_grammar.backend.main",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--data-dir",
                str(data_dir),
            ],
            **popen_kwargs,
        )

        def _cleanup_proc() -> None:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            if proc.stdout is not None:
                proc.stdout.close()

        self.addCleanup(_cleanup_proc)

        marker_path = data_dir / "server.json"
        health_url = f"http://127.0.0.1:{port}/api/health"
        health_payload = None

        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                self.fail(f"Live server exited early ({proc.returncode}): {out}")
            if marker_path.is_file():
                try:
                    with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                        if resp.status == 200:
                            health_payload = json.loads(resp.read().decode("utf-8"))
                            break
                except (urllib.error.URLError, TimeoutError, ValueError):
                    pass
            time.sleep(0.1)

        self.assertIsNotNone(health_payload, "Timed out waiting for /api/health == 200")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        self.assertEqual(marker["service_id"], SERVER_SERVICE_ID)
        self.assertEqual(marker["pid"], health_payload["pid"])
        self.assertIsInstance(marker["pid"], int)
        self.assertGreater(marker["pid"], 0)
        self.assertEqual(marker["port"], port)
        self.assertEqual(marker["instance_id"], health_payload["instance_id"])
        self.assertEqual(marker["process_started_at"], health_payload["process_started_at"])
        self.assertTrue(marker["process_started_at"])

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2.0) as root_resp:
            self.assertEqual(root_resp.status, 200)
            self.assertIn("text/html", root_resp.headers.get("Content-Type", ""))
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/app.js", timeout=2.0) as js_resp:
            self.assertEqual(js_resp.status, 200)
            self.assertIn("javascript", js_resp.headers.get("Content-Type", ""))

        # Trigger clean shutdown & verify server.json is removed on exit
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        rc = proc.wait(timeout=10)
        self.assertIsNotNone(rc)
        self.assertFalse(
            marker_path.exists(),
            f"server.json remained after clean shutdown (rc={rc})",
        )

    def test_prerequisite_due_review_blocker_chunk_gap_and_next_due_at_consistency(self) -> None:
        data_dir, clock, port = self._make_env()
        _rt, client = self._make_client(data_dir, clock, port)
        try:
            self._complete_jp01(client, clock, test_wrong_and_self_rating=False)

            # Start jp02 and master at least its first point so jp02 holds its own FSRS schedule
            s2 = client.get("/api/state", params={"topic_id": JP02}).json()
            self.assertTrue(s2["dependency_ready"])
            all_cards = _all_flashcards()
            for _ in range(30):
                if s2.get("learned_count", 0) >= 1:
                    break
                phase = s2.get("phase")
                if phase in ("introduction", "chunk"):
                    resp = client.post(
                        "/api/continue",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                        },
                    )
                    self.assertEqual(resp.status_code, 200, resp.text)
                    s2 = resp.json()
                elif phase == "answer":
                    fc = all_cards[s2["current"]["card_id"]]
                    resp = client.post(
                        "/api/submit",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                            "answer": demo_answer(fc),
                        },
                    )
                    self.assertEqual(resp.status_code, 200, resp.text)
                    sub = resp.json()
                    self.assertEqual(sub["status"], "judged")
                    self.assertTrue(sub["correct"])
                    s2 = sub["state"]
                elif phase in ("feedback", "waiting"):
                    if s2.get("next_available_at"):
                        clock.advance(seconds=180)
                    s2 = client.post(
                        "/api/continue",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                        },
                    ).json()
                else:
                    self.fail(f"Unexpected jp02 state phase={phase!r}: {s2}")

            self.assertGreaterEqual(s2["learned_count"], 1)

            # Advance clock so BOTH jp01 (due earlier) and jp02 have past due_at timestamps
            clock.advance(hours=7)
            now_dt = clock()

            jp01_blocked_view = client.get("/api/state", params={"topic_id": JP01}).json()
            self.assertEqual(jp01_blocked_view["status"], "completed")
            self.assertGreaterEqual(jp01_blocked_view["review_summary"]["due_count"], 1)

            jp02_blocked_view = client.get("/api/state", params={"topic_id": JP02}).json()
            self.assertFalse(jp02_blocked_view["dependency_ready"])
            self.assertTrue(jp02_blocked_view["dependency_blocked"])
            blocker = jp02_blocked_view["blocking_topics"][0]
            self.assertEqual(blocker["topic_id"], JP01)
            self.assertTrue(blocker["completed"])
            self.assertFalse(blocker["paused"])
            self.assertGreaterEqual(blocker["due_count"], 1)
            self.assertEqual(blocker["reason"], "due_reviews")

            # Locked jp02's past due_at MUST NOT leak into top-level atomic/reviews or dashboard next_due_at
            atomic_rev = client.get("/api/atomic/reviews", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
            if atomic_rev["next_due_at"] is not None:
                self.assertGreater(datetime.fromisoformat(atomic_rev["next_due_at"]), now_dt)
            jp02_rev_item = next(i for i in atomic_rev["items"] if i["topic_id"] == JP02)
            self.assertFalse(jp02_rev_item["dependency_ready"])
            self.assertGreaterEqual(jp02_rev_item["due_count"], 1)

            dash = client.get("/api/dashboard", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
            if dash["next_review_due_at"] is not None:
                self.assertGreater(datetime.fromisoformat(dash["next_review_due_at"]), now_dt)

            # Simulate the exact chunk-spacing cooldown deadlock edge case:
            # only p-jp01-wh-ga remains past due in jp01, while same chunk chunk-jp01-wh-info-flow
            # was just seen within GAP_SECONDS (180s), making inbox return 0 jp01 items.
            with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
                row = con.execute(
                    "SELECT body FROM topics WHERE learner=? AND topic=?",
                    (LOCAL_LEARNER_ID, JP01),
                ).fetchone()
                body = json.loads(row[0])
                future_iso = (now_dt + timedelta(minutes=15)).isoformat()
                for pid, pstate in body["atomic"]["points"].items():
                    if pid != "p-jp01-wh-ga":
                        pstate["due_at"] = future_iso
                body["atomic"]["chunk_last_seen"]["chunk-jp01-wh-info-flow"] = now_dt.isoformat()
                con.execute(
                    "UPDATE topics SET body=? WHERE learner=? AND topic=?",
                    (json.dumps(body, ensure_ascii=False), LOCAL_LEARNER_ID, JP01),
                )
                con.commit()

            # During the 180s chunk cooldown on chunk-jp01-wh-info-flow, jp01 has 0 servable reviews;
            # dependency_policy MUST agree rather than deadlocking jp02 against an empty inbox.
            inbox_during_gap = client.get("/api/review-papers/inbox", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
            self.assertGreater(datetime.fromisoformat(inbox_during_gap["next_due_at"]), now_dt)
            atomic_during_gap = client.get("/api/atomic/reviews", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
            if atomic_during_gap["next_due_at"] is not None:
                self.assertGreater(datetime.fromisoformat(atomic_during_gap["next_due_at"]), now_dt)
            self.assertTrue(client.get("/api/state", params={"topic_id": JP02}).json()["dependency_ready"])

            # Once the 180s chunk cooldown expires, jp01's overdue p-jp01-wh-ga becomes servable
            # in BOTH inbox AND dependency_policy synchronously.
            clock.advance(seconds=181)
            inbox_after_gap = client.get("/api/review-papers/inbox", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
            self.assertGreaterEqual(inbox_after_gap["due_count"], 1)
            jp02_after_gap = client.get("/api/state", params={"topic_id": JP02}).json()
            self.assertFalse(jp02_after_gap["dependency_ready"])
            self.assertEqual(jp02_after_gap["blocking_topics"][0]["reason"], "due_reviews")
        finally:
            client.__exit__(None, None, None)


class JapaneseGrammarUpgradeAndAiTests(unittest.TestCase):
    """Coverage for non-spoiler cards, lossless topic upgrades, and AI tutor endpoints."""

    def test_curriculum_spoilers_removed_and_ui_hooks_present(self) -> None:
        forbidden_prompt_spoilers = (
            "は / が",
            "が / を",
            "（ている）",
            "（ません）",
            "（たい / たくない）",
            "（くなかった）",
            "（ではなかった / じゃなかった）",
            "を→に",
        )
        for tid in ALL_TOPICS:
            topic = _load_topic(tid)
            for fc in topic.get("flashcards", []):
                question_text = f"{fc.get('question', '')}\n{fc.get('html', '')}"
                for tok in forbidden_prompt_spoilers:
                    self.assertNotIn(
                        tok,
                        question_text,
                        f"{tid}/{fc['id']} leaked spoiler token {tok!r}",
                    )
                blanks = (fc.get("interaction") or {}).get("blanks") or []
                zh_match = re.search(r'<p class="jp-zh">(.*?)</p>', fc.get("html", ""), re.S)
                zh_text = zh_match.group(1) if zh_match else ""
                for b in blanks:
                    for ans in b.get("accepted") or []:
                        ans_s = str(ans).strip()
                        if ans_s:
                            self.assertNotIn(
                                f"「{ans_s}」",
                                str(fc.get("question", "")),
                                f"{tid}/{fc['id']} quoted its own blank answer {ans_s!r}",
                            )
                    if "2222" in fc["id"]:
                        for bad_gloss in ("五段动词", "一段动词", "知道（知る", "要る属于"):
                            self.assertNotIn(
                                bad_gloss,
                                zh_text,
                                f"{tid}/{fc['id']} leaked forbidden gloss {bad_gloss!r} in .jp-zh={zh_text!r}",
                            )
                        neutral_choice_zh = "一段 / 五段" in zh_text or "着る / 寝る / 知る / 出る" in zh_text
                        for ans in b.get("answers") or []:
                            ans_s = str(ans).strip()
                            if ans_s:
                                self.assertNotIn(
                                    f"「{ans_s}」",
                                    str(fc.get("question", "")),
                                    f"{tid}/{fc['id']} quoted its own blank answer {ans_s!r}",
                                )
                                if len(ans_s) >= 2 and not neutral_choice_zh:
                                    self.assertNotIn(
                                        ans_s,
                                        zh_text,
                                        f"{tid}/{fc['id']} leaked answer {ans_s!r} in .jp-zh={zh_text!r}",
                                    )

        index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="aiSettingsBtn"', index_html)
        self.assertIn('id="aiDrawerToggleBtn"', index_html)
        self.assertIn('id="aiDrawerHost"', index_html)

        app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("splitIntroductionSteps", app_js)
        self.assertIn("neutralPlaceholder", app_js)
        self.assertIn("revealTitle", app_js)
        self.assertIn("createAiAssistant", app_js)
        self.assertNotIn("busy: appState.busy", app_js)

        qw_js = (WEB_DIR / "question-widget.js").read_text(encoding="utf-8")
        self.assertIn("neutralPlaceholder", qw_js)
        self.assertIn("填入日语...", qw_js)

        mc_js = (WEB_DIR / "memory-chunk.js").read_text(encoding="utf-8")
        self.assertIn("revealTitle", mc_js)
        self.assertIn("相关讲义参考", mc_js)

        # Verify every relative ES module import inside web/ resolves to an existing file.
        import_re = re.compile(r"""from\s+['"](\.[^'"]+)['"]""")
        for js_file in WEB_DIR.glob("*.js"):
            src = js_file.read_text(encoding="utf-8")
            for rel in import_re.findall(src):
                target = (js_file.parent / rel).resolve()
                self.assertTrue(
                    target.is_file(),
                    f"Broken ES module import in {js_file.name}: {rel!r} -> {target} missing",
                )

    def _drive_topic_cards(
        self,
        client: TestClient,
        clock: MutableClock,
        topic_id: str,
        fc_map: dict[str, dict],
        *,
        max_correct_cards: int | None = None,
    ) -> dict:
        s = client.get("/api/state", params={"topic_id": topic_id}).json()
        answered = 0
        for _ in range(300):
            if s.get("status") == "completed" or s.get("phase") == "completed":
                return s
            if max_correct_cards is not None and answered >= max_correct_cards:
                return s
            phase = s.get("phase")
            if phase in {"introduction", "chunk"}:
                actions = s.get("actions") or []
                if phase == "introduction" and "continue" not in actions and not s.get("started_at"):
                    s = client.post(
                        "/api/choose",
                        params={"topic_id": topic_id},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s["revision"],
                            "mode": "learn",
                        },
                    ).json()
                else:
                    s = client.post(
                        "/api/continue",
                        params={"topic_id": topic_id},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s["revision"],
                            "attempt_id": s["attempt_id"],
                            "step_id": s["active_step_id"],
                        },
                    ).json()
                continue
            if phase == "answer":
                cid = s["current"]["card_id"]
                resp = client.post(
                    "/api/submit",
                    params={"topic_id": topic_id},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                        "answer": demo_answer(fc_map[cid]),
                    },
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                answered += 1
                s = resp.json()["state"]
                continue
            if phase == "feedback":
                s = client.post(
                    "/api/continue",
                    params={"topic_id": topic_id},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                    },
                ).json()
                continue
            if phase == "waiting":
                clock.advance(minutes=15)
                s = client.post(
                    "/api/continue",
                    params={"topic_id": topic_id},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                    },
                ).json()
                continue
            self.fail(f"Unexpected state in _drive_topic_cards({topic_id}): {s}")
        self.fail(f"Exceeded loop cap while driving {topic_id}")

    def test_compatible_topic_revision_migration_preserves_progress_and_guards_inflight(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="jp_grammar_migrate_")
        self.addCleanup(tmp.cleanup)
        root_tmp = Path(tmp.name)
        old_pkg_dir = root_tmp / "old_packages"
        shutil.copytree(PACKAGES_DIR, old_pkg_dir)

        legacy_version = "jp-grammar-legacy-v1"
        legacy_cv = "legacycv1"
        for tid in (JP01, JP02):
            tp = old_pkg_dir / tid / "topic.json"
            data = json.loads(tp.read_text(encoding="utf-8"))
            data["version"] = legacy_version
            data["content_version"] = legacy_cv
            if tid == JP02:
                data["flashcards"][0]["question"] = "[LEGACY PROMPT] " + str(data["flashcards"][0]["question"])
            tp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        data_dir = root_tmp / "data"
        clock = MutableClock()
        port = _pick_free_loopback_port()

        rt_old = LocalRuntime(
            packages_dir=old_pkg_dir,
            data_dir=data_dir,
            web_dir=WEB_DIR,
            host="127.0.0.1",
            port=port,
            clock=clock,
        )
        jp01_fc = {fc["id"]: fc for fc in json.loads((old_pkg_dir / JP01 / "topic.json").read_text(encoding="utf-8"))["flashcards"]}
        jp02_fc = {fc["id"]: fc for fc in json.loads((old_pkg_dir / JP02 / "topic.json").read_text(encoding="utf-8"))["flashcards"]}
        with TestClient(create_app(rt_old), base_url=f"http://127.0.0.1:{port}") as client_old:
            s1 = self._drive_topic_cards(client_old, clock, JP01, jp01_fc)
            self.assertEqual(s1.get("status"), "completed")
            s2 = self._drive_topic_cards(client_old, clock, JP02, jp02_fc, max_correct_cards=2)
            self.assertGreaterEqual(len(s2.get("history") or []), 2)

        with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
            old_row_jp01 = con.execute("SELECT version, body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP01)).fetchone()
            old_row_jp02 = con.execute("SELECT version, body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP02)).fetchone()
            old_rp_count = con.execute("SELECT COUNT(*) FROM review_points WHERE version=?", (legacy_version,)).fetchone()[0]
        self.assertEqual(old_row_jp01[0], legacy_version)
        self.assertEqual(old_row_jp02[0], legacy_version)
        self.assertGreaterEqual(old_rp_count, 9)
        old_jp01_body = json.loads(old_row_jp01[1])
        old_jp02_body = json.loads(old_row_jp02[1])
        old_jp02_mastered = {k for k, v in old_jp02_body["atomic"]["points"].items() if v.get("mastered")}
        self.assertGreaterEqual(len(old_jp02_mastered), 2)

        # Upgrade runtime to rebuilt PACKAGES_DIR -> lossless migration runs automatically.
        rt_new = LocalRuntime(
            packages_dir=PACKAGES_DIR,
            data_dir=data_dir,
            web_dir=WEB_DIR,
            host="127.0.0.1",
            port=port,
            clock=clock,
        )
        backups = list((data_dir / "backups").glob("learning-pre-migrate-*.sqlite3"))
        self.assertTrue(backups, "Expected automatic pre-migration SQLite backup")

        new_jp01 = _load_topic(JP01)
        new_jp02 = _load_topic(JP02)
        with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
            new_row_jp01 = con.execute("SELECT version, body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP01)).fetchone()
            new_row_jp02 = con.execute("SELECT version, body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP02)).fetchone()
            migrated_rp_jp01 = con.execute("SELECT COUNT(*) FROM review_points WHERE container=? AND version=?", (JP01, new_jp01["version"])).fetchone()[0]
            migrated_rp_jp02 = con.execute("SELECT COUNT(*) FROM review_points WHERE container=? AND version=?", (JP02, new_jp02["version"])).fetchone()[0]
            leftover_old_rp = con.execute("SELECT COUNT(*) FROM review_points WHERE version=?", (legacy_version,)).fetchone()[0]

        self.assertEqual(new_row_jp01[0], new_jp01["version"])
        self.assertEqual(new_row_jp02[0], new_jp02["version"])
        self.assertEqual(migrated_rp_jp01, 9)
        self.assertEqual(migrated_rp_jp02, 2)
        self.assertEqual(migrated_rp_jp01 + migrated_rp_jp02, old_rp_count)
        self.assertEqual(leftover_old_rp, 0)

        new_jp01_body = json.loads(new_row_jp01[1])
        self.assertEqual(new_jp01_body.get("content_version"), new_jp01["content_version"])
        expected_jp01_read_cv = (
            new_jp01["content_version"]
            if old_jp01_body.get("read_content_version") == legacy_cv
            else old_jp01_body.get("read_content_version")
        )
        self.assertEqual(new_jp01_body.get("read_content_version"), expected_jp01_read_cv)

        new_jp02_body = json.loads(new_row_jp02[1])
        self.assertEqual(new_jp02_body.get("content_version"), new_jp02["content_version"])
        expected_jp02_read_cv = (
            new_jp02["content_version"]
            if old_jp02_body.get("read_content_version") == legacy_cv
            else old_jp02_body.get("read_content_version")
        )
        self.assertEqual(new_jp02_body.get("read_content_version"), expected_jp02_read_cv)
        self.assertEqual(new_jp02_body.get("sections_finished"), old_jp02_body.get("sections_finished"))
        self.assertEqual(new_jp02_body.get("read_introductions"), old_jp02_body.get("read_introductions"))
        new_jp02_mastered = {k for k, v in new_jp02_body["atomic"]["points"].items() if v.get("mastered")}
        self.assertEqual(new_jp02_mastered, old_jp02_mastered)
        for item in new_jp02_body["atomic"]["history"]:
            self.assertIsInstance(item.get("snapshot"), dict)
            self.assertEqual(item.get("snapshot_version"), legacy_version)

        with TestClient(create_app(rt_new), base_url=f"http://127.0.0.1:{port}") as client_new:
            resumed1 = client_new.get("/api/state", params={"topic_id": JP01}).json()
            self.assertEqual(resumed1.get("status"), "completed")
            resumed2 = client_new.get("/api/state", params={"topic_id": JP02}).json()
            self.assertGreaterEqual(resumed2.get("learned_count", 0), len(old_jp02_mastered))
            self.assertEqual(len(resumed2.get("history") or []), len(old_jp02_body["atomic"]["history"]))

        # Guard: active pending submission blocks silent migration.
        guard_data = root_tmp / "guard_data"
        rt_guard_old = LocalRuntime(
            packages_dir=old_pkg_dir,
            data_dir=guard_data,
            web_dir=WEB_DIR,
            host="127.0.0.1",
            port=port,
            clock=clock,
        )
        with TestClient(create_app(rt_guard_old), base_url=f"http://127.0.0.1:{port}") as cg:
            self._drive_topic_cards(cg, clock, JP01, jp01_fc, max_correct_cards=1)
        with closing(sqlite3.connect(str(guard_data / "learning.sqlite3"))) as con:
            con.execute(
                """INSERT INTO submissions
                (id, learner, topic, attempt, step, question, answer, fingerprint, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "sub-inflight",
                    LOCAL_LEARNER_ID,
                    JP01,
                    "att-1",
                    "step-1",
                    "q-1",
                    "{}",
                    "fp-1",
                    "pending",
                    "2026-11-14T00:00:00+00:00",
                    "2026-11-14T00:00:00+00:00",
                ),
            )
            con.commit()
        with self.assertRaises(DomainError) as err_ctx:
            LocalRuntime(
                packages_dir=PACKAGES_DIR,
                data_dir=guard_data,
                web_dir=WEB_DIR,
                host="127.0.0.1",
                port=port,
                clock=clock,
            )
        self.assertEqual(err_ctx.exception.code, "incompatible_topic_revision")

    def test_ai_config_tutor_socratic_and_sse_streaming(self) -> None:
        captured: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = None
            if request.content:
                body = json.loads(request.content.decode("utf-8"))
            captured.append(
                {
                    "method": request.method,
                    "url": str(request.url),
                    "auth": request.headers.get("authorization"),
                    "json": body,
                }
            )
            if request.url.path.endswith("/models"):
                if "fallback-404" in str(request.url):
                    return httpx.Response(404, json={"error": {"message": "not found"}})
                if request.headers.get("authorization") == "Bearer sk-bad-token":
                    return httpx.Response(401, json={"error": {"message": "invalid api key sk-bad-token"}})
                return httpx.Response(200, json={"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]})
            if request.url.path.endswith("/chat/completions"):
                if body and "temperature" in body and body["temperature"] != 1:
                    return httpx.Response(
                        400,
                        json={"error": {"message": "invalid temperature: only 1 is allowed for this model"}},
                    )
                if body and body.get("stream"):
                    sse = (
                        'data: {"choices":[{"delta":{"content":"这里应该用"}}]}\n\n'
                        'data: {"choices":[{"delta":{"content":"主題助詞。"}}]}\n\n'
                        'data: [DONE]\n\n'
                    ).encode("utf-8")
                    return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=sse)
                return httpx.Response(
                    200,
                    json={
                        "model": body.get("model", "gpt-4o-mini"),
                        "choices": [{"message": {"content": "请先判断句首名词是不是全句要说明的主题。"}}],
                    },
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        tmp = tempfile.TemporaryDirectory(prefix="jp_grammar_ai_")
        self.addCleanup(tmp.cleanup)
        data_dir = Path(tmp.name) / "data"
        clock = MutableClock()
        port = _pick_free_loopback_port()

        env_vars = {
            "OPENAI_API_KEY": "sk-env-secret-1234",
            "OPENAI_BASE_URL": "https://api.env.example/v1",
            "OPENAI_MODEL": "env-test-model",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            runtime = LocalRuntime(
                packages_dir=PACKAGES_DIR,
                data_dir=data_dir,
                web_dir=WEB_DIR,
                host="127.0.0.1",
                port=port,
                clock=clock,
                ai_transport=transport,
            )
            with TestClient(create_app(runtime), base_url=f"http://127.0.0.1:{port}") as client:
                # 1. Config falls back cleanly to env with key masking
                cfg0 = client.get("/api/ai/config")
                self.assertEqual(cfg0.status_code, 200)
                c0 = cfg0.json()
                self.assertTrue(c0["configured"])
                self.assertEqual(c0["sources"]["api_key"], "env")
                self.assertEqual(c0["model"], "env-test-model")
                self.assertNotIn("sk-env-secret-1234", cfg0.text)

                # 2. Validation rejects invalid schemes / embedded credentials while allowing loopback HTTP & HTTPS
                bad_scheme = client.put("/api/ai/config", json={"base_url": "ftp://remote.example.com/v1"})
                self.assertEqual(bad_scheme.status_code, 422)
                bad_creds = client.put("/api/ai/config", json={"base_url": "https://user:pass@remote.example.com/v1"})
                self.assertEqual(bad_creds.status_code, 422)
                local_http = client.put("/api/ai/config", json={"base_url": "http://127.0.0.1:11434/v1"})
                self.assertEqual(local_http.status_code, 200)

                # 3. Local config overrides env, masks stored secret, and resets back cleanly
                upd = client.put(
                    "/api/ai/config",
                    json={
                        "base_url": "https://api.local.example/v1",
                        "api_key": "sk-local-secret-9876",
                        "model": "gpt-4o-mini",
                        "stream": False,
                    },
                )
                self.assertEqual(upd.status_code, 200, upd.text)
                uj = upd.json()
                self.assertEqual(uj["sources"]["api_key"], "local")
                self.assertEqual(uj["model"], "gpt-4o-mini")
                self.assertFalse(uj["stream"])
                self.assertNotIn("sk-local-secret-9876", upd.text)
                self.assertTrue((data_dir / "ai_config.json").is_file())

                # 4. Connection probe (/models, 404->chat fallback, and 401 sanitization)
                t_ok = client.post("/api/ai/test", json={})
                self.assertEqual(t_ok.status_code, 200, t_ok.text)
                self.assertEqual(t_ok.json()["probe"], "models")
                self.assertEqual(t_ok.json()["available_models_count"], 2)

                captured.clear()
                t_fb = client.post("/api/ai/test", json={"base_url": "https://fallback-404.example/v1"})
                self.assertEqual(t_fb.status_code, 200, t_fb.text)
                self.assertEqual(t_fb.json()["probe"], "chat_completions")
                self.assertNotIn("temperature", captured[-1]["json"])

                t_401 = client.post("/api/ai/test", json={"api_key": "sk-bad-token"})
                self.assertEqual(t_401.status_code, 502)
                self.assertEqual(t_401.json()["detail"]["code"], "ai_auth_failed")

                # 5. Unsubmitted active card enforces Socratic non-spoiler system prompt
                s = client.get("/api/state", params={"topic_id": JP01}).json()
                while s.get("phase") != "answer":
                    actions = s.get("actions") or []
                    if s.get("phase") == "introduction" and "continue" not in actions and not s.get("started_at"):
                        s = client.post(
                            "/api/choose",
                            params={"topic_id": JP01},
                            json={"request_id": str(uuid.uuid4()), "expected_revision": s["revision"], "mode": "learn"},
                        ).json()
                    else:
                        s = client.post(
                            "/api/continue",
                            params={"topic_id": JP01},
                            json={
                                "request_id": str(uuid.uuid4()),
                                "expected_revision": s["revision"],
                                "attempt_id": s["attempt_id"],
                                "step_id": s["active_step_id"],
                            },
                        ).json()
                active_card_id = s["current"]["card_id"]
                fc = next(c for c in _load_topic(JP01)["flashcards"] if c["id"] == active_card_id)

                captured.clear()
                chat_sync = client.post(
                    "/api/ai/chat",
                    json={
                        "messages": [{"role": "user", "content": "这里该填什么助词？"}],
                        "attach_context": True,
                        "context": {"topic_id": JP01, "view": "answer", "card_id": active_card_id},
                        "stream": False,
                    },
                )
                self.assertEqual(chat_sync.status_code, 200, chat_sync.text)
                self.assertEqual(len(captured), 1)
                self.assertNotIn("temperature", captured[-1]["json"])
                cj = chat_sync.json()
                self.assertTrue(cj["heuristic_mode"])
                self.assertEqual(cj["effective_mode"], "quiz_unsubmitted")
                self.assertNotIn("sk-local-secret-9876", chat_sync.text)
                sys_prompt_unsubmitted = captured[-1]["json"]["messages"][0]["content"]
                self.assertIn("未交卷启发式助教模式", sys_prompt_unsubmitted)
                self.assertIn("严格禁止", sys_prompt_unsubmitted)

                # 6. Submitted card switches to feedback/full-explanation & streams SSE
                sub = client.post(
                    "/api/submit",
                    params={"topic_id": JP01},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s["attempt_id"],
                        "step_id": s["active_step_id"],
                        "answer": demo_answer(fc),
                    },
                )
                self.assertEqual(sub.status_code, 200)

                captured.clear()
                chat_sse = client.post(
                    "/api/ai/chat",
                    json={
                        "messages": [{"role": "user", "content": "请解释刚才这题的原理"}],
                        "attach_context": True,
                        "context": {"topic_id": JP01, "view": "feedback", "card_id": active_card_id},
                        "stream": True,
                    },
                )
                self.assertEqual(chat_sse.status_code, 200)
                self.assertEqual(len(captured), 1)
                self.assertNotIn("temperature", captured[-1]["json"])
                self.assertIn("text/event-stream", chat_sse.headers.get("content-type", ""))
                sse_body = chat_sse.text
                self.assertIn('"meta":', sse_body)
                self.assertIn('"heuristic_mode": false', sse_body.lower())
                self.assertIn("这里应该用", sse_body)
                self.assertIn('"done": true', sse_body)
                sys_prompt_submitted = captured[-1]["json"]["messages"][0]["content"]
                self.assertNotIn("未交卷启发式助教模式", sys_prompt_submitted)

                # 7. Explicit unsupported temperature falls back automatically by stripping temperature and retrying
                captured.clear()
                sync_retry = complete_chat(
                    data_dir,
                    system_prompt="你是日语助教。",
                    messages=[{"role": "user", "content": "测试 temperature 回退"}],
                    temperature=0.3,
                    transport=transport,
                )
                self.assertIn("主题", sync_retry["reply"])
                self.assertEqual(len(captured), 2)
                self.assertEqual(captured[0]["json"].get("temperature"), 0.3)
                self.assertNotIn("temperature", captured[1]["json"])

                captured.clear()
                stream_chunks = b"".join(
                    open_chat_stream(
                        data_dir,
                        system_prompt="你是日语助教。",
                        messages=[{"role": "user", "content": "流式测试 temperature 回退"}],
                        temperature=0.3,
                        transport=transport,
                    )
                ).decode("utf-8")
                self.assertIn("主題助詞", stream_chunks)
                self.assertEqual(len(captured), 2)
                self.assertEqual(captured[0]["json"].get("temperature"), 0.3)
                self.assertNotIn("temperature", captured[1]["json"])

                # 8. Reset back to environment defaults
                rst = client.put("/api/ai/config", json={"reset_to_env": True})
                self.assertEqual(rst.status_code, 200)
                self.assertEqual(rst.json()["sources"]["api_key"], "env")
                self.assertEqual(rst.json()["model"], "env-test-model")

    def test_romaji_unit_and_curriculum_roundtrip(self) -> None:
        from tools.japanese_grammar.backend.judge import evaluate_question_offline
        from tools.japanese_grammar.backend.romaji import (
            katakana_to_hiragana,
            resolve_blank_answer_with_romaji,
            romaji_to_hiragana_candidates,
        )

        # Direct & particle-phonetic cases
        self.assertEqual(resolve_blank_answer_with_romaji(["の"], "no"), "の")
        self.assertEqual(resolve_blank_answer_with_romaji(["の"], "NO"), "の")
        self.assertEqual(resolve_blank_answer_with_romaji(["の"], "ｎｏ"), "の")
        self.assertEqual(resolve_blank_answer_with_romaji(["は"], "wa"), "は")
        self.assertEqual(resolve_blank_answer_with_romaji(["は"], "ha"), "は")
        self.assertEqual(resolve_blank_answer_with_romaji(["を"], "o"), "を")
        self.assertEqual(resolve_blank_answer_with_romaji(["を"], "wo"), "を")
        self.assertEqual(resolve_blank_answer_with_romaji(["へ"], "e"), "へ")
        self.assertEqual(resolve_blank_answer_with_romaji(["へ"], "he"), "へ")
        self.assertEqual(resolve_blank_answer_with_romaji(["では"], "dewa"), "では")
        self.assertEqual(resolve_blank_answer_with_romaji(["では"], "deha"), "では")
        self.assertEqual(resolve_blank_answer_with_romaji(["ホテルじゃない", "ホテルではない"], "hoteru janai"), "ホテルじゃない")
        self.assertEqual(resolve_blank_answer_with_romaji(["ホテルじゃない", "ホテルではない"], "ほてる じゃない"), "ホテルじゃない")
        self.assertEqual(resolve_blank_answer_with_romaji(["勉強する", "べんきょうする"], "benkyō suru"), "べんきょうする")
        self.assertEqual(resolve_blank_answer_with_romaji(["食べなかった"], "食べnakatta"), "食べなかった")
        self.assertIn("べんきょう", romaji_to_hiragana_candidates("benkyou"))
        self.assertIn("こっち", romaji_to_hiragana_candidates("kocchi"))

        # Strict negatives: wrong particle or misspelled non-particle consonant must not pass
        self.assertEqual(resolve_blank_answer_with_romaji(["が"], "wa"), "wa")
        self.assertEqual(resolve_blank_answer_with_romaji(["かわない"], "kahanai"), "kahanai")
        self.assertEqual(resolve_blank_answer_with_romaji(["の"], "qzx"), "qzx")

        # Programmatic Hepburn romaji round-trip across every kana blank in all 6 topics
        digraphs = {
            "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
            "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
            "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
            "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
            "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
            "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
            "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
            "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
            "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
            "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
            "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
            "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo",
            "てぃ": "ti", "でぃ": "di",
        }
        monographs = {
            "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
            "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
            "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
            "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
            "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
            "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
            "だ": "da", "ぢ": "ji", "づ": "dzu", "で": "de", "ど": "do",
            "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
            "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
            "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
            "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
            "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
            "や": "ya", "ゆ": "yu", "よ": "yo",
            "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
            "わ": "wa", "を": "wo", "ん": "n",
        }

        def to_romaji(jp_text: str) -> str:
            hira = katakana_to_hiragana(re.sub(r"\s+", "", jp_text))
            out: list[str] = []
            idx = 0
            while idx < len(hira):
                ch = hira[idx]
                if ch == "っ":
                    nxt = hira[idx + 1 : idx + 3]
                    nxt_rom = digraphs.get(nxt) or monographs.get(hira[idx + 1 : idx + 2], "")
                    if nxt_rom.startswith("ch"):
                        out.append("t")
                    elif nxt_rom:
                        out.append(nxt_rom[0])
                    idx += 1
                    continue
                if ch == "ん":
                    nxt = hira[idx + 1 : idx + 2]
                    if nxt and nxt in "あいうえおやゆよ":
                        out.append("n'")
                    elif idx + 1 == len(hira):
                        out.append("nn")
                    else:
                        out.append("n")
                    idx += 1
                    continue
                if idx + 2 <= len(hira) and hira[idx : idx + 2] in digraphs:
                    out.append(digraphs[hira[idx : idx + 2]])
                    idx += 2
                    continue
                if ch in monographs:
                    out.append(monographs[ch])
                    idx += 1
                    continue
                out.append(ch)
                idx += 1
            return "".join(out)

        from graspmemoedu.judging import judge_answer

        all_cards = _all_flashcards()
        judge = JapaneseGrammarJudge()
        checked_cards = 0
        checked_blanks = 0
        for card in all_cards.values():
            interaction = card.get("interaction") or {}
            blanks = interaction.get("blanks") or []
            if interaction.get("type") != "fill_blank" or not blanks:
                continue
            checked_cards += 1
            romaji_blanks: dict[str, str] = {}
            for b in blanks:
                sample = to_romaji(b["answers"][0])
                romaji_blanks[b["id"]] = sample
                checked_blanks += 1
            payload = json.dumps(romaji_blanks, ensure_ascii=False)
            shared_ok, shared_reason = judge_answer(judge, card, payload)
            self.assertTrue(shared_ok, f"Shared judge_answer failed for {card['id']}: {payload} ({shared_reason})")
            ok, _reason = evaluate_question_offline(card, payload)
            self.assertTrue(ok, f"Romaji round-trip failed for {card['id']}: {payload}")
            item_results = per_blank_results(card, payload)
            self.assertTrue(all(it["correct"] for it in item_results), f"per_blank_results failed for {card['id']}: {item_results}")

        self.assertEqual(checked_cards, len(all_cards))
        self.assertGreaterEqual(checked_blanks, 190)

    def test_romaji_submit_e2e_lesson_and_review_paper(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="jp_grammar_romaji_e2e_")
        self.addCleanup(tmp.cleanup)
        data_dir = Path(tmp.name) / "data"
        clock = MutableClock()
        port = _pick_free_loopback_port()
        rt = LocalRuntime(
            packages_dir=PACKAGES_DIR,
            data_dir=data_dir,
            web_dir=WEB_DIR,
            host="127.0.0.1",
            port=port,
            clock=clock,
        )
        jp01_fc = {fc["id"]: fc for fc in _load_topic(JP01)["flashcards"]}
        with TestClient(create_app(rt), base_url=f"http://127.0.0.1:{port}") as client:
            # 1. Start JP01 Lesson and submit romaji directly for every card via /api/submit
            s = client.get("/api/state", params={"topic_id": JP01}).json()
            if s.get("phase") == "choose":
                s = client.post(
                    "/api/choose",
                    params={"topic_id": JP01},
                    json={
                        "request_id": str(uuid.uuid4()),
                        "expected_revision": s["revision"],
                        "attempt_id": s.get("attempt_id"),
                        "step_id": s.get("active_step_id"),
                        "choice": "learn",
                    },
                ).json()
            answered = 0
            tested_wrong = False
            for _ in range(80):
                if s.get("status") == "completed":
                    break
                phase = s.get("phase")
                if phase in ("introduction", "intro", "chunk", "feedback", "waiting"):
                    if phase in ("waiting", "feedback") and s.get("next_available_at"):
                        clock.advance(minutes=15)
                    s = client.post(
                        "/api/continue",
                        params={"topic_id": JP01},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s["revision"],
                            "attempt_id": s["attempt_id"],
                            "step_id": s["active_step_id"],
                        },
                    ).json()
                    continue
                if phase == "answer":
                    cid = s["current"]["card_id"]
                    card = jp01_fc[cid]
                    # On the first question, verify wrong romaji is rejected before submitting correct romaji
                    if not tested_wrong:
                        tested_wrong = True
                        bad_blanks = {b["id"]: "qzxwrong" for b in card["interaction"]["blanks"]}
                        bad_resp = client.post(
                            "/api/submit",
                            params={"topic_id": JP01},
                            json={
                                "request_id": str(uuid.uuid4()),
                                "expected_revision": s["revision"],
                                "attempt_id": s["attempt_id"],
                                "step_id": s["active_step_id"],
                                "answer": json.dumps(bad_blanks, ensure_ascii=False),
                            },
                        )
                        self.assertEqual(bad_resp.status_code, 200, bad_resp.text)
                        bad_body = bad_resp.json()
                        self.assertFalse(bad_body["correct"])
                        self.assertTrue(all(v is False for v in (bad_body.get("blank_results") or {}).values()))
                        s = bad_body["state"]
                        continue
                    token_map = {
                        "だ": "da",
                        "の": "no",
                        "な": "na",
                        "です": "desu",
                        "は": "wa",
                        "が": "ga",
                    }
                    romaji_ans = {
                        b["id"]: token_map[b["answers"][0]]
                        for b in card["interaction"]["blanks"]
                    }
                    ok_resp = client.post(
                        "/api/submit",
                        params={"topic_id": JP01},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s["revision"],
                            "attempt_id": s["attempt_id"],
                            "step_id": s["active_step_id"],
                            "answer": json.dumps(romaji_ans, ensure_ascii=False),
                        },
                    )
                    self.assertEqual(ok_resp.status_code, 200, ok_resp.text)
                    ok_body = ok_resp.json()
                    self.assertTrue(ok_body["correct"], f"{cid}: {ok_body}")
                    br = ok_body.get("blank_results") or {}
                    self.assertTrue(bool(br) and all(v is True for v in br.values()), f"{cid}: {ok_body}")
                    answered += 1
                    s = ok_body["state"]
                    continue
                self.fail(f"Unexpected state in Lesson romaji E2E: {s}")
            self.assertEqual(s.get("status"), "completed")
            self.assertGreaterEqual(answered, 9)

            # 2. Advance clock 3 days and verify Review Paper grading accepts romaji
            clock.advance(days=3)
            inbox = client.get("/api/review-papers/inbox", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
            self.assertGreaterEqual(len(inbox["items"]), 1)
            paper = client.post(
                "/api/review-papers/open",
                params={"subject_id": DEFAULT_SUBJECT_ID},
                json={"request_id": str(uuid.uuid4()), "candidate_id": inbox["items"][0]["id"]},
            ).json()
            rev = paper["revision"]
            review_token_map = {
                "だ": "da",
                "の": "no",
                "な": "na",
                "です": "desu",
                "は": "ha",
                "が": "ga",
            }
            entries = [
                {
                    "index": item["index"],
                    "answer": json.dumps(
                        {
                            b["id"]: review_token_map[b["answers"][0]]
                            for b in jp01_fc[item["content_context"]["question_id"]]["interaction"]["blanks"]
                        },
                        ensure_ascii=False,
                    ),
                    "elapsed_ms": 800,
                }
                for item in paper["items"]
            ]
            for start in range(0, len(entries), 2):
                dr = client.post(
                    "/api/review-papers/draft",
                    params={"subject_id": DEFAULT_SUBJECT_ID},
                    json={"paper_id": paper["id"], "expected_revision": rev, "answers": entries[start : start + 2]},
                )
                self.assertEqual(dr.status_code, 200, dr.text)
                rev = dr.json()["revision"]
            done = client.post(
                "/api/review-papers/submit",
                params={"subject_id": DEFAULT_SUBJECT_ID},
                json={"paper_id": paper["id"], "request_id": str(uuid.uuid4()), "expected_revision": rev},
            ).json()
            self.assertEqual(done["phase"], "done")
            self.assertTrue(all(it["result"]["correct"] for it in done["items"]))

    def test_atomic_next_available_at_prefers_future_wakeup_and_ui_auto_continues(self) -> None:
        from graspmemoedu.atomic import AtomicLearningService

        tmp = tempfile.TemporaryDirectory(prefix="jp_atomic_wakeup_")
        self.addCleanup(tmp.cleanup)
        now = datetime(2026, 11, 15, 3, 20, 0, tzinfo=timezone.utc)
        topic = _load_topic(JP01)
        svc = AtomicLearningService(topic, Path(tmp.name), clock=lambda: now)
        past_iso = (now - timedelta(hours=14)).isoformat()
        future_iso = (now + timedelta(minutes=10)).isoformat()
        fake_state = {
            "mode": "learn",
            "chunk_last_seen": {},
            "points": {
                pid: {"mastered": idx >= 2, "due_at": past_iso if idx == 0 else future_iso}
                for idx, pid in enumerate(svc.point_chunks.keys())
            },
        }
        eligible, wakeup = svc._eligible(fake_state)
        first_pid = next(iter(svc.point_chunks.keys()))
        self.assertEqual(eligible, {first_pid})
        self.assertEqual(wakeup, future_iso)

        app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("autoContinueKeys", app_js)
        self.assertIn("alreadyReady", app_js)
        self.assertIn("triggerContinue", app_js)

    def test_2222_integrated_cards_shared_point_fsrs_memory_and_rotation(self) -> None:
        from graspmemoedu.atomic_content import plain_text
        from tools.japanese_grammar.backend.judge import evaluate_question_offline

        expected_point_counts = {
            JP02: {
                "p-jp02-o-marker": 3,
                "p-jp02-ni-e-diff": 5,
                "p-jp02-ni-vs-de": 6,
                "p-jp02-double-o": 2,
                "p-jp02-trans-rule": 4,
                "p-jp02-trans-pairs": 3,
                "p-jp02-iru-ga": 2,
                "p-jp02-ni-experiencer": 1,
            },
            JP04: {
                "p-jp04-verb-3classes": 3,
                "p-jp04-iru-eru-exc": 4,
                "p-jp04-aru-vs-iru": 2,
                "p-jp04-past-ru": 2,
                "p-jp04-past-u-4rules": 7,
                "p-jp04-past-3exc": 2,
                "p-jp04-past-neg-rule": 3,
            },
            JP06: {
                "p-jp06-state-mod": 4,
                "p-jp06-verb-mod": 3,
                "p-jp06-sentence-order": 2,
                "p-jp06-to-particle": 3,
                "p-jp06-ya-toka": 2,
                "p-jp06-no-3uses": 3,
                "p-jp06-no-explain": 3,
            },
        }
        expected_card_totals = {JP02: 24, JP04: 20, JP06: 19}

        total_2222_cards = 0
        for tid, expected_pts in expected_point_counts.items():
            topic = _load_topic(tid)
            valid_pts = {p["id"] for ch in topic["memory_chunks"] for p in ch["points"]}
            new_cards = [fc for fc in topic["flashcards"] if "-2222-" in fc["id"]]
            self.assertEqual(len(new_cards), expected_card_totals[tid], tid)
            total_2222_cards += len(new_cards)
            counts = {pid: 0 for pid in expected_pts}
            for fc in new_cards:
                for pid in fc["point_ids"]:
                    self.assertIn(pid, valid_pts, f"{fc['id']} references unknown point {pid}")
                    counts[pid] = counts.get(pid, 0) + 1
            self.assertEqual(counts, expected_pts, f"Unexpected 2222 point mapping for {tid}")

        self.assertEqual(total_2222_cards, 63)

        # Verify 3.2 及物度标度 & 必要とする integration and intact anchors on JP02
        jp02_topic = _load_topic(JP02)
        trans_intro = next(i for i in jp02_topic["introductions"] if i["id"] == "intro-jp02-transitivity")
        trans_plain = plain_text(trans_intro["html"])
        self.assertIn("及物度标度", trans_plain)
        self.assertIn("必要(ひつよう)とする", trans_plain)
        self.assertNotIn("{r(", trans_intro["html"])
        iru_chunk = next(ch for ch in jp02_topic["memory_chunks"] if ch["id"] == "chunk-jp02-iru-wakaru")
        self.assertIn("必要とする", iru_chunk["html"])
        for anchor in iru_chunk["anchors"]:
            self.assertIn(anchor["quote"], trans_plain)

        # Verify special romaji & short-answer variants for 2222 cards
        all_fc = _all_flashcards()
        for cid, romaji_val in (
            ("fc-jp04-2222-01", "godan"),
            ("fc-jp04-2222-02", "ichidan"),
            ("fc-jp04-2222-04", "godan"),
            ("fc-jp04-2222-05", "shiru"),
            ("fc-jp04-2222-06", "godan"),
            ("fc-jp04-2222-11", "oyoida"),
            ("fc-jp04-2222-15", "kaetta"),
            ("fc-jp04-2222-18", "tabenakatta"),
            ("fc-jp04-2222-19", "kawanakatta"),
            ("fc-jp04-2222-20", "inakatta"),
            ("fc-jp06-2222-08", "tabeta"),
            ("fc-jp06-2222-11", "b"),
            ("fc-jp06-2222-19", "janakatta"),
        ):
            ok, reason = evaluate_question_offline(all_fc[cid], json.dumps({"b1": romaji_val}, ensure_ascii=False))
            self.assertTrue(ok, f"{cid} rejected romaji/variant {romaji_val!r}: {reason}")

        # E2E Lesson + Review Paper verification of shared FSRS point memory & card rotation
        tmp = tempfile.TemporaryDirectory(prefix="jp_2222_shared_mem_")
        self.addCleanup(tmp.cleanup)
        data_dir = Path(tmp.name) / "data"
        clock = MutableClock()
        port = _pick_free_loopback_port()
        rt = LocalRuntime(
            packages_dir=PACKAGES_DIR,
            data_dir=data_dir,
            web_dir=WEB_DIR,
            host="127.0.0.1",
            port=port,
            clock=clock,
        )
        jp01_fc = {fc["id"]: fc for fc in _load_topic(JP01)["flashcards"]}
        jp02_fc = {fc["id"]: fc for fc in jp02_topic["flashcards"]}
        expected_jp02_points = {p["id"] for ch in jp02_topic["memory_chunks"] for p in ch["points"]}

        with TestClient(create_app(rt), base_url=f"http://127.0.0.1:{port}") as client:
            # Complete JP01 prerequisite
            self.assertEqual(self._drive_topic_cards(client, clock, JP01, jp01_fc).get("status"), "completed")

            # Enter JP02 Lesson: intentionally miss p-jp02-o-marker's initial card twice so Lesson rotates to a 2222 variant
            s2 = client.get("/api/state", params={"topic_id": JP02}).json()
            seen_o_marker_cards: list[str] = []
            for _ in range(40):
                if s2.get("phase") == "answer" and s2["current"]["point_ids"] == ["p-jp02-o-marker"]:
                    cid = s2["current"]["card_id"]
                    seen_o_marker_cards.append(cid)
                    if len(seen_o_marker_cards) <= 2:
                        # Fail first two p-jp02-o-marker cards (fc-jp02-01, fc-jp02-02) to force rotation to 2222 variant
                        sub = client.post(
                            "/api/submit",
                            params={"topic_id": JP02},
                            json={
                                "request_id": str(uuid.uuid4()),
                                "expected_revision": s2["revision"],
                                "attempt_id": s2["attempt_id"],
                                "step_id": s2["active_step_id"],
                                "answer": _wrong_fill_blank_answer(jp02_fc[cid]),
                            },
                        )
                        self.assertEqual(sub.status_code, 200, sub.text)
                        s2 = sub.json()["state"]
                        continue
                    # Third card for p-jp02-o-marker must be a 2222 card (least-used rotation)
                    self.assertIn("-2222-", cid, f"Expected rotation to 2222 card, got {seen_o_marker_cards}")
                    sub = client.post(
                        "/api/submit",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                            "answer": demo_answer(jp02_fc[cid]),
                        },
                    )
                    self.assertEqual(sub.status_code, 200, sub.text)
                    s2 = sub.json()["state"]
                    break
                if s2.get("phase") in {"introduction", "chunk", "feedback", "waiting"}:
                    if s2.get("next_available_at"):
                        clock.advance(minutes=15)
                    s2 = client.post(
                        "/api/continue",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                        },
                    ).json()
                elif s2.get("phase") == "answer":
                    cid = s2["current"]["card_id"]
                    s2 = client.post(
                        "/api/submit",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                            "answer": demo_answer(jp02_fc[cid]),
                        },
                    ).json()["state"]

            self.assertEqual(len(set(seen_o_marker_cards)), 3)
            with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
                body_after_o = json.loads(
                    con.execute("SELECT body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP02)).fetchone()[0]
                )
            self.assertEqual(set(body_after_o["atomic"]["points"].keys()), expected_jp02_points)
            self.assertTrue(body_after_o["atomic"]["points"]["p-jp02-o-marker"]["mastered"])

            # Finish remaining JP02 points
            self.assertEqual(self._drive_topic_cards(client, clock, JP02, jp02_fc).get("status"), "completed")

            with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
                pre_review_body = json.loads(
                    con.execute("SELECT body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP02)).fetchone()[0]
                )
            pre_o_point = pre_review_body["atomic"]["points"]["p-jp02-o-marker"]
            pre_o_due = pre_o_point["due_at"]
            pre_o_card = json.loads(pre_o_point["card_json"])

            # Run Review Paper rounds (+3d, +14d, +30d, +45d), clearing JP01 reviews before each round so JP02 is unblocked.
            # Round 1 uses remaining original uses=0 JP02 cards; later rounds rotate in 2222 single & multi cards.
            observed_2222_review_cards: list[str] = []
            reviewed_points: set[str] = set()
            double_o_first_card_id: str | None = None
            double_o_first_stability: float | None = None
            double_o_first_due: str | None = None
            for advance_days in (3, 14, 30, 45):
                clock.advance(days=advance_days)
                for _ in range(30):
                    inbox = client.get("/api/review-papers/inbox", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
                    jp01_items = [it for it in inbox["items"] if (it.get("source") or {}).get("container") == JP01]
                    if not jp01_items:
                        break
                    paper = client.post(
                        "/api/review-papers/open",
                        params={"subject_id": DEFAULT_SUBJECT_ID},
                        json={"request_id": str(uuid.uuid4()), "candidate_id": jp01_items[0]["id"]},
                    ).json()
                    rev = paper["revision"]
                    entries = [
                        {
                            "index": item["index"],
                            "answer": demo_answer(jp01_fc[item["content_context"]["question_id"]]),
                            "elapsed_ms": 800,
                        }
                        for item in paper["items"]
                    ]
                    for start in range(0, len(entries), 2):
                        rev = client.post(
                            "/api/review-papers/draft",
                            params={"subject_id": DEFAULT_SUBJECT_ID},
                            json={"paper_id": paper["id"], "expected_revision": rev, "answers": entries[start : start + 2]},
                        ).json()["revision"]
                    done = client.post(
                        "/api/review-papers/submit",
                        params={"subject_id": DEFAULT_SUBJECT_ID},
                        json={"paper_id": paper["id"], "request_id": str(uuid.uuid4()), "expected_revision": rev},
                    ).json()
                    self.assertEqual(done["phase"], "done")
                    clock.advance(seconds=185)

                for _ in range(25):
                    inbox = client.get("/api/review-papers/inbox", params={"subject_id": DEFAULT_SUBJECT_ID}).json()
                    jp02_items = [it for it in inbox["items"] if (it.get("source") or {}).get("container") == JP02]
                    if not jp02_items:
                        break
                    paper = client.post(
                        "/api/review-papers/open",
                        params={"subject_id": DEFAULT_SUBJECT_ID},
                        json={"request_id": str(uuid.uuid4()), "candidate_id": jp02_items[0]["id"]},
                    ).json()
                    rev = paper["revision"]
                    entries = []
                    for item in paper["items"]:
                        qid = item["content_context"]["question_id"]
                        if "-2222-" in qid:
                            observed_2222_review_cards.append(qid)
                        reviewed_points.update(jp02_fc[qid]["point_ids"])
                        entries.append({"index": item["index"], "answer": demo_answer(jp02_fc[qid]), "elapsed_ms": 900})
                    for start in range(0, len(entries), 2):
                        rev = client.post(
                            "/api/review-papers/draft",
                            params={"subject_id": DEFAULT_SUBJECT_ID},
                            json={"paper_id": paper["id"], "expected_revision": rev, "answers": entries[start : start + 2]},
                        ).json()["revision"]
                    done = client.post(
                        "/api/review-papers/submit",
                        params={"subject_id": DEFAULT_SUBJECT_ID},
                        json={"paper_id": paper["id"], "request_id": str(uuid.uuid4()), "expected_revision": rev},
                    ).json()
                    self.assertEqual(done["phase"], "done")
                    clock.advance(seconds=185)

                if double_o_first_card_id is None:
                    with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
                        mid_body = json.loads(
                            con.execute("SELECT body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP02)).fetchone()[0]
                        )
                    mid_do = mid_body["atomic"]["points"]["p-jp02-double-o"]
                    if mid_do.get("card_json"):
                        mid_do_card = json.loads(mid_do["card_json"])
                        double_o_first_card_id = mid_do_card["card_id"]
                        double_o_first_stability = mid_do_card["stability"]
                        double_o_first_due = mid_do["due_at"]

            self.assertGreaterEqual(len(observed_2222_review_cards), 3, f"Expected 2222 cards in JP02 reviews, got {observed_2222_review_cards}")
            self.assertIn("fc-jp02-2222-15", observed_2222_review_cards)
            self.assertIn("fc-jp02-2222-16", observed_2222_review_cards)
            self.assertIn("fc-jp02-2222-24", observed_2222_review_cards)
            self.assertEqual(reviewed_points, expected_jp02_points)

            with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
                post_review_body = json.loads(
                    con.execute("SELECT body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP02)).fetchone()[0]
                )
            self.assertEqual(set(post_review_body["atomic"]["points"].keys()), expected_jp02_points)
            for qid in observed_2222_review_cards:
                self.assertGreaterEqual(post_review_body["atomic"]["card_uses"].get(qid, 0), 1)
            post_o_point = post_review_body["atomic"]["points"]["p-jp02-o-marker"]
            post_o_due = post_o_point["due_at"]
            post_o_card = json.loads(post_o_point["card_json"])
            self.assertEqual(post_o_card["card_id"], pre_o_card["card_id"])
            self.assertNotEqual(post_o_due, pre_o_due)
            self.assertGreater(
                datetime.fromisoformat(post_o_card["last_review"]),
                datetime.fromisoformat(pre_o_card["last_review"]),
            )
            self.assertGreater(post_o_card["stability"], pre_o_card["stability"])
            # Also confirm p-jp02-double-o kept the SAME FSRS card_id across original + 2222 card reviews
            self.assertIsNotNone(double_o_first_card_id)
            post_do = post_review_body["atomic"]["points"]["p-jp02-double-o"]
            post_do_card = json.loads(post_do["card_json"])
            self.assertEqual(post_do_card["card_id"], double_o_first_card_id)
            self.assertNotEqual(post_do["due_at"], double_o_first_due)
            self.assertGreater(post_do_card["stability"], double_o_first_stability)

    def test_compatible_migration_from_in_progress_waiting_jp02_and_completed_jp01(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="jp_waiting_migrate_")
        self.addCleanup(tmp.cleanup)
        root_tmp = Path(tmp.name)
        old_pkg_dir = root_tmp / "old_packages"
        shutil.copytree(PACKAGES_DIR, old_pkg_dir)

        legacy_version = "jp-grammar-legacy-pre2222"
        legacy_cv = "legacypre2222cv1"
        for tid in (JP02, JP04, JP06):
            tp = old_pkg_dir / tid / "topic.json"
            data = json.loads(tp.read_text(encoding="utf-8"))
            data["version"] = legacy_version
            data["content_version"] = legacy_cv
            data["flashcards"] = [fc for fc in data["flashcards"] if "-2222-" not in fc["id"]]
            tp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        data_dir = root_tmp / "data"
        clock = MutableClock()
        port = _pick_free_loopback_port()

        rt_old = LocalRuntime(
            packages_dir=old_pkg_dir,
            data_dir=data_dir,
            web_dir=WEB_DIR,
            host="127.0.0.1",
            port=port,
            clock=clock,
        )
        jp01_fc = {fc["id"]: fc for fc in json.loads((old_pkg_dir / JP01 / "topic.json").read_text(encoding="utf-8"))["flashcards"]}
        jp02_fc = {fc["id"]: fc for fc in json.loads((old_pkg_dir / JP02 / "topic.json").read_text(encoding="utf-8"))["flashcards"]}

        with TestClient(create_app(rt_old), base_url=f"http://127.0.0.1:{port}") as client_old:
            # Complete JP01 advancing only 181s per chunk cooldown so JP01's 6h first review stays in the future
            s1 = client_old.get("/api/state", params={"topic_id": JP01}).json()
            for _ in range(120):
                if s1.get("status") == "completed" or s1.get("phase") == "completed":
                    break
                p1 = s1.get("phase")
                if p1 in {"introduction", "chunk", "feedback", "waiting"}:
                    if s1.get("next_available_at"):
                        clock.advance(seconds=181)
                    s1 = client_old.post(
                        "/api/continue",
                        params={"topic_id": JP01},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s1["revision"],
                            "attempt_id": s1["attempt_id"],
                            "step_id": s1["active_step_id"],
                        },
                    ).json()
                elif p1 == "answer":
                    cid = s1["current"]["card_id"]
                    s1 = client_old.post(
                        "/api/submit",
                        params={"topic_id": JP01},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s1["revision"],
                            "attempt_id": s1["attempt_id"],
                            "step_id": s1["active_step_id"],
                            "answer": demo_answer(jp01_fc[cid]),
                        },
                    ).json()["state"]
                else:
                    self.fail(f"Unexpected JP01 state: {s1}")
            self.assertEqual(s1.get("status"), "completed")

            # Drive JP02 so 8/10 points are mastered and 2/10 (p-jp02-ni-vs-de, p-jp02-trans-pairs) stay unmastered in atomic.phase='waiting'
            target_unmastered = {"p-jp02-ni-vs-de", "p-jp02-trans-pairs"}
            s2 = client_old.get("/api/state", params={"topic_id": JP02}).json()
            last_was_target = False
            for _ in range(120):
                if s2.get("phase") == "waiting" and s2.get("learned_count") == 8:
                    break
                phase = s2.get("phase")
                if phase in {"introduction", "chunk"}:
                    s2 = client_old.post(
                        "/api/continue",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                        },
                    ).json()
                elif phase == "answer":
                    cid = s2["current"]["card_id"]
                    pts = set(s2["current"]["point_ids"])
                    last_was_target = bool(pts & target_unmastered)
                    ans = _wrong_fill_blank_answer(jp02_fc[cid]) if last_was_target else demo_answer(jp02_fc[cid])
                    s2 = client_old.post(
                        "/api/submit",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                            "answer": ans,
                        },
                    ).json()["state"]
                elif phase == "feedback":
                    # Do NOT advance clock after intentionally failing a target point so UnifiedLearningService
                    # moves forward through sections without re-serving the target point inside the same section.
                    if not last_was_target and s2.get("learned_count", 0) < 8 and s2.get("next_available_at"):
                        clock.advance(seconds=181)
                    last_was_target = False
                    s2 = client_old.post(
                        "/api/continue",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                        },
                    ).json()
                elif phase == "waiting":
                    if s2.get("learned_count") == 8:
                        break
                    clock.advance(seconds=181)
                    s2 = client_old.post(
                        "/api/continue",
                        params={"topic_id": JP02},
                        json={
                            "request_id": str(uuid.uuid4()),
                            "expected_revision": s2["revision"],
                            "attempt_id": s2["attempt_id"],
                            "step_id": s2["active_step_id"],
                        },
                    ).json()
                else:
                    self.fail(f"Unexpected JP02 state before migration: {s2}")

        with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
            pre_jp01_row = con.execute("SELECT version, body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP01)).fetchone()
            pre_jp02_row = con.execute("SELECT version, body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP02)).fetchone()
            pre_jp01_rps = con.execute("SELECT id, source_point FROM review_points WHERE container=?", (JP01,)).fetchall()
            pre_jp02_rps = con.execute("SELECT id, source_point FROM review_points WHERE container=? AND version=?", (JP02, legacy_version)).fetchall()

        pre_jp02_body = json.loads(pre_jp02_row[1])
        self.assertEqual(pre_jp02_row[0], legacy_version)
        self.assertEqual(pre_jp02_body["status"], "in_progress")
        self.assertEqual(pre_jp02_body["display"], "atomic")
        self.assertTrue(pre_jp02_body.get("atomic_catch_up"))
        self.assertEqual(pre_jp02_body["atomic"]["phase"], "waiting")
        pre_mastered = {k for k, v in pre_jp02_body["atomic"]["points"].items() if v.get("mastered")}
        pre_unmastered = {k for k, v in pre_jp02_body["atomic"]["points"].items() if not v.get("mastered")}
        self.assertEqual(len(pre_mastered), 8)
        self.assertEqual(pre_unmastered, target_unmastered)
        self.assertEqual(len(pre_jp01_rps), 9)
        self.assertEqual(len(pre_jp02_rps), 10)

        # Upgrade to rebuilt PACKAGES_DIR
        rt_new = LocalRuntime(
            packages_dir=PACKAGES_DIR,
            data_dir=data_dir,
            web_dir=WEB_DIR,
            host="127.0.0.1",
            port=port,
            clock=clock,
        )
        migrated_ids = [m["topic_id"] for m in rt_new.revision_migration["migrated_topics"]]
        self.assertIn(JP02, migrated_ids)
        self.assertNotIn(JP01, migrated_ids)
        self.assertTrue(list((data_dir / "backups").glob("learning-pre-migrate-*.sqlite3")))

        new_jp01 = _load_topic(JP01)
        new_jp02 = _load_topic(JP02)
        with closing(sqlite3.connect(str(data_dir / "learning.sqlite3"))) as con:
            post_jp01_row = con.execute("SELECT version, body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP01)).fetchone()
            post_jp02_row = con.execute("SELECT version, body FROM topics WHERE learner=? AND topic=?", (LOCAL_LEARNER_ID, JP02)).fetchone()
            post_jp01_rps = con.execute("SELECT id, source_point FROM review_points WHERE container=? AND version=?", (JP01, new_jp01["version"])).fetchall()
            post_jp02_rps = con.execute("SELECT id, source_point FROM review_points WHERE container=? AND version=?", (JP02, new_jp02["version"])).fetchall()
            leftover_legacy_rps = con.execute("SELECT COUNT(*) FROM review_points WHERE version=?", (legacy_version,)).fetchone()[0]

        self.assertEqual(post_jp01_row[0], pre_jp01_row[0])
        self.assertEqual(post_jp01_rps, pre_jp01_rps)
        self.assertEqual(post_jp02_row[0], new_jp02["version"])
        self.assertEqual(len(post_jp02_rps), 10)
        self.assertEqual(leftover_legacy_rps, 0)

        post_jp02_body = json.loads(post_jp02_row[1])
        self.assertEqual(post_jp02_body["status"], "in_progress")
        self.assertEqual(post_jp02_body["display"], "atomic")
        self.assertTrue(post_jp02_body.get("atomic_catch_up"))
        self.assertEqual(post_jp02_body["atomic"]["phase"], "waiting")
        post_mastered = {k for k, v in post_jp02_body["atomic"]["points"].items() if v.get("mastered")}
        self.assertEqual(post_mastered, pre_mastered)
        self.assertEqual(len(post_jp02_body["atomic"]["history"]), len(pre_jp02_body["atomic"]["history"]))
        for item in post_jp02_body["atomic"]["history"]:
            self.assertIsInstance(item.get("snapshot"), dict)
            self.assertEqual(item.get("snapshot_version"), legacy_version)

        # Resume JP02 from phase='waiting', enforce cooldown 409, then finish remaining 2 points cleanly
        new_jp02_fc = {fc["id"]: fc for fc in new_jp02["flashcards"]}
        with TestClient(create_app(rt_new), base_url=f"http://127.0.0.1:{port}") as client_new:
            resumed1 = client_new.get("/api/state", params={"topic_id": JP01}).json()
            self.assertEqual(resumed1["status"], "completed")
            resumed2 = client_new.get("/api/state", params={"topic_id": JP02}).json()
            self.assertEqual(resumed2["status"], "in_progress")
            self.assertEqual(resumed2["phase"], "waiting")
            self.assertEqual(resumed2["learned_count"], 8)
            self.assertEqual(resumed2["point_count"], 10)

            early = client_new.post(
                "/api/continue",
                params={"topic_id": JP02},
                json={
                    "request_id": str(uuid.uuid4()),
                    "expected_revision": resumed2["revision"],
                    "attempt_id": resumed2["attempt_id"],
                    "step_id": resumed2["active_step_id"],
                },
            )
            self.assertEqual(early.status_code, 200)
            self.assertEqual(early.json()["phase"], "waiting")
            self.assertEqual(early.json()["learned_count"], 8)

            finished2 = self._drive_topic_cards(client_new, clock, JP02, new_jp02_fc)
            self.assertEqual(finished2.get("status"), "completed")


if __name__ == "__main__":
    unittest.main()
