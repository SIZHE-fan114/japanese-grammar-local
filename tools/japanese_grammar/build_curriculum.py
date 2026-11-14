"""Build and validate the Schema-2 Japanese Grammar Curriculum packages.

Outputs:
    tools/japanese_grammar/packages/course_graph.json
    tools/japanese_grammar/packages/<topic_id>/topic.json
    tools/japanese_grammar/packages/<topic_id>/manifest.json
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import uuid

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from graspmemoedu.atomic_content import plain_text, validate_atomic
from graspmemoedu.course_graph import validate_graph
from graspmemoedu.question_types import (
    demo_answer,
    deterministic_verdict,
    validate_interaction,
)
from graspmemoedu.service import create_learning_service
from graspmemoedu.topic_runtime import validate_runtime

from tools.japanese_grammar.corpus_data import (
    COURSE_ID,
    COURSE_TITLE,
    GRAPH_SPEC,
    SOURCE_REM_ID,
    SUBJECT_ID,
    TOPICS,
)

PACKAGES_DIR = Path(__file__).resolve().parent / 'packages'
BLANK_TOKEN_RE = re.compile(r'\{\{blank:([A-Za-z][A-Za-z0-9_-]{0,39})\}\}')
ANY_MUSTACHE_RE = re.compile(r'\{\{|\}\}')
ORPHAN_REF_RE = re.compile(r'\[\d+\]')
FORBIDDEN_SUBSTRINGS = (
    '[Untitled]',
    'beta.remnote.com',
    'file:///',
    '****',
    '^^^',
    'thought Let',
    '見たた',
    '高学生',
    '砸开',
    'ちょうど',
    '**',
    '__',
)


class _BlankTagInspector(HTMLParser):
    """Verify no {{blank:...}} token appears inside forbidden HTML tags/classes."""

    FORBIDDEN_TAGS = frozenset({'ruby', 'rt', 'rp', 'code', 'pre', 'script', 'style'})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[tuple[str, bool]] = []
        self.found_blanks: list[str] = []
        self.violations: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = ''
        for k, v in attrs:
            if k == 'class' and v:
                classes = v
        is_katex = 'katex' in classes.split()
        self.stack.append((tag.lower(), is_katex))

    def handle_endtag(self, tag: str) -> None:
        target = tag.lower()
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx][0] == target:
                del self.stack[idx:]
                break

    def handle_data(self, data: str) -> None:
        tokens = BLANK_TOKEN_RE.findall(data)
        if not tokens:
            return
        self.found_blanks.extend(tokens)
        for tag, is_katex in self.stack:
            if tag in self.FORBIDDEN_TAGS or is_katex:
                self.violations.append(f'blank token inside <{tag}> (katex={is_katex}): {data!r}')


def _sha256_hex(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _find_anchor(intro_plain: str, quote: str) -> dict:
    start = intro_plain.find(quote)
    if start < 0:
        raise ValueError(f'Anchor quote not found in plain_text(intro): {quote!r}\nPlain preview: {intro_plain[:300]!r}')
    return {'start': start, 'end': start + len(quote), 'quote': quote}


def build_topic_package(spec: dict, course_version: str) -> tuple[dict, dict]:
    """Compile one structured Topic spec into a Schema-2 topic.json + manifest.json."""
    introductions = deepcopy(spec['introductions'])
    intro_plain_by_id = {intro['id']: plain_text(intro['html']) for intro in introductions}

    memory_chunks = []
    for chunk_spec in spec['memory_chunks']:
        intro_id = chunk_spec['introduction_id']
        intro_plain = intro_plain_by_id[intro_id]
        anchors = [_find_anchor(intro_plain, q) for q in chunk_spec['anchor_quotes']]
        memory_chunks.append({
            'id': chunk_spec['id'],
            'introduction_id': intro_id,
            'title': chunk_spec['title'],
            'html': chunk_spec['html'],
            'anchors': anchors,
            'points': deepcopy(chunk_spec['points']),
        })

    flashcards = deepcopy(spec['flashcards'])
    sections = deepcopy(spec['sections'])
    content_order = [{'kind': 'introduction', 'id': intro['id']} for intro in introductions]

    core_payload = {
        'id': spec['id'],
        'title': spec['title'],
        'subject_id': SUBJECT_ID,
        'course_id': COURSE_ID,
        'sections': sections,
        'introductions': introductions,
        'content_order': content_order,
        'memory_chunks': memory_chunks,
        'flashcards': flashcards,
    }
    digest = _sha256_hex(core_payload)
    topic = {
        'id': spec['id'],
        'title': spec['title'],
        'subject_id': SUBJECT_ID,
        'course_id': COURSE_ID,
        'course_title': COURSE_TITLE,
        'topic_format_version': 2,
        'topic_kind': 'lesson',
        'training_mode': 'atomic_retrieval',
        'version': f'jp-grammar-{digest[:12]}',
        'content_version': digest[:16],
        'course_version': course_version,
        'source_rem_id': SOURCE_REM_ID,
        'source_sha256': digest,
        'sections': sections,
        'introductions': introductions,
        'introduction': deepcopy(introductions[0]),
        'modules': [],
        'content_order': content_order,
        'content_nodes': [],
        'references': [],
        'memory_chunks': memory_chunks,
        'flashcards': flashcards,
    }

    point_count = sum(len(c['points']) for c in memory_chunks)
    single_learn_cards = sum(
        1 for c in flashcards
        if len(c['point_ids']) == 1 and 'learn' in c['learning_phases']
    )
    manifest = {
        'topic_id': topic['id'],
        'title': topic['title'],
        'subject_id': SUBJECT_ID,
        'course_id': COURSE_ID,
        'version': topic['version'],
        'content_version': topic['content_version'],
        'source_rem_id': SOURCE_REM_ID,
        'source_sha256': digest,
        'section_count': len(sections),
        'introduction_count': len(introductions),
        'chunk_count': len(memory_chunks),
        'point_count': point_count,
        'flashcard_count': len(flashcards),
        'single_learn_flashcard_count': single_learn_cards,
        'multi_point_review_flashcard_count': len(flashcards) - single_learn_cards,
    }
    return topic, manifest


def build_all(packages_dir: Path = PACKAGES_DIR) -> tuple[dict, list[dict], list[dict]]:
    """Build all 6 Topic packages and course_graph.json on disk."""
    packages_dir.mkdir(parents=True, exist_ok=True)
    course_version = _sha256_hex({'topics': TOPICS, 'graph': GRAPH_SPEC})[:16]
    graph = deepcopy(GRAPH_SPEC)
    graph_path = packages_dir / 'course_graph.json'
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    built_topics: list[dict] = []
    manifests: list[dict] = []
    for spec in TOPICS:
        topic, manifest = build_topic_package(spec, course_version)
        topic_dir = packages_dir / topic['id']
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / 'topic.json').write_text(
            json.dumps(topic, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        (topic_dir / 'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        built_topics.append(topic)
        manifests.append(manifest)
    return graph, built_topics, manifests


def _walk_strings(node: object, path: str = '') -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(node, str):
        out.append((path, node))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            out.extend(_walk_strings(item, f'{path}[{idx}]'))
    elif isinstance(node, dict):
        for k, v in node.items():
            out.extend(_walk_strings(v, f'{path}.{k}' if path else k))
    return out


def _audit_hygiene(topic: dict) -> None:
    for path, text in _walk_strings(topic):
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in text:
                raise AssertionError(f'{topic["id"]} {path}: forbidden RemNote/typos substring {bad!r} in {text!r}')
        if ORPHAN_REF_RE.search(text):
            raise AssertionError(f'{topic["id"]} {path}: orphan bracket citation in {text!r}')
        cleaned = BLANK_TOKEN_RE.sub('', text)
        if ANY_MUSTACHE_RE.search(cleaned):
            raise AssertionError(f'{topic["id"]} {path}: stray mustache braces in {text!r}')


def _audit_cards(topic: dict) -> None:
    point_ids = {p['id'] for c in topic['memory_chunks'] for p in c['points']}
    covered_single_learn: set[str] = set()
    for card in topic['flashcards']:
        if card.get('answer_type') != 'fill_blank':
            raise AssertionError(f'{card["id"]}: expected fill_blank, got {card.get("answer_type")!r}')
        interaction = card.get('interaction') or {}
        if interaction.get('grading') != 'exact':
            raise AssertionError(f'{card["id"]}: expected grading=exact')
        validate_interaction(interaction, card['question'])
        validate_interaction(interaction, card['html'])

        blanks = interaction['blanks']
        expected_ids = [b['id'] for b in blanks]
        for b in blanks:
            answers = b.get('answers') or []
            if not answers:
                raise AssertionError(f'{card["id"]} blank {b["id"]}: empty answers')
            for a in answers:
                if '|' in a or not a.strip():
                    raise AssertionError(f'{card["id"]} blank {b["id"]}: invalid answer {a!r}')

        q_blanks = BLANK_TOKEN_RE.findall(card['question'])
        if q_blanks != expected_ids:
            raise AssertionError(f'{card["id"]}: question blanks {q_blanks} != {expected_ids}')

        inspector = _BlankTagInspector()
        inspector.feed(card['html'])
        inspector.close()
        if inspector.violations:
            raise AssertionError(f'{card["id"]}: HTML blank placement violation: {inspector.violations}')
        if inspector.found_blanks != expected_ids:
            raise AssertionError(f'{card["id"]}: html blanks {inspector.found_blanks} != {expected_ids}')

        demo_payload = demo_answer(card)
        demo_ok = deterministic_verdict(card, demo_payload)
        if not (isinstance(demo_ok, tuple) and demo_ok[0] is True):
            raise AssertionError(f'{card["id"]}: demo_answer {demo_payload!r} failed deterministic_verdict: {demo_ok!r}')

        max_variants = max(len(b['answers']) for b in blanks)
        for v_idx in range(max_variants):
            variant_map = {
                b['id']: b['answers'][min(v_idx, len(b['answers']) - 1)]
                for b in blanks
            }
            v_res = deterministic_verdict(card, json.dumps(variant_map, ensure_ascii=False))
            if not (isinstance(v_res, tuple) and v_res[0] is True):
                raise AssertionError(f'{card["id"]}: answer variant {variant_map!r} failed deterministic_verdict: {v_res!r}')

        wrong_map = {b['id']: '誤答テスト' for b in blanks}
        w_res = deterministic_verdict(card, json.dumps(wrong_map, ensure_ascii=False))
        if not (isinstance(w_res, tuple) and w_res[0] is False):
            raise AssertionError(f'{card["id"]}: wrong answer unexpectedly passed deterministic_verdict: {w_res!r}')

        if len(card['point_ids']) == 1 and 'learn' in card['learning_phases']:
            covered_single_learn.add(card['point_ids'][0])

    missing = point_ids - covered_single_learn
    if missing:
        raise AssertionError(f'{topic["id"]}: points missing single-point learn cards: {sorted(missing)}')


def _payload(service, **extra) -> dict:
    state = service.state()
    return {
        'request_id': str(uuid.uuid4()),
        'expected_revision': state['revision'],
        'attempt_id': state['attempt_id'],
        'step_id': state['active_step_id'],
        **extra,
    }


def _simulate_topic_flow(topic: dict) -> dict:
    """Run full UnifiedLearningService progression from intro 1 through completion."""
    clock_now = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)
    seen_intros: list[str] = []
    answered_cards: list[str] = []

    with tempfile.TemporaryDirectory(prefix=f'jp_verify_{topic["id"]}_') as tmpdir:
        service = create_learning_service(
            deepcopy(topic),
            tmpdir,
            judge=None,
            learner_id='verify-learner',
            clock=lambda: clock_now,
        )
        for _ in range(500):
            state = service.state()
            if state.get('completed'):
                break
            mode = state.get('training_mode')
            if mode == 'atomic_retrieval':
                phase = state['phase']
                if phase == 'answer':
                    cid = state['current']['card_id']
                    card = service.atomic.questions[cid]
                    ans = demo_answer(card)
                    res = service.submit(_payload(service, answer=ans))
                    service.process_submission(res['submission_id'])
                    sub = service.submission(res['submission_id'])
                    if not (sub and sub.get('correct')):
                        raise AssertionError(f'{topic["id"]} simulation: demo_answer rejected on {cid}: {sub}')
                    answered_cards.append(cid)
                elif phase == 'waiting':
                    clock_now = datetime.fromisoformat(state['next_available_at'])
                    service.advance(_payload(service))
                else:
                    if phase == 'feedback':
                        clock_now += timedelta(seconds=180)
                    service.advance(_payload(service))
            else:
                active = next(s for s in state['steps'] if s['id'] == state['active_step_id'])
                if active.get('introduction_id') and active['introduction_id'] not in seen_intros:
                    seen_intros.append(active['introduction_id'])
                if active.get('kind') == 'completion':
                    break
                service.advance(_payload(service))
        else:
            raise AssertionError(f'{topic["id"]}: UnifiedLearningService did not complete within 500 steps; last state={service.state()}')

    expected_intros = [i['id'] for i in topic['introductions']]
    if seen_intros != expected_intros:
        raise AssertionError(f'{topic["id"]}: visited intros {seen_intros} != {expected_intros}')
    return {
        'topic_id': topic['id'],
        'visited_intros': len(seen_intros),
        'answered_learn_cards': len(answered_cards),
    }


def verify_all(packages_dir: Path = PACKAGES_DIR) -> list[dict]:
    """Validate serialized course_graph.json and every Topic package on disk."""
    graph_path = packages_dir / 'course_graph.json'
    graph = json.loads(graph_path.read_text(encoding='utf-8'))
    validate_graph(graph)

    results: list[dict] = []
    for spec in TOPICS:
        tid = spec['id']
        topic_path = packages_dir / tid / 'topic.json'
        topic = json.loads(topic_path.read_text(encoding='utf-8'))
        validate_runtime(topic)
        validate_atomic(topic)
        _audit_hygiene(topic)
        _audit_cards(topic)
        sim = _simulate_topic_flow(topic)
        results.append(sim)

    node_ids = {n['topic_id'] for n in graph['nodes']}
    pkg_ids = {spec['id'] for spec in TOPICS}
    if node_ids != pkg_ids:
        raise AssertionError(f'Graph nodes {sorted(node_ids)} != topics {sorted(pkg_ids)}')
    return results


def main() -> int:
    graph, topics, manifests = build_all()
    sims = verify_all()
    summary = {
        'course_id': COURSE_ID,
        'subject_id': SUBJECT_ID,
        'topic_count': len(topics),
        'graph_nodes': len(graph['nodes']),
        'graph_edges': len(graph['edges']),
        'totals': {
            'sections': sum(m['section_count'] for m in manifests),
            'introductions': sum(m['introduction_count'] for m in manifests),
            'memory_chunks': sum(m['chunk_count'] for m in manifests),
            'points': sum(m['point_count'] for m in manifests),
            'flashcards': sum(m['flashcard_count'] for m in manifests),
            'single_learn_flashcards': sum(m['single_learn_flashcard_count'] for m in manifests),
            'multi_point_review_flashcards': sum(m['multi_point_review_flashcard_count'] for m in manifests),
        },
        'manifests': manifests,
        'simulations': sims,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
