from types import SimpleNamespace

from app.analysis import EvidenceCategory
from app.analysis.evidence_extractor import extract_evidence, extract_key_themes


def paper(paper_id: int = 1, title: str = "", abstract: str | None = None):
    return SimpleNamespace(id=paper_id, title=title, abstract=abstract)


def category_items(items, category):
    return [item for item in items if item.evidence_type is category]


def test_title_only_tokens_do_not_become_topics() -> None:
    evidence = extract_evidence([
        paper(
            1,
            title="3d Printed Operando Acoustic Holder For Coin Cell Batteries",
            abstract=None,
        )
    ])
    assert evidence == []


def test_abstract_generates_meaningful_topics_but_not_stopwords() -> None:
    evidence = extract_evidence([
        paper(
            1,
            title="Nanoindentation software",
            abstract="The study evaluates nanoindentation analysis software for mechanical testing and validation.",
        )
    ])
    claims = [item.claim for item in category_items(evidence, EvidenceCategory.TOPIC)]
    assert claims
    assert not any("for" in claim.lower() for claim in claims)
    assert not any("study" in claim.lower() for claim in claims)
    assert any("nanoindentation" in claim.lower() for claim in claims)


def test_explicit_categories_are_extracted() -> None:
    text = (
        "We conducted a randomized experiment with students and measured accuracy. "
        "The method was compared with a baseline using a public dataset. "
        "A limitation is the small sample size. Future work should investigate teachers."
    )
    evidence = extract_evidence([paper(title="Machine Learning Study", abstract=text)])

    for category in (
        EvidenceCategory.METHODOLOGY,
        EvidenceCategory.POPULATION_CONTEXT,
        EvidenceCategory.OUTCOME,
        EvidenceCategory.COMPARISON,
        EvidenceCategory.DATASET,
        EvidenceCategory.LIMITATION,
        EvidenceCategory.FUTURE_WORK,
    ):
        assert category_items(evidence, category)


def test_qualitative_spatial_language_is_not_methodology() -> None:
    evidence = extract_evidence([
        paper(1, abstract="The system answers qualitative spatial questions.")
    ])
    assert category_items(evidence, EvidenceCategory.METHODOLOGY) == []


def test_qualitative_study_is_methodology() -> None:
    evidence = extract_evidence([
        paper(1, abstract="We conducted a qualitative study using interviews.")
    ])
    assert category_items(evidence, EvidenceCategory.METHODOLOGY)


def test_generic_terms_are_not_promoted_to_themes() -> None:
    papers = [
        paper(1, title="Cellulose foams for compression", abstract="Cellulose foams improve compressive performance."),
        paper(2, title="Textile wearables for health monitoring", abstract="Textile wearables track motion."),
    ]
    themes = extract_key_themes(papers)

    phrases = {theme["phrase"] for theme in themes}
    assert "cellulose foam" in phrases
    assert "textile wearable" in phrases
    assert "performance" not in phrases
    assert "for" not in phrases


def test_duplicate_evidence_is_avoided() -> None:
    evidence = extract_evidence([paper(title="Dataset dataset", abstract="The dataset is public.")])
    dataset = category_items(evidence, EvidenceCategory.DATASET)
    assert len(dataset) == 1


def test_empty_text_is_safe() -> None:
    assert extract_evidence([paper(), paper(title="")]) == []


def test_multiple_papers_remain_separate() -> None:
    evidence = extract_evidence([
        paper(1, title="Accuracy Study", abstract="Accuracy is measured."),
        paper(2, title="Precision Study", abstract="Precision is measured."),
    ])
    assert {item.paper_id for item in evidence} == {1, 2}


def test_sentence_fragments_are_not_topics() -> None:
    evidence = extract_evidence([
        paper(
            1,
            abstract=(
                "Although geospatial question answering is difficult, the systems comprise three main "
                "components and increasingly strong AI methods are evaluated."
            ),
        )
    ])
    claims = [item.claim.lower() for item in category_items(evidence, EvidenceCategory.TOPIC)]
    assert not any(
        fragment in claim
        for claim in claims
        for fragment in (
            "although geospatial question",
            "comprise three main",
            "increasingly strong ai",
        )
    )


