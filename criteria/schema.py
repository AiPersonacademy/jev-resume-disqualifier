"""
Criteria and Evaluation Data Schema.
Defines structured classes for Knockouts, Competencies, and Evaluation Verdicts.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum


class KnockoutCategory(str, Enum):
    VISA = "VISA"
    LOCATION = "LOCATION"
    TOTAL_TENURE = "TOTAL_TENURE"
    SKILL_TENURE = "SKILL_TENURE"
    MANDATORY_DEGREE = "MANDATORY_DEGREE"
    MANDATORY_LICENSE = "MANDATORY_LICENSE"
    CLEARANCE = "CLEARANCE"
    CUSTOM = "CUSTOM"


class EvaluationStatus(str, Enum):
    DISQUALIFIED = "DISQUALIFIED"
    ADVANCE = "ADVANCE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass
class KnockoutCriterion:
    id: str
    name: str
    category: KnockoutCategory
    requirement_text: str
    min_value: Optional[float] = None
    target_keywords: List[str] = field(default_factory=list)
    mandatory: bool = True
    strict_silence_fails: bool = False  # If True, omission = instant disqualify
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass
class CompetencyCriterion:
    id: str
    name: str
    category: str
    requirement_text: str
    min_tenure_years: float = 0.0
    synonyms: List[str] = field(default_factory=list)
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JobProfile:
    job_id: str
    title: str
    company: str
    location: str
    raw_jd: str
    knockouts: List[KnockoutCriterion] = field(default_factory=list)
    competencies: List[CompetencyCriterion] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "raw_jd": self.raw_jd,
            "knockouts": [k.to_dict() for k in self.knockouts],
            "competencies": [c.to_dict() for c in self.competencies]
        }


@dataclass
class KnockoutViolation:
    criterion_id: str
    criterion_name: str
    category: str
    requirement_text: str
    resume_evidence: str
    deficit_reason: str
    severity: str = "HIGH"  # 'CRITICAL', 'HIGH'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompetencyMatch:
    criterion_id: str
    name: str
    is_satisfied: bool
    measured_tenure_years: float
    required_tenure_years: float
    evidence_snippets: List[str]
    score: float  # 0.0 to 100.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationResult:
    candidate_name: str
    filename: str
    status: EvaluationStatus
    overall_match_score: float
    total_calendar_years: float
    knockout_violations: List[KnockoutViolation] = field(default_factory=list)
    competency_matches: List[CompetencyMatch] = field(default_factory=list)
    audit_trail: List[str] = field(default_factory=list)
    confidence: float = 0.95
    evaluated_at: str = ""
    api_telemetry: Dict[str, Any] = field(default_factory=dict)
    timeline_breakdown: List[Dict[str, Any]] = field(default_factory=list)
    raw_resume_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_name": self.candidate_name,
            "filename": self.filename,
            "status": self.status.value,
            "overall_match_score": round(self.overall_match_score, 1),
            "total_calendar_years": self.total_calendar_years,
            "knockout_violations": [v.to_dict() for v in self.knockout_violations],
            "competency_matches": [m.to_dict() for m in self.competency_matches],
            "audit_trail": self.audit_trail,
            "confidence": round(self.confidence * 100.0, 1),
            "evaluated_at": self.evaluated_at,
            "api_telemetry": self.api_telemetry,
            "timeline_breakdown": self.timeline_breakdown,
            "raw_resume_text": self.raw_resume_text
        }
