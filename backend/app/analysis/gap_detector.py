"""Deterministic, evidence-first candidate research gap detection.

The gap detector is deliberately conservative. It treats topic frequency,
repeated title words, and generic academic wording as corpus observations rather
than as evidence of a research gap. A candidate gap must be supported by
explicit limitation, future-work, contradiction, or comparison evidence.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from app.analysis.evidence_rules import STOPWORDS
from app.analysis.schemas import (
    AnalysisLimitations,
    CandidateResearchGap,
    EvidenceCategory,
    EvidenceItem,
    GapCategory,
)

_GENERIC_GAP_TERMS = {
    "study", "studies", "research", "paper", "article", "approach", "method",
    "methods", "methodology", "result", "results", "analysis", "investigation",
    "development", "developed", "using", "used", "based", "proposed", "evaluate",
    "evaluation", "effect", "effects", "performance", "experiment", "experimental",
    "data", "findings", "application", "process", "processes", "system", "systems",
    "model", "models", "work", "works", "review", "survey", "framework", "frameworks",
    "design", "designed", "problem", "problems", "metric", "metrics", "topic",
    "keyword", "keywords", "title", "abstract", "paper", "article", "methodology",
    "signal", "signals", "finding", "findings",
}
_GENERIC_CONTEXT_TERMS = _GENERIC_GAP_TERMS | {
    "limited", "limitation", "limitations", "generalizability", "generalization",
    "validation", "validate", "future", "work", "additional", "one", "dataset", "phrase",
}


def detect_candidate_gaps(
    evidence: Sequence[EvidenceItem],
    papers: Sequence[Any] | Mapping[int, Any] | None = None,
    *,
    research_question: str | None = None,
    methodology_version: str | None = None,
) -> list[CandidateResearchGap]:
    """Return only candidate gaps that are evidence-backed and not merely topic frequency."""
    ordered = _deduplicate_evidence(list(evidence))
    if not ordered:
        return []

    unique_papers = {item.paper_id for item in ordered}
    if len(unique_papers) < 2:
        return []

    gaps: list[CandidateResearchGap] = []
    gaps.extend(_detect_limitations(ordered, papers=papers, research_question=research_question))
    gaps.extend(_detect_future_work(ordered, papers=papers, research_question=research_question))
    gaps.extend(_detect_conflicts(ordered))
    gaps.extend(_detect_method_gap(ordered))
    return _deduplicate(gaps)


def detect_corpus_coherence(
    evidence: Sequence[EvidenceItem],
    papers: Sequence[Any] | Mapping[int, Any] | None = None,
) -> dict[str, Any]:
    paper_ids = {item.paper_id for item in evidence}
    if len(paper_ids) == 1:
        return {
            "status": "insufficient",
            "summary": "There is only one selected paper, so cross-paper coherence cannot be assessed.",
            "dominant_cluster": None,
        }
    if not paper_ids:
        return {"status": "low", "summary": "No paper evidence is available to assess coherence.", "dominant_cluster": None}

    topic_claims = [item.claim for item in evidence if item.evidence_type is EvidenceCategory.TOPIC]
    if not topic_claims:
        return {
            "status": "medium",
            "summary": "The corpus has too little topic-level evidence to assess coherence reliably.",
            "dominant_cluster": None,
        }

    clusters: dict[str, set[int]] = defaultdict(set)
    for item in evidence:
        if item.evidence_type is not EvidenceCategory.TOPIC:
            continue
        key = _normalize_topic_key(item.claim)
        if key:
            clusters[key].add(item.paper_id)

    if not clusters:
        return {"status": "low", "summary": "The selected corpus does not produce a stable topic cluster.", "dominant_cluster": None}

    dominant_key, dominant_papers = max(clusters.items(), key=lambda entry: (len(entry[1]), entry[0]))
    dominant_ratio = len(dominant_papers) / max(len(paper_ids), 1)
    if dominant_ratio >= 0.7 and len(clusters) <= 2:
        return {"status": "high", "summary": "The selected papers are concentrated around a shared topic.", "dominant_cluster": dominant_key}
    return {"status": "low", "summary": "The selected papers span substantially different research domains, so cross-paper synthesis is weak.", "dominant_cluster": dominant_key}


def _detect_limitations(
    evidence: Sequence[EvidenceItem],
    *,
    papers: Sequence[Any] | Mapping[int, Any] | None = None,
    research_question: str | None = None,
) -> list[CandidateResearchGap]:
    filtered = [
        item for item in evidence
        if item.evidence_type is EvidenceCategory.LIMITATION
        and _is_valid_gap_claim(item.claim, EvidenceCategory.LIMITATION)
    ]
    filtered = _filter_cross_paper_context(filtered, evidence, papers, research_question)
    return _grouped_gap(
        "limitations",
        GapCategory.METHODOLOGICAL_LIMITATION,
        "The selected corpus reports recurring methodological limitations that limit confidence in the available evidence.",
        "Multiple papers explicitly describe limitations or weak design characteristics.",
        "The evidence is insufficiently robust to support a strong conclusion across the selected corpus.",
        filtered,
        0.72,
    )


def _detect_future_work(
    evidence: Sequence[EvidenceItem],
    *,
    papers: Sequence[Any] | Mapping[int, Any] | None = None,
    research_question: str | None = None,
) -> list[CandidateResearchGap]:
    filtered = [
        item for item in evidence
        if item.evidence_type is EvidenceCategory.FUTURE_WORK
        and _is_valid_gap_claim(item.claim, EvidenceCategory.FUTURE_WORK)
    ]
    filtered = _filter_cross_paper_context(filtered, evidence, papers, research_question)
    return _grouped_gap(
        "future-work",
        GapCategory.VALIDATION_GAP,
        "The selected literature repeatedly identifies unresolved validation and follow-up work.",
        "Multiple papers explicitly recommend further validation, study, or generalization work.",
        "The current evidence does not yet establish the needed validation or generalization across the selected corpus.",
        filtered,
        0.68,
    )


def _detect_conflicts(evidence: Sequence[EvidenceItem]) -> list[CandidateResearchGap]:
    filtered = [item for item in evidence if item.evidence_type is EvidenceCategory.CONTRADICTION and _is_valid_gap_claim(item.claim)]
    if not _has_comparable_contradiction(filtered):
        return []
    return _grouped_gap(
        "contradiction",
        GapCategory.INCONSISTENT_EVIDENCE,
        "The selected corpus contains conflicting evidence that prevents a stable conclusion.",
        "Different papers report materially inconsistent findings or outcomes in the same domain.",
        "The evidence base is not stable enough to infer a single reliable conclusion from the selected corpus.",
        filtered,
        0.78,
    )


def _has_comparable_contradiction(items: Sequence[EvidenceItem]) -> bool:
    for index, left in enumerate(items):
        for right in items[index + 1:]:
            if left.paper_id == right.paper_id:
                continue
            left_signature = _contradiction_signature(left.claim)
            right_signature = _contradiction_signature(right.claim)
            if left_signature is None or right_signature is None:
                continue
            left_method, left_outcome, left_context, left_polarity = left_signature
            right_method, right_outcome, right_context, right_polarity = right_signature
            if left_method != right_method or left_outcome != right_outcome:
                continue
            if left_context != right_context and (left_context or right_context):
                continue
            if left_polarity == right_polarity:
                continue
            return True
    return False


def _contradiction_signature(claim: str) -> tuple[str, str, str, str] | None:
    normalized = re.sub(r"[^a-z0-9\s-]", " ", claim.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    method_match = re.search(r"\b(?:method|intervention|model|approach)\s+([a-z0-9-]+)", normalized)
    outcome_match = re.search(
        r"\b(?:improv\w*|reduc\w*|increas\w*|decreas\w*)\s+"
        r"(?:the\s+)?([a-z0-9-]+)",
        normalized,
    )
    if outcome_match is None and re.search(r"\bperform\w*\s+(?:better|worse)\b", normalized):
        outcome = "performance"
    elif outcome_match is None:
        return None
    else:
        outcome = outcome_match.group(1)
    if method_match is None:
        return None

    positive = ("improv", "increas", "outperform", "better", "benefit", "enhanc")
    negative = ("worse", "reduc", "decreas", "declin", "fail", "harm", "lower")
    if any(marker in normalized for marker in positive):
        polarity = "positive"
    elif any(marker in normalized for marker in negative):
        polarity = "negative"
    else:
        return None

    context_match = re.search(
        r"\b(?:material|population|system|setting|context|condition|conditions)\s+"
        r"([a-z0-9-]+(?:\s+[a-z0-9-]+)?)",
        normalized,
    )
    context = context_match.group(0) if context_match else ""
    return method_match.group(1), outcome, context, polarity


def _detect_method_gap(evidence: Sequence[EvidenceItem]) -> list[CandidateResearchGap]:
    filtered = [
        item for item in evidence
        if item.evidence_type is EvidenceCategory.METHODOLOGY and _is_valid_gap_claim(item.claim)
        and any(token in item.claim.lower() for token in ("lack", "limited", "cannot", "insufficient", "validation", "generaliz"))
    ]
    return _grouped_gap(
        "method-gap",
        GapCategory.INTERVENTION_OR_METHOD_GAP,
        "The selected corpus does not establish a consistently validated methodological approach.",
        "Several papers refer to methodological limitations or missing validation of the primary approach.",
        "The current evidence is insufficient to conclude that the method is robust or generalizable across the selected studies.",
        filtered,
        0.64,
    )


def _grouped_gap(
    identifier_prefix: str,
    category: GapCategory,
    statement: str,
    pattern: str,
    inference: str,
    items: Sequence[EvidenceItem],
    base_confidence: float,
) -> list[CandidateResearchGap]:
    items = [item for item in _deduplicate_evidence(items) if _is_valid_gap_claim(item.claim)]
    if not items:
        return []

    grouped: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in items:
        if identifier_prefix == "contradiction":
            grouped["contradictory-evidence"].append(item)
        else:
            grouped[_semantic_group_key(item.claim)].append(item)

    candidates: list[CandidateResearchGap] = []
    for group_key, group_items in sorted(grouped.items(), key=lambda entry: (-len({item.paper_id for item in entry[1]}), entry[0])):
        paper_ids = sorted({item.paper_id for item in group_items})
        if len(paper_ids) < 2:
            continue

        observed: list[str] = []
        seen_claims: set[str] = set()
        for item in _unique_item_claims(group_items):
            claim = item.claim.strip()
            if claim in seen_claims:
                continue
            seen_claims.add(claim)
            observed.append(claim)

        if not observed:
            continue

        issue = _issue_label(observed)
        gap_statement = _statement_for_issue(category, issue, statement)
        gap_pattern = _pattern_for_issue(category, issue, pattern, observed)
        gap_inference = _inference_for_issue(category, issue, inference, observed)
        confidence, confidence_breakdown = _score_gap_confidence(base_confidence, group_items, paper_ids)
        candidates.append(
            CandidateResearchGap(
                id=f"{identifier_prefix}-{group_key}-{paper_ids[0]}-{paper_ids[-1]}",
                category=category,
                statement=gap_statement,
                observed_evidence=observed,
                pattern=gap_pattern,
                inference=gap_inference,
                confidence=confidence,
                confidence_breakdown=confidence_breakdown,
                supporting_paper_ids=paper_ids,
                limitations=AnalysisLimitations(items=[
                    "This is a selected-corpus finding, not a field-wide claim.",
                    "Evidence quality and corpus heterogeneity affect confidence.",
                ]),
            )
        )

    if not candidates:
        return []
    return sorted(candidates, key=lambda gap: (-gap.confidence, gap.statement))[:3]


def _deduplicate_evidence(items: Sequence[EvidenceItem]) -> list[EvidenceItem]:
    seen: set[tuple[int, str, str | None]] = set()
    unique: list[EvidenceItem] = []
    for item in items:
        key = (item.paper_id, item.claim.strip(), item.source_excerpt)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _unique_item_claims(items: Sequence[EvidenceItem]) -> list[EvidenceItem]:
    seen: set[tuple[int, str]] = set()
    result: list[EvidenceItem] = []
    for item in items:
        token = (item.paper_id, item.claim.strip())
        if token in seen:
            continue
        seen.add(token)
        result.append(item)
    return result


def _deduplicate(gaps: Sequence[CandidateResearchGap]) -> list[CandidateResearchGap]:
    merged: dict[tuple[GapCategory, str], CandidateResearchGap] = {}
    for gap in gaps:
        key = (gap.category, gap.statement.lower())
        existing = merged.get(key)
        if existing is None or gap.confidence > existing.confidence:
            merged[key] = gap
        else:
            existing.supporting_paper_ids = sorted(set(existing.supporting_paper_ids + gap.supporting_paper_ids))
            existing.observed_evidence = sorted(set(existing.observed_evidence + gap.observed_evidence))
    return sorted(merged.values(), key=lambda gap: (-gap.confidence, gap.statement))


def _is_valid_gap_claim(claim: str, category: EvidenceCategory | None = None) -> bool:
    if not claim or not claim.strip():
        return False
    lowered = re.sub(r"[^a-z0-9\s-]", " ", claim.lower())
    tokens = [token for token in lowered.split() if token and token not in STOPWORDS and token not in {"explicit", "signal"}]
    if not tokens:
        return False
    if len(tokens) <= 2 and set(tokens).issubset(_GENERIC_GAP_TERMS):
        return False
    if set(tokens).issubset(_GENERIC_GAP_TERMS):
        return False
    if category is EvidenceCategory.LIMITATION:
        concrete_markers = (
            "small sample", "limited generaliz", "lack of", "limited by",
            "constrained by", "did not include", "not considered",
            "cannot generalize", "restricted to", "lacked validation", "one dataset",
        )
        return any(marker in lowered for marker in concrete_markers)
    if category is EvidenceCategory.FUTURE_WORK:
        generic_markers = (
            "more research is needed", "further research is needed",
            "future work is needed", "future research is needed",
            "further studies are needed",
        )
        if any(marker in lowered for marker in generic_markers):
            return False
        subject_markers = (
            "validate", "validation", "generaliz", "dataset", "population",
            "setting", "context", "outcome", "method", "comparison",
            "sample", "investigate", "examine", "explore",
        )
        return any(marker in lowered for marker in subject_markers)
    return True


def _filter_cross_paper_context(
    candidate_items: Sequence[EvidenceItem],
    all_evidence: Sequence[EvidenceItem],
    papers: Sequence[Any] | Mapping[int, Any] | None,
    research_question: str | None,
) -> list[EvidenceItem]:
    if papers is None:
        return list(candidate_items)
    paper_map = papers if isinstance(papers, Mapping) else {getattr(paper, "id", None): paper for paper in papers}
    if research_question:
        question_tokens = _content_tokens(research_question)
        if question_tokens:
            relevant_ids = {
                paper_id for paper_id, paper in paper_map.items()
                if question_tokens.intersection(_content_tokens(f"{getattr(paper, 'title', '')} {getattr(paper, 'abstract', '')}"))
            }
            candidate_items = [item for item in candidate_items if item.paper_id in relevant_ids]
    by_paper: dict[int, set[str]] = defaultdict(set)
    for item in all_evidence:
        if item.evidence_type is EvidenceCategory.TOPIC:
            key = _normalize_topic_key(item.claim)
            if key:
                by_paper[item.paper_id].update(
                    token for token in key.split() if token not in _GENERIC_CONTEXT_TERMS
                )
    paper_ids = {item.paper_id for item in candidate_items}
    if len(paper_ids) < 2:
        return []
    shared_tokens = set.intersection(*(by_paper.get(paper_id, set()) for paper_id in paper_ids)) if by_paper else set()
    if not shared_tokens:
        return []
    return list(candidate_items)


def _content_tokens(value: str) -> set[str]:
    return {
        token for token in re.sub(r"[^a-z0-9\s-]", " ", value.lower()).split()
        if token and token not in STOPWORDS and token not in _GENERIC_GAP_TERMS
    }


def _normalize_topic_key(claim: str) -> str:
    lowered = re.sub(r"[^a-z0-9\s-]", " ", claim.lower())
    tokens = [token for token in lowered.split() if token and token not in STOPWORDS and token not in _GENERIC_GAP_TERMS]
    return " ".join(tokens[:3]) or ""


def _semantic_group_key(claim: str) -> str:
    lowered = re.sub(r"[^a-z0-9\s-]", " ", claim.lower())
    if any(token in lowered for token in ("future work", "validate", "validation", "generaliz", "real world", "robust")):
        return "validation"
    if any(token in lowered for token in ("sample size", "small sample", "power", "statistical", "generalizability")):
        return "sample-size-generalizability"
    if any(token in lowered for token in ("baseline", "compared", "versus", "comparison")):
        return "comparison"
    if any(token in lowered for token in ("patient", "participant", "student", "population", "context", "setting")):
        return "population-context"
    if any(token in lowered for token in ("outcome", "accuracy", "performance", "effectiveness", "precision", "recall")):
        return "outcome"
    if any(token in lowered for token in ("reproduc", "replication")):
        return "reproducibility"
    if any(token in lowered for token in ("conflict", "contradict", "inconsisten", "worse", "better")):
        return "contradiction"
    if any(token in lowered for token in ("limitation", "limited", "lack of", "constrained", "weak")):
        return "methodology"
    tokens = [token for token in lowered.split() if token and token not in STOPWORDS and token not in _GENERIC_GAP_TERMS]
    normalized = " ".join(tokens[:3])
    return normalized or "other"


def _issue_label(observed: Sequence[str]) -> str:
    combined = " ".join(observed).lower()
    if any(token in combined for token in ("validate", "validation", "generaliz", "real-world", "robust")):
        return "validation and generalizability"
    if any(token in combined for token in ("sample size", "small sample", "limited", "generalizability")):
        return "sample size and generalizability"
    if any(token in combined for token in ("baseline", "compared", "versus", "comparison")):
        return "comparative evaluation"
    if any(token in combined for token in ("population", "participant", "patient", "student", "context", "setting")):
        return "population or context coverage"
    if any(token in combined for token in ("accuracy", "performance", "effectiveness", "precision", "recall", "outcome")):
        return "outcome measurement and evaluation"
    if any(token in combined for token in ("reproduc", "replication")):
        return "reproducibility"
    if any(token in combined for token in ("limit", "lack", "weak", "constrained")):
        return "methodological constraints"
    return "the reported methodological constraints"


def _statement_for_issue(category: GapCategory, issue: str, fallback_statement: str) -> str:
    if category is GapCategory.METHODOLOGICAL_LIMITATION:
        return f"Within the selected corpus, the repeated evidence points to a methodological gap centered on {issue}."
    if category is GapCategory.VALIDATION_GAP:
        return f"Within the selected corpus, the repeated evidence indicates a validation gap around {issue}."
    if category is GapCategory.INCONSISTENT_EVIDENCE:
        return f"Within the selected corpus, the evidence is inconsistent on {issue}, preventing a stable conclusion."
    if category is GapCategory.INTERVENTION_OR_METHOD_GAP:
        return f"Within the selected corpus, the evidence suggests an unresolved methodological or intervention gap around {issue}."
    return fallback_statement


def _pattern_for_issue(category: GapCategory, issue: str, fallback_pattern: str, observed: Sequence[str]) -> str:
    if observed:
        return f"Multiple independent papers report the same issue: {observed[0]}"
    return fallback_pattern


def _inference_for_issue(category: GapCategory, issue: str, fallback_inference: str, observed: Sequence[str]) -> str:
    if category is GapCategory.METHODOLOGICAL_LIMITATION:
        return (
            "The selected corpus does not yet provide enough robust evidence to rule out a recurring methodological weakness "
            f"around {issue}."
        )
    if category is GapCategory.VALIDATION_GAP:
        return (
            "The selected corpus does not yet establish sufficient validation or generalization for the reported methods "
            f"around {issue}."
        )
    if category is GapCategory.INCONSISTENT_EVIDENCE:
        return (
            "The selected corpus contains conflicting findings on the same issue, so the current evidence does not support a stable conclusion "
            f"for {issue}."
        )
    return fallback_inference


def _score_gap_confidence(base_confidence: float, items: Sequence[EvidenceItem], paper_ids: Sequence[int]) -> tuple[float, dict[str, float]]:
    claim_text = " ".join(item.claim.lower() for item in items)
    explicit_markers = ("limitation", "future work", "validation", "generaliz", "sample size", "baseline", "conflict", "worse", "better", "insufficient")
    specificity_markers = ("sample size", "generaliz", "validation", "baseline", "population", "patient", "student", "outcome", "reproduc", "real-world")

    explicit_evidence = 1.0 if any(marker in claim_text for marker in explicit_markers) else 0.2
    independent_papers = min(len(paper_ids) / max(len(paper_ids), 2), 1.0)
    grouped_keys = {_semantic_group_key(item.claim) for item in items}
    cross_paper_consistency = 1.0 if len(grouped_keys) == 1 else 0.45
    specificity_signal_count = sum(marker in claim_text for marker in specificity_markers)
    specificity = min(1.0, 0.35 + (0.2 * specificity_signal_count))
    inference_penalty = 0.0 if any(marker in claim_text for marker in explicit_markers) else 0.2
    corpus_size_penalty = 0.1 if len(paper_ids) < 3 else 0.0

    support_strength = 0.08 * max(len(paper_ids) - 1, 0)
    score = (
        0.35
        + support_strength
        + (explicit_evidence * 0.2)
        + (specificity * 0.2)
        + (cross_paper_consistency * 0.1)
        + (0.03 if len(items) > 1 else 0.0)
        - inference_penalty
        - corpus_size_penalty
    )
    score = max(0.25, min(0.95, score))
    breakdown = {
        "explicit_evidence": round(min(1.0, max(0.0, explicit_evidence)), 2),
        "independent_papers": round(min(1.0, max(0.0, independent_papers)), 2),
        "cross_paper_consistency": round(min(1.0, max(0.0, cross_paper_consistency)), 2),
        "specificity": round(min(1.0, max(0.0, specificity)), 2),
        "inference_penalty": round(min(1.0, max(0.0, inference_penalty)), 2),
        "corpus_size_penalty": round(min(1.0, max(0.0, corpus_size_penalty)), 2),
    }
    return round(score, 2), breakdown
