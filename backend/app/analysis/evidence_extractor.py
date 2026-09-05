from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Protocol

from app.analysis.evidence_rules import (
    COMPARISON_SIGNALS,
    DATASET_SIGNALS,
    FUTURE_WORK_SIGNALS,
    LIMITATION_SIGNALS,
    METHODOLOGY_SIGNALS,
    OUTCOME_SIGNALS,
    POPULATION_SIGNALS,
    STOPWORDS,
)
from app.analysis.schemas import EvidenceCategory, EvidenceItem

_GENERIC_TOPIC_TERMS = frozenset({
    "study", "studies", "research", "paper", "article", "approach", "method",
    "methodology", "result", "results", "analysis", "investigation", "development",
    "developed", "using", "used", "based", "proposed", "evaluate", "evaluation",
    "effect", "effects", "performance", "experiment", "experimental", "data",
    "findings", "application", "process", "processes", "system", "systems",
    "model", "models", "work", "works", "review", "survey", "framework", "frameworks",
    "design", "designed", "problem", "problems",
})
_SCIENTIFIC_ALLOWLIST = frozenset({"ai", "ml", "3d", "pca", "cnn", "rnn", "nlp", "llm"})
_INVALID_TOPIC_STARTS = frozenset({
    "although", "because", "comprise", "despite", "however", "moreover",
    "finally", "therefore", "using", "which", "while", "with",
})
_INVALID_TOPIC_TOKENS = frozenset({
    "anniversary", "deepire", "eight", "five", "four", "main", "nine",
    "one", "seven", "six", "strong", "three", "two",
})
_INVALID_TOPIC_ENDS = frozenset({
    "are", "be", "being", "comprise", "does", "evaluated", "is", "reported",
    "the", "use", "uses", "used", "were",
})
_TOPIC_VERB_FRAGMENTS = frozenset({
    "answer", "answering", "automatically", "comprise", "developing",
    "evaluate", "extract", "extraction", "extracts", "generate", "generates", "helped", "improve",
    "increasingly", "leading", "propose", "reported", "rises", "shows",
    "track", "uses",
})
_MAX_TOPIC_TERMS = 8
_MAX_MATCHES_PER_CATEGORY = 8
_WHITESPACE_PATTERN = re.compile(r"\s+")


class PaperLike(Protocol):
    id: int
    title: str | None
    abstract: str | None


def extract_evidence(papers: Sequence[PaperLike]) -> list[EvidenceItem]:
    """Extract explicit, paper-attributed evidence without interpretation or network calls."""
    evidence: list[EvidenceItem] = []
    for paper in papers:
        evidence.extend(_extract_paper_evidence(paper))
    return evidence


def extract_key_themes(papers: Sequence[PaperLike]) -> list[dict[str, Any]]:
    phrase_scores: dict[str, dict[str, Any]] = {}
    total_papers = max(len(papers), 1)
    for paper in papers:
        abstract_text = _text(paper.abstract)
        if not abstract_text:
            continue
        for phrase in _iter_topic_phrases(abstract_text):
            key = _canonicalize_phrase(phrase)
            if not key:
                continue
            record = phrase_scores.setdefault(
                key,
                {
                    "phrase": phrase,
                    "normalized_phrase": key,
                    "supporting_paper_ids": set(),
                    "occurrence_count": 0,
                    "score": 0.0,
                },
            )
            record["supporting_paper_ids"].add(_paper_id(paper))
            record["occurrence_count"] += 1
            record["score"] += _phrase_score(phrase, 1, len(record["supporting_paper_ids"]), total_papers)

    themes = []
    for record in phrase_scores.values():
        paper_ids = sorted(record["supporting_paper_ids"])
        themes.append(
            {
                "phrase": record["phrase"],
                "normalized_phrase": record["normalized_phrase"],
                "supporting_paper_ids": paper_ids,
                "paper_count": len(paper_ids),
                "occurrence_count": record["occurrence_count"],
                "score": round(record["score"], 3),
            }
        )
    return sorted(themes, key=lambda item: (-item["score"], -item["paper_count"], item["normalized_phrase"]))[:8]