def test_topic_excerpts_use_complete_source_sentences() -> None:
    evidence = extract_evidence([
        paper(1, abstract="We study automated theorem proving. It improves premise selection.")
    ])
    topics = category_items(evidence, EvidenceCategory.TOPIC)
    assert topics
    assert all(item.source_excerpt.endswith(".") for item in topics)
    assert all(not item.source_excerpt.startswith("tudy") for item in topics)


def test_domain_phrases_can_survive_structural_topic_filtering() -> None:
    evidence = extract_evidence([
        paper(
            1,
            abstract="We evaluate automated theorem proving and qualitative spatial reasoning.",
        )
    ])
    claims = [item.claim.lower() for item in category_items(evidence, EvidenceCategory.TOPIC)]
    assert any("automated theorem" in claim for claim in claims)
    assert any("spatial reasoning" in claim for claim in claims)


def test_topic_phrases_do_not_expose_action_fragments() -> None:
    evidence = extract_evidence([
        paper(
            1,
            abstract="A geoparser extracts place semantic information and generates final answers.",
        )
    ])
    claims = [item.claim.lower() for item in category_items(evidence, EvidenceCategory.TOPIC)]
    assert not any("extract place semantic" in claim or "generate final answer" in claim for claim in claims)


def test_outcome_signal_does_not_claim_a_result() -> None:
    evidence = extract_evidence([
        paper(1, abstract="Accuracy was measured on the validation set."),
    ])
    outcomes = category_items(evidence, EvidenceCategory.OUTCOME)
    assert len(outcomes) == 1
    assert outcomes[0].claim == "Detected outcome signal: accuracy"
    assert "increased" not in outcomes[0].claim.lower()


def test_concrete_future_work_is_extracted_but_generic_future_work_is_not_a_gap_signal() -> None:
    evidence = extract_evidence([
        paper(1, abstract="Future work should validate the method on additional datasets."),
    ])
    future = category_items(evidence, EvidenceCategory.FUTURE_WORK)
    assert future
    assert future[0].claim == "Future-work target: validate the method on additional datasets."
    assert "future research target" in future[0].interpretation
    assert future[0].source_excerpt


def test_quantitative_finding_is_result_oriented() -> None:
    evidence = extract_evidence([
        paper(1, abstract="The E and Vampire provers with ENIGMA modifications achieve 75% success."),
    ])
    findings = category_items(evidence, EvidenceCategory.FINDING)
    assert len(findings) == 1
    assert "75%" in findings[0].claim
    assert "success" in findings[0].claim.lower()
    assert findings[0].claim.startswith("Reported finding: The E and Vampire provers")
    assert findings[0].source_excerpt == "The E and Vampire provers with ENIGMA modifications achieve 75% success."


def test_multiple_quantitative_results_are_retained_in_one_finding() -> None:
    evidence = extract_evidence([
        paper(
            1,
            abstract=(
                "AI/TP methods automatically prove about 60% of Mizar theorems in the hammer setting, "
                "increasing to 75% when using premises from human-written Mizar proofs."
            ),
        ),
    ])
    findings = category_items(evidence, EvidenceCategory.FINDING)
    assert len(findings) == 1
    assert "60%" in findings[0].claim
    assert "75%" in findings[0].claim


def test_mizar_findings_keep_subject_and_result_context() -> None:
    evidence = extract_evidence([
        paper(
            1,
            abstract=(
                "As a present to Mizar on its 50th anniversary, we develop an AI/TP system that "
                "automatically proves about 60% of the Mizar theorems in the hammer setting. "
                "We also automatically prove 75% of the Mizar theorems when the automated provers "
                "are helped by using only the premises used in the human-written Mizar proofs."
            ),
        )
    ])
    claims = [item.claim for item in category_items(evidence, EvidenceCategory.FINDING)]
    assert claims[0] == "Reported finding: AI/TP system that automatically proves about 60% of the Mizar theorems in the hammer setting."
    assert claims[1] == "Reported finding: The automated provers prove 75% of the Mizar theorems when helped using only the premises used in the human-written Mizar proofs."


def test_methodology_only_sentence_is_not_a_finding() -> None:
    evidence = extract_evidence([
        paper(1, abstract="We introduce the ENIGMA system."),
    ])
    assert category_items(evidence, EvidenceCategory.FINDING) == []
