"""The existing judge contract shared by Lesson and review submissions."""
from inspect import getattr_static
from .question_types import deterministic_verdict, semantic_arguments, is_reproduction


def instant_question(question):
    """Classify the server's pinned question without grading or exposing its key."""
    return not is_reproduction(question)


def judge_answer(judge, question, answer):
    # Call this outside any database transaction.
    try:
        # Optional adapters must declare the hook. Dynamic __getattr__ proxies
        # (including Mock judges) otherwise fabricate a callable and corrupt
        # mechanical answers before the deterministic grader can see them.
        declared = getattr_static(judge, 'normalize_answer', None)
        normalizer = getattr(judge, 'normalize_answer') if declared is not None else None
        normalized = normalizer(question, answer) if callable(normalizer) else answer
        deterministic = deterministic_verdict(question, normalized)
        if deterministic is not None:
            return deterministic
        if judge is None:
            raise RuntimeError('Judge not configured')
        verdict = judge(*semantic_arguments(question, normalized))
        if not isinstance(verdict, dict):
            verdict = {'status': verdict.status, 'correct': verdict.correct, 'reason': verdict.reason}
        if (verdict.get('status') == 'judged' and type(verdict.get('correct')) is bool
                and isinstance(verdict.get('reason'), str)):
            return verdict['correct'], verdict['reason'][:2000]
    except Exception:
        pass
    return None, '判题服务暂时不可用，请重试；本次未计入作答。'
