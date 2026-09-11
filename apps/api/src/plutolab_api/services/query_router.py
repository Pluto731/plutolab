"""Deterministic query routing helpers for the Agentic RAG retrieval loop."""

import re
from dataclasses import dataclass

from plutolab_api.schemas.rag import SearchResultItem

_COURTESY_PREFIXES = (
    "请问",
    "请帮我",
    "能否告诉我",
    "可以告诉我",
    "我想知道",
    "帮我看看",
    "please tell me",
    "could you tell me",
)
_STOP_WORDS = {
    "如何",
    "怎么",
    "什么",
    "为什么",
    "是否",
    "请问",
    "帮我",
    "tell",
    "please",
    "about",
    "the",
    "and",
    "with",
}
_TERM_PATTERN = re.compile(
    r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_.-]{1,}|\d+(?:\.\d+)?"
)


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """Search queries derived from the user's original question."""

    original_query: str
    semantic_query: str
    keyword_query: str


def _clean_query(query: str) -> str:
    cleaned = " ".join(query.strip().split())
    lowered = cleaned.casefold()
    for prefix in _COURTESY_PREFIXES:
        if lowered.startswith(prefix.casefold()):
            cleaned = cleaned[len(prefix) :].lstrip(" ，,：:？?！!")
            break
    return cleaned or query.strip()


def _extract_terms(query: str) -> list[str]:
    terms: list[str] = []
    for match in _TERM_PATTERN.findall(query):
        normalized = match.strip().casefold()
        if normalized and normalized not in _STOP_WORDS and normalized not in terms:
            terms.append(normalized)
    return terms


def build_query_plan(
    query: str, history: list[dict[str, str]] | None = None
) -> QueryPlan:
    """Build deterministic semantic and lexical queries without external model calls."""
    original = query.strip()
    cleaned = _clean_query(original)
    terms = _extract_terms(cleaned)

    context_terms: list[str] = []
    for message in reversed(history or []):
        if message.get("role") != "user":
            continue
        context_terms.extend(_extract_terms(message.get("content", "")))
        if len(context_terms) >= 4:
            break

    semantic_parts = [cleaned]
    for term in context_terms:
        if term not in terms and term not in semantic_parts and len(semantic_parts) < 4:
            semantic_parts.append(term)
    semantic_query = " ".join(semantic_parts).strip() or original
    keyword_query = " ".join(terms[:12]).strip() or cleaned or original
    return QueryPlan(
        original_query=original,
        semantic_query=semantic_query,
        keyword_query=keyword_query,
    )


def retrieval_confidence(results: list[SearchResultItem], query: str) -> float:
    """Estimate retrieval confidence using bounded score and lexical coverage.

    This is a control signal for one bounded retry, not an accuracy metric.
    """
    if not results:
        return 0.0

    terms = _extract_terms(query)
    if not terms:
        return min(1.0, len(results) / 5)

    covered = 0
    for term in terms:
        if any(term in result.content.casefold() for result in results[:5]):
            covered += 1
    lexical_coverage = covered / len(terms)
    best_score = max(float(result.score) for result in results[:5])
    if results[0].retrieval_source == "hybrid" and best_score <= 0.2:
        score_signal = min(1.0, max(0.0, best_score * 60.0))
    else:
        score_signal = min(1.0, max(0.0, best_score))
    return round(min(1.0, 0.6 * lexical_coverage + 0.4 * score_signal), 4)


def should_reflect(
    results: list[SearchResultItem], query: str, threshold: float = 0.75
) -> bool:
    """Return whether a single expanded retrieval attempt should run."""
    return retrieval_confidence(results, query) < threshold
