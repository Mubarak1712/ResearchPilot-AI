"""Pure domain schemas for future research gap analysis."""

from .evidence_extractor import extract_evidence
from .gap_detector import detect_candidate_gaps
from .schemas import (
    AnalysisLimitations,
    AnalysisRequest,
    AnalysisResult,
    AnalysisStatus,
    CandidateResearchGap,
    EvidenceCategory,
    EvidenceItem,
    GapCategory,
    MethodologyVersion,
    SelectedPaperInput,
)

__all__ = [
    "AnalysisLimitations",
    "extract_evidence",
    "detect_candidate_gaps",
    "AnalysisRequest",
    "AnalysisResult",
    "AnalysisStatus",
    "CandidateResearchGap",
    "EvidenceCategory",
    "EvidenceItem",
    "GapCategory",
    "MethodologyVersion",
    "SelectedPaperInput",
]
