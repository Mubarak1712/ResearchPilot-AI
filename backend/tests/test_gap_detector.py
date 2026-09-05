from types import SimpleNamespace

from app.analysis import EvidenceCategory
from app.analysis.gap_detector import detect_candidate_gaps, detect_corpus_coherence
from app.analysis.schemas import EvidenceItem, GapCategory


def evidence(paper_id: int, category: EvidenceCategory, claim: str) -> EvidenceItem:
    return EvidenceItem(
        paper_id=paper_id,
        evidence_type=category,
        claim=claim,
        source_excerpt=claim,
        source_field="abstract",
        confidence=0.95,
    )


def test_empty_and_single_paper_evidence_do_not_create_gaps() -> None:
    assert detect_candidate_gaps([]) == []
    assert detect_candidate_gaps([evidence(1, EvidenceCategory.TOPIC, "Topic phrase: nanoindentation")]) == []


def test_topic_concentration_is_not_labelled_as_underrepresentation() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.TOPIC, "Topic phrase: nanoindentation"),
        evidence(2, EvidenceCategory.TOPIC, "Topic phrase: nanoindentation"),
        evidence(3, EvidenceCategory.TOPIC, "Topic phrase: nanoindentation"),
    ])
    assert gaps == []


def test_title_word_or_stopword_is_not_a_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.TOPIC, "Topic phrase: for"),
        evidence(2, EvidenceCategory.TOPIC, "Topic phrase: for"),
        evidence(3, EvidenceCategory.TOPIC, "Topic phrase: 3d"),
    ])
    assert gaps == []


def test_explicit_limitation_creates_evidence_backed_gap() -> None:
    items = [
        evidence(1, EvidenceCategory.LIMITATION, "The study had a small sample size and limited generalizability."),
        evidence(2, EvidenceCategory.LIMITATION, "The study had a small sample size and limited generalizability."),
    ]
    gaps = detect_candidate_gaps(items)
    assert len(gaps) == 1
    assert gaps[0].category is GapCategory.METHODOLOGICAL_LIMITATION
    assert gaps[0].supporting_paper_ids == [1, 2]


def test_explicit_future_work_creates_validation_gap() -> None:
    items = [
        evidence(1, EvidenceCategory.FUTURE_WORK, "Future work should validate the method in a real-world setting."),
        evidence(2, EvidenceCategory.FUTURE_WORK, "Future work should validate the method in a real-world setting."),
    ]
    gaps = detect_candidate_gaps(items)
    assert len(gaps) == 1
    assert gaps[0].category is GapCategory.VALIDATION_GAP


def test_generic_future_work_does_not_create_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.FUTURE_WORK, "More research is needed."),
        evidence(2, EvidenceCategory.FUTURE_WORK, "More research is needed."),
    ])
    assert gaps == []


def test_generic_limitation_mention_does_not_create_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.LIMITATION, "Limitations are discussed."),
        evidence(2, EvidenceCategory.LIMITATION, "Limitations are discussed."),
    ])
    assert gaps == []


def test_repeated_limitations_in_unrelated_papers_are_not_combined() -> None:
    papers = [
        SimpleNamespace(id=1, title="Medical imaging", abstract="Medical imaging method has limited generalizability."),
        SimpleNamespace(id=2, title="Robotics control", abstract="Robotics control method has limited generalizability."),
    ]
    items = [
        evidence(1, EvidenceCategory.TOPIC, "Topic phrase: medical imaging"),
        evidence(1, EvidenceCategory.LIMITATION, "The medical imaging method has limited generalizability."),
        evidence(2, EvidenceCategory.TOPIC, "Topic phrase: robotics control"),
        evidence(2, EvidenceCategory.LIMITATION, "The robotics control method has limited generalizability."),
    ]
    assert detect_candidate_gaps(items, papers) == []


def test_one_paper_coherence_is_insufficient() -> None:
    coherence = detect_corpus_coherence([
        evidence(1, EvidenceCategory.TOPIC, "Topic phrase: medical imaging"),
    ])
    assert coherence["status"] == "insufficient"
    assert "one selected paper" in coherence["summary"].lower()


def test_contradictory_evidence_creates_inconsistency_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.CONTRADICTION, "Method A improved performance under the stated conditions."),
        evidence(2, EvidenceCategory.CONTRADICTION, "Method A performed worse under the same conditions."),
    ])
    assert len(gaps) == 1
    assert gaps[0].category is GapCategory.INCONSISTENT_EVIDENCE


def test_comparable_contradiction_requires_matching_method_outcome_and_polarity() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.CONTRADICTION, "Method A improved performance under the same conditions."),
        evidence(2, EvidenceCategory.CONTRADICTION, "Method A performed worse performance under the same conditions."),
    ])
    assert len(gaps) == 1


def test_different_outcomes_do_not_create_contradiction_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.CONTRADICTION, "Method A improved performance."),
        evidence(2, EvidenceCategory.CONTRADICTION, "Method A improved durability."),
    ])
    assert gaps == []


def test_different_contexts_do_not_create_contradiction_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.CONTRADICTION, "Method A improved performance in material X."),
        evidence(2, EvidenceCategory.CONTRADICTION, "Method A reduced performance in material Y."),
    ])
    assert gaps == []


