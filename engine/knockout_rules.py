"""
Deterministic Knockout Rule Evaluator.
Executes zero-compromise gates against candidate timelines and credentials.
Guarantees 100% auditable rejection justification with exact deficit math.
"""

import re
from typing import List, Optional, Tuple
from criteria.schema import KnockoutCriterion, KnockoutViolation, KnockoutCategory
from parser.timeline_extractor import CandidateTimeline


SPONSORSHIP_RED_FLAGS = [
    r"require(?:s)?\s+(?:visa\s+)?sponsorship",
    r"will\s+require\s+sponsorship",
    r"h-?1b\s+(?:visa|transfer|holder)",
    r"f-?1\s+(?:opt|cpt)",
    r"seeking\s+sponsorship"
]

AUTHORIZED_INDICATORS = [
    r"u\.?s\.?\s+citizen(?:ship)?",
    r"permanent\s+resident",
    r"green\s+card",
    r"authorized\s+to\s+work\s+in\s+(?:the\s+)?u\.?s\.?",
    r"no\s+sponsorship\s+required"
]


class KnockoutEvaluator:
    @classmethod
    def evaluate_knockouts(
        cls,
        knockouts: List[KnockoutCriterion],
        timeline: CandidateTimeline,
        raw_text: str
    ) -> List[KnockoutViolation]:
        """
        Evaluates all knockout criteria. Returns a list of violations (if empty, all passed).
        """
        violations: List[KnockoutViolation] = []

        for ko in knockouts:
            if not getattr(ko, 'enabled', True):
                continue
            violation = cls._evaluate_single_knockout(ko, timeline, raw_text)
            if violation:
                violations.append(violation)

        return violations

    @classmethod
    def _evaluate_single_knockout(
        cls,
        ko: KnockoutCriterion,
        timeline: CandidateTimeline,
        raw_text: str
    ) -> Optional[KnockoutViolation]:
        cat = ko.category

        if cat == KnockoutCategory.TOTAL_TENURE:
            return cls._eval_total_tenure(ko, timeline)
        elif cat == KnockoutCategory.SKILL_TENURE:
            return cls._eval_skill_tenure(ko, timeline, raw_text)
        elif cat == KnockoutCategory.VISA:
            return cls._eval_visa_authorization(ko, raw_text)
        elif cat in (KnockoutCategory.MANDATORY_LICENSE, KnockoutCategory.CLEARANCE, KnockoutCategory.MANDATORY_DEGREE):
            return cls._eval_keyword_credential(ko, raw_text)
        elif cat == KnockoutCategory.LOCATION:
            return cls._eval_location(ko, raw_text)
        elif cat == KnockoutCategory.CUSTOM:
            return cls._eval_custom(ko, timeline, raw_text)

        return None

    @staticmethod
    def _eval_total_tenure(ko: KnockoutCriterion, timeline: CandidateTimeline) -> Optional[KnockoutViolation]:
        required_years = ko.min_value or 0.0
        candidate_years = timeline.total_calendar_years

        if candidate_years < required_years:
            deficit = round(required_years - candidate_years, 2)
            return KnockoutViolation(
                criterion_id=ko.id,
                criterion_name=ko.name,
                category=ko.category.value,
                requirement_text=ko.requirement_text,
                resume_evidence=f"Total cumulative employment timeline across {len(timeline.positions)} verified positions: {candidate_years} years.",
                deficit_reason=f"Experience Tenure Deficit: -{deficit} years (Candidate has {candidate_years} yrs vs mandatory minimum of {required_years} yrs).",
                severity="CRITICAL"
            )
        return None

    @classmethod
    def _eval_skill_tenure(cls, ko: KnockoutCriterion, timeline: CandidateTimeline, raw_text: str) -> Optional[KnockoutViolation]:
        required_years = ko.min_value or 1.0
        target_kws = ko.target_keywords or [ko.name.lower()]

        # Calculate actual cumulative tenure for roles where the skill is mentioned
        matched_months = 0
        matching_roles = []

        for p in timeline.positions:
            role_text = f"{p.company} {p.title} {' '.join(p.bullet_points)}".lower()
            if any(re.search(rf"\b{re.escape(kw.lower())}\b", role_text) for kw in target_kws):
                matched_months += p.tenure_months
                matching_roles.append(f"{p.company} ({p.title}, {p.tenure_years} yrs)")

        measured_years = round(matched_months / 12.0, 2)

        if measured_years < required_years:
            deficit = round(required_years - measured_years, 2)
            roles_desc = ", ".join(matching_roles) if matching_roles else "Not mentioned in any verified employment role."
            return KnockoutViolation(
                criterion_id=ko.id,
                criterion_name=ko.name,
                category=ko.category.value,
                requirement_text=ko.requirement_text,
                resume_evidence=f"Demonstrated production skill tenure: {measured_years} years. Identified in: {roles_desc}",
                deficit_reason=f"Skill Tenure Deficit: -{deficit} years in '{ko.name}' (Candidate has {measured_years} yrs vs required {required_years} yrs).",
                severity="CRITICAL"
            )
        return None

    @staticmethod
    def _eval_visa_authorization(ko: KnockoutCriterion, raw_text: str) -> Optional[KnockoutViolation]:
        text_lower = raw_text.lower()

        # Check for explicit sponsorship requirement flags in candidate text
        has_sponsorship_flag = any(re.search(pat, text_lower) for pat in SPONSORSHIP_RED_FLAGS)
        has_authorized_flag = any(re.search(pat, text_lower) for pat in AUTHORIZED_INDICATORS)

        if has_sponsorship_flag and not has_authorized_flag:
            return KnockoutViolation(
                criterion_id=ko.id,
                criterion_name=ko.name,
                category=ko.category.value,
                requirement_text=ko.requirement_text,
                resume_evidence="Resume explicitly indicates candidate requires visa sponsorship (e.g., H1B / F1 OPT / Sponsorship needed).",
                deficit_reason="Visa Ineligibility: Position strictly does not provide visa sponsorship.",
                severity="CRITICAL"
            )

        if ko.strict_silence_fails and not has_authorized_flag:
            return KnockoutViolation(
                criterion_id=ko.id,
                criterion_name=ko.name,
                category=ko.category.value,
                requirement_text=ko.requirement_text,
                resume_evidence="No work authorization or US citizenship statement found in resume.",
                deficit_reason="Missing Mandatory Proof: Job requires explicit US citizenship or permanent residency without sponsorship.",
                severity="HIGH"
            )

        return None

    @staticmethod
    def _eval_keyword_credential(ko: KnockoutCriterion, raw_text: str) -> Optional[KnockoutViolation]:
        target_kws = ko.target_keywords
        text_lower = raw_text.lower()

        found = any(re.search(rf"\b{re.escape(kw.lower())}\b", text_lower) for kw in target_kws)

        if not found:
            return KnockoutViolation(
                criterion_id=ko.id,
                criterion_name=ko.name,
                category=ko.category.value,
                requirement_text=ko.requirement_text,
                resume_evidence=f"No mention of mandatory credentials ({', '.join(target_kws)}) found in resume text.",
                deficit_reason=f"Missing Mandatory Credential: {ko.name} is a required prerequisite for this position.",
                severity="CRITICAL"
            )
        return None

    @staticmethod
    def _eval_location(ko: KnockoutCriterion, raw_text: str) -> Optional[KnockoutViolation]:
        if not ko.target_keywords:
            return None
        text_lower = raw_text.lower()
        found = any(re.search(rf"\b{re.escape(kw.lower())}\b", text_lower) for kw in ko.target_keywords)
        if not found and ko.strict_silence_fails:
            return KnockoutViolation(
                criterion_id=ko.id,
                criterion_name=ko.name,
                category=ko.category.value,
                requirement_text=ko.requirement_text,
                resume_evidence=f"Resume does not confirm location proximity ({', '.join(ko.target_keywords)}).",
                deficit_reason=f"Location Knockout: Candidate location does not match mandatory geographic zone ({ko.requirement_text}).",
                severity="HIGH"
            )
        return None

    @classmethod
    def _eval_custom(cls, ko: KnockoutCriterion, timeline: CandidateTimeline, raw_text: str) -> Optional[KnockoutViolation]:
        # Check if custom rule specifies min tenure
        if ko.min_value and ko.min_value > 0:
            if ko.target_keywords:
                return cls._eval_skill_tenure(ko, timeline, raw_text)
            else:
                return cls._eval_total_tenure(ko, timeline)

        # Keyword presence requirement
        if ko.target_keywords:
            text_lower = raw_text.lower()
            found = any(re.search(rf"\b{re.escape(kw.lower())}\b", text_lower) for kw in ko.target_keywords)
            if not found and (ko.strict_silence_fails or ko.mandatory):
                return KnockoutViolation(
                    criterion_id=ko.id,
                    criterion_name=ko.name,
                    category=ko.category.value,
                    requirement_text=ko.requirement_text,
                    resume_evidence=f"No matching evidence for required keywords ({', '.join(ko.target_keywords)}) found.",
                    deficit_reason=f"Custom Knockout Violation: {ko.name} requirement not satisfied.",
                    severity="CRITICAL" if ko.mandatory else "HIGH"
                )
        return None