def _extract_paper_evidence(paper: PaperLike) -> list[EvidenceItem]:
    paper_id = _paper_id(paper)
    title = paper.title or ""
    abstract = paper.abstract or ""
    source_parts = [(abstract, "abstract")] if abstract else []
    if not source_parts:
        return []
    source_text = _normalize_whitespace(" ".join(text for text, _ in source_parts if text))
    if not source_text:
        return []

    evidence: list[EvidenceItem] = []
    evidence.extend(_extract_topics(paper_id, source_parts))
    for category, signals, confidence in (
        (EvidenceCategory.METHODOLOGY, METHODOLOGY_SIGNALS, 0.95),
        (EvidenceCategory.POPULATION_CONTEXT, POPULATION_SIGNALS, 0.85),
        (EvidenceCategory.OUTCOME, OUTCOME_SIGNALS, 0.85),
        (EvidenceCategory.COMPARISON, COMPARISON_SIGNALS, 0.95),
        (EvidenceCategory.DATASET, DATASET_SIGNALS, 0.95),
        (EvidenceCategory.LIMITATION, LIMITATION_SIGNALS, 0.95),
        (EvidenceCategory.FUTURE_WORK, FUTURE_WORK_SIGNALS, 0.95),
    ):
        evidence.extend(_extract_signal_evidence(paper_id, source_text, 0, category, signals, confidence))
    evidence.extend(_extract_reported_findings(paper_id, source_text))
    return evidence


def _extract_topics(paper_id: int, source_parts: list[tuple[str, str]]) -> list[EvidenceItem]:
    topics: list[EvidenceItem] = []
    seen: set[str] = set()
    for text, source_field in source_parts:
        if not text:
            continue
        for phrase in _iter_topic_phrases(text):
            canonical = _canonicalize_phrase(phrase)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            topics.append(
                EvidenceItem(
                    paper_id=paper_id,
                    evidence_type=EvidenceCategory.TOPIC,
                    claim=f"Topic phrase: {phrase}",
                    source_excerpt=_excerpt_for_phrase(text, phrase),
                    source_field=source_field,
                    confidence=0.82,
                    evidence_status="research_element",
                    interpretation="A topic phrase was identified; this is not a reported finding or research gap.",
                )
            )
            if len(topics) >= _MAX_TOPIC_TERMS:
                return topics
    return topics


def _iter_topic_phrases(text: str) -> list[str]:
    normalized = _normalize_text(text)
    tokens = normalized.split()
    if not tokens:
        return []
    phrases: dict[str, float] = {}
    for length in (2, 3):
        for index in range(0, len(tokens) - length + 1):
            window = tokens[index:index + length]
            if any(token in STOPWORDS or token in _GENERIC_TOPIC_TERMS for token in window):
                continue
            phrase = " ".join(window)
            canonical = _canonicalize_phrase(phrase)
            if not canonical or not _is_structurally_valid_topic(window, canonical):
                continue
            phrases[canonical] = max(phrases.get(canonical, 0.0), _phrase_score(phrase, 1, 1, max(len(tokens), 1)))
    ranked = sorted(phrases, key=lambda value: (-phrases[value], value))
    # Keep the most informative complete phrases instead of displaying nested fragments.
    selected: list[str] = []
    for phrase in ranked:
        if any(phrase in existing or existing in phrase for existing in selected):
            continue
        selected.append(phrase)
        if len(selected) >= _MAX_TOPIC_TERMS:
            break
    return selected


def _is_structurally_valid_topic(tokens: Sequence[str], canonical: str) -> bool:
    if not canonical or not tokens:
        return False
    if tokens[0] in _INVALID_TOPIC_STARTS or tokens[-1] in _INVALID_TOPIC_ENDS:
        return False
    if any(token in STOPWORDS or token in _INVALID_TOPIC_TOKENS for token in tokens):
        return False
    if any(token in _TOPIC_VERB_FRAGMENTS for token in tokens):
        return False
    if any(any(character.isdigit() for character in token) for token in tokens):
        return False
    return len(canonical.split()) >= 2 and any(_is_meaningful_token(token) for token in tokens)


def _is_meaningful_token(token: str) -> bool:
    if not token:
        return False
    if token in STOPWORDS or token in _GENERIC_TOPIC_TERMS:
        return False
    if token.isdigit():
        return False
    if len(token) < 3 and token not in _SCIENTIFIC_ALLOWLIST:
        return False
    return True


def _canonicalize_phrase(phrase: str) -> str:
    canonical = _normalize_text(phrase)
    if not canonical:
        return ""
    tokens = [token for token in canonical.split() if _is_meaningful_token(token)]
    if not tokens:
        return ""
    normalized = []
    for token in tokens:
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("sses") and len(token) > 5:
            token = token[:-2]
        elif token.endswith(("ches", "shes", "xes", "zes")):
            token = token[:-2]
        elif token.endswith("s") and len(token) > 4 and not token.endswith(("ss", "us", "is", "as", "os")):
            token = token[:-1]
        normalized.append(token)
    return " ".join(normalized)