def test_single_contradiction_item_does_not_create_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.CONTRADICTION, "Method A improved performance."),
    ])
    assert gaps == []


def test_unrelated_contradiction_domains_do_not_create_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.CONTRADICTION, "Method A improved performance in material X."),
        evidence(2, EvidenceCategory.CONTRADICTION, "Method B reduced durability in material Y."),
        evidence(3, EvidenceCategory.CONTRADICTION, "Method C improved accuracy in population Z."),
    ])
    assert gaps == []


def test_repeated_accuracy_mentions_do_not_create_contradiction() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.OUTCOME, "Detected outcome signal: accuracy"),
        evidence(2, EvidenceCategory.OUTCOME, "Detected outcome signal: accuracy"),
    ])
    assert gaps == []


def test_measured_and_unreported_accuracy_do_not_create_contradiction() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.OUTCOME, "Accuracy was measured."),
        evidence(2, EvidenceCategory.OUTCOME, "Accuracy was not reported."),
    ])
    assert gaps == []


def test_duplicate_records_do_not_inflate_evidence_count() -> None:
    items = [
        evidence(1, EvidenceCategory.LIMITATION, "The study had a small sample size and limited generalizability."),
        evidence(1, EvidenceCategory.LIMITATION, "The study had a small sample size and limited generalizability."),
        evidence(2, EvidenceCategory.LIMITATION, "The study had a small sample size and limited generalizability."),
    ]
    gaps = detect_candidate_gaps(items)
    assert len(gaps) == 1
    assert gaps[0].supporting_paper_ids == [1, 2]
    assert len(gaps[0].observed_evidence) == 1


def test_one_paper_cannot_create_field_wide_gap() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.FUTURE_WORK, "Future work should investigate validation."),
    ])
    assert gaps == []


def test_heterogeneous_corpus_has_low_coherence_warning() -> None:
    items = [
        evidence(1, EvidenceCategory.TOPIC, "Topic phrase: nanoindentation analysis"),
        evidence(2, EvidenceCategory.TOPIC, "Topic phrase: battery acoustic holder"),
        evidence(3, EvidenceCategory.TOPIC, "Topic phrase: cross laminated timber treatment"),
    ]
    coherence = detect_corpus_coherence(items)
    assert coherence["status"] == "low"
    assert "substantially different" in coherence["summary"].lower()


def test_missing_evidence_rejected() -> None:
    items = [
        evidence(1, EvidenceCategory.TOPIC, "Topic phrase: methodology"),
        evidence(2, EvidenceCategory.TOPIC, "Topic phrase: methodology"),
    ]
    assert detect_candidate_gaps(items) == []


def test_unsupported_inference_is_rejected() -> None:
    items = [
        evidence(1, EvidenceCategory.TOPIC, "Topic phrase: performance"),
        evidence(2, EvidenceCategory.TOPIC, "Topic phrase: performance"),
    ]
    assert detect_candidate_gaps(items) == []


def test_confidence_is_not_static() -> None:
    small = detect_candidate_gaps([
        evidence(1, EvidenceCategory.LIMITATION, "The study had limited generalizability."),
        evidence(2, EvidenceCategory.LIMITATION, "The study had limited generalizability."),
    ])
    stronger = detect_candidate_gaps([
        evidence(1, EvidenceCategory.LIMITATION, "The study had a small sample size and insufficient validation across multiple settings."),
        evidence(2, EvidenceCategory.LIMITATION, "The study had a small sample size and insufficient validation across multiple settings."),
        evidence(3, EvidenceCategory.LIMITATION, "The study had a small sample size and insufficient validation across multiple settings."),
    ])
    assert len(small) == 1 and len(stronger) == 1
    assert stronger[0].confidence > small[0].confidence
    assert stronger[0].confidence_breakdown.specificity > small[0].confidence_breakdown.specificity
    assert stronger[0].confidence_breakdown.corpus_size_penalty < small[0].confidence_breakdown.corpus_size_penalty


def test_gap_claims_include_excerpts_and_why_its_missing() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.LIMITATION, "The sample size was small and the method lacked validation."),
        evidence(2, EvidenceCategory.LIMITATION, "The sample size was small and the method lacked validation."),
    ])
    assert gaps
    assert gaps[0].observed_evidence
    assert "validation" in " ".join(gaps[0].observed_evidence).lower()
    assert "selected corpus" in gaps[0].pattern.lower() or "selected corpus" in gaps[0].statement.lower()


def test_semantically_different_claims_are_not_collapsed_into_generic_gap_statements() -> None:
    gaps = detect_candidate_gaps([
        evidence(1, EvidenceCategory.LIMITATION, "The sample size was small and generalizability was limited."),
        evidence(2, EvidenceCategory.LIMITATION, "The sample size was small and generalizability was limited."),
        evidence(3, EvidenceCategory.FUTURE_WORK, "Future work should validate the method in a real-world setting."),
        evidence(4, EvidenceCategory.FUTURE_WORK, "Future work should validate the method in a real-world setting."),
    ])
    assert gaps
    assert not any("recurring methodological limitations" in gap.statement.lower() for gap in gaps)
    assert any("validation" in gap.statement.lower() or "generaliz" in gap.statement.lower() or "sample size" in gap.statement.lower() for gap in gaps)