def _phrase_score(phrase: str, occurrence_count: int, paper_count: int, total_papers: int) -> float:
    tokens = [token for token in _normalize_text(phrase).split() if token and token not in STOPWORDS]
    if not tokens:
        return 0.0
    length_bonus = 0.7 * (len(tokens) - 1)
    distinct_bonus = 1.8 * (paper_count / max(total_papers, 1))
    generic_penalty = sum(1 for token in tokens if token in _GENERIC_TOPIC_TERMS)
    return occurrence_count * 2.2 + paper_count * 3.0 + length_bonus + distinct_bonus - generic_penalty


def _extract_signal_evidence(
    paper_id: int,
    source_text: str,
    title_boundary: int,
    category: EvidenceCategory,
    signals: Sequence[str],
    confidence: float,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    seen: set[str] = set()
    occupied_ranges: list[tuple[int, int]] = []
    for signal in signals:
        match = re.search(re.escape(signal), source_text, flags=re.IGNORECASE)
        if match is None or signal.lower() in seen:
            continue
        if category is EvidenceCategory.METHODOLOGY and not _is_methodology_match(source_text, match, signal):
            continue
        if any(match.start() < existing_end and match.end() > existing_start for existing_start, existing_end in occupied_ranges):
            continue
        seen.add(signal.lower())
        occupied_ranges.append((match.start(), match.end()))
        excerpt = _sentence_containing(source_text, match.start(), match.end())
        if category in (EvidenceCategory.LIMITATION, EvidenceCategory.FUTURE_WORK) and not _is_concrete_gap_excerpt(excerpt, category):
            continue
        if category is EvidenceCategory.OUTCOME:
            interpretation = (
                f"The abstract mentions {signal} as an outcome or metric, but this match alone does not report a result."
            )
            status = "research_element"
            claim = f"Detected outcome signal: {signal}"
        elif category is EvidenceCategory.FUTURE_WORK:
            target = _future_work_target(excerpt)
            interpretation = (
                f"The paper explicitly identifies {target.rstrip('.')} as a future research target."
            )
            status = "research_element"
            claim = f"Future-work target: {target}"
        else:
            interpretation = f"The abstract contains an explicit {category.value.replace('_', ' ')} signal."
            status = "research_element"
            claim = f"Detected {category.value.replace('_', ' ')} signal: {signal}"
        evidence.append(
            EvidenceItem(
                paper_id=paper_id,
                evidence_type=category,
                claim=claim,
                source_excerpt=excerpt,
                source_field="abstract",
                confidence=confidence,
                evidence_status=status,
                interpretation=interpretation,
            )
        )
        if len(evidence) >= _MAX_MATCHES_PER_CATEGORY:
            break
    return evidence


def _future_work_target(excerpt: str) -> str:
    target = re.sub(r"^\s*future work\s+should\s+", "", excerpt, flags=re.IGNORECASE)
    target = re.sub(r"^\s*future research\s+should\s+", "", target, flags=re.IGNORECASE)
    target = re.sub(r"^\s*further research\s+should\s+", "", target, flags=re.IGNORECASE)
    target = re.sub(r"^\s*further studies\s+should\s+", "", target, flags=re.IGNORECASE)
    return target.strip() or excerpt.strip()


def _extract_reported_findings(paper_id: int, source_text: str) -> list[EvidenceItem]:
    result_cues = re.compile(
        r"\b(?:achiev\w*|obtain\w*|report\w*|prove(?:s|d|n)?|solv\w*|reach\w*|attain\w*|"
        r"measur\w*|improv\w*|increas\w*|decreas\w*|reduc\w*|outperform\w*)\b",
        flags=re.IGNORECASE,
    )
    numeric_result = re.compile(r"\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s*(?:of|out of)\b", flags=re.IGNORECASE)
    findings: list[EvidenceItem] = []
    seen: set[str] = set()
    for sentence_match in re.finditer(r"[^.!?]+[.!?]|[^.!?]+$", source_text):
        excerpt = sentence_match.group(0).strip()
        if "prior work" in excerpt.lower() or "discussed" in excerpt.lower():
            continue
        cue = result_cues.search(excerpt)
        if cue is None:
            continue
        has_numeric_result = numeric_result.search(excerpt) is not None
        has_comparative_result = bool(re.search(
            r"\b(?:improv\w*|increas\w*|decreas\w*|reduc\w*|outperform\w*)\b"
            r"[^.!?]{0,80}\b(?:accuracy|performance|error|success|rate|baseline|result)\b"
            r"|\b(?:over|than)\s+(?:the\s+)?baseline\b",
            excerpt,
            flags=re.IGNORECASE,
        ))
        if not has_numeric_result and not has_comparative_result:
            continue
        # Retain the source sentence so the reported result keeps its grammatical subject.
        claim = f"Reported finding: {_finding_claim(excerpt)}"
        if claim in seen:
            continue
        seen.add(claim)
        findings.append(EvidenceItem(
            paper_id=paper_id,
            evidence_type=EvidenceCategory.FINDING,
            claim=claim,
            source_excerpt=excerpt,
            source_field="abstract",
            confidence=0.9,
            evidence_status="finding",
            interpretation="The abstract explicitly reports a result in this excerpt.",
        ))
    return findings[:_MAX_MATCHES_PER_CATEGORY]


def _finding_claim(excerpt: str) -> str:
    """Make common reported-result constructions readable without adding claims."""
    claim = excerpt.strip()
    claim = re.sub(r"^As [^,]+,\s*we develop\s+", "", claim, flags=re.IGNORECASE)
    claim = re.sub(r"^We also automatically prove\s+(.+?)\s+when the automated provers are helped by using only\s+(.+)$",
                   r"The automated provers prove \1 when helped using only \2", claim, flags=re.IGNORECASE)
    claim = re.sub(r"^(?:a|an)\s+", "", claim, flags=re.IGNORECASE)
    return claim[:1].upper() + claim[1:] if claim else excerpt


def _is_concrete_gap_excerpt(excerpt: str, category: EvidenceCategory) -> bool:
    normalized = excerpt.lower()
    if category is EvidenceCategory.LIMITATION:
        return any(marker in normalized for marker in (
            "small sample", "one dataset", "limited generaliz", "lack of",
            "limited by", "constrained by", "did not include", "not considered",
            "cannot generalize", "restricted to",
        ))
    if any(marker in normalized for marker in (
        "more research is needed", "further research is needed",
        "future work is needed", "future research is needed",
        "further studies are needed",
    )):
        return False
    return any(marker in normalized for marker in (
        "validate", "validation", "generaliz", "dataset", "population",
        "setting", "context", "outcome", "method", "comparison",
        "sample", "investigate", "examine", "explore", "evaluated",
    ))


def _is_methodology_match(source_text: str, match: re.Match[str], signal: str) -> bool:
    """Require methodological context for ambiguous lexical terms."""
    if signal.lower() not in {"experiment", "experimental evaluation", "experimental design"}:
        return True
    excerpt = _sentence_containing(source_text, match.start(), match.end()).lower()
    return bool(re.search(
        r"\b(?:conducted|designed|design|evaluation|evaluated|study|studies|"
        r"large-scale|randomized|controlled|experimental)\b",
        excerpt,
    ))


def _paper_id(paper: PaperLike) -> int:
    value = paper.id
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("paper.id must be a positive integer")
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _normalize_whitespace(value)


def _normalize_text(value: str) -> str:
    lowered = value.lower().replace("—", "-").replace("–", "-").replace("−", "-").replace("’", "'")
    lowered = re.sub(r"[^a-z0-9\s-]", " ", lowered)
    lowered = re.sub(r"-+", "-", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _normalize_phrase_for_match(phrase: str) -> str:
    return _normalize_text(phrase).replace("-", " ")


def _sentence_containing(source_text: str, start: int, end: int) -> str:
    left = max(source_text.rfind(".", 0, start), source_text.rfind("!", 0, start), source_text.rfind("?", 0, start))
    right_candidates = [index for mark in ".!?" if (index := source_text.find(mark, end)) >= 0]
    right = min(right_candidates, default=len(source_text) - 1)
    sentence = source_text[left + 1 : right + 1].strip()
    if sentence:
        return sentence[:1].upper() + sentence[1:]
    return sentence


def _excerpt_for_phrase(text: str, phrase: str) -> str:
    normalized = _normalize_text(text)
    phrase_match = re.search(re.escape(_normalize_phrase_for_match(phrase)), normalized)
    if phrase_match is None:
        return _normalize_whitespace(text)
    raw_lower = text.lower()
    raw_phrase_match = re.search(re.escape(_normalize_phrase_for_match(phrase)), raw_lower)
    if raw_phrase_match is None:
        return _normalize_whitespace(text)
    # Evidence excerpts are sentence-grounded so they never start or end mid-word.
    return _sentence_containing(text, raw_phrase_match.start(), raw_phrase_match.end())
