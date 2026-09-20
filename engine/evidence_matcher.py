"""
Evidence Matcher & Role Context Extractor.
Extracts verbatim proof sentences from employment history bullets.
Differentiates shallow keyword stuffing from real production usage.
"""

import re
from typing import List, Dict, Any, Tuple
from criteria.schema import CompetencyCriterion, CompetencyMatch
from parser.timeline_extractor import CandidateTimeline


class EvidenceMatcher:
    @classmethod
    def evaluate_competencies(
        cls,
        competencies: List[CompetencyCriterion],
        timeline: CandidateTimeline,
        raw_text: str
    ) -> Tuple[List[CompetencyMatch], float]:
        """
        Evaluates candidate against core competencies and extracts verbatim evidence snippets.
        Returns a list of CompetencyMatch objects and an aggregate score (0 to 100).
        """
        matches: List[CompetencyMatch] = []
        total_weight = 0.0
        weighted_score_accum = 0.0

        for comp in competencies:
            match = cls._match_single_competency(comp, timeline, raw_text)
            matches.append(match)
            total_weight += comp.weight
            weighted_score_accum += (match.score * comp.weight)

        if not competencies:
            return [], 100.0

        overall_score = (weighted_score_accum / total_weight) if total_weight > 0 else 100.0
        return matches, round(overall_score, 1)

    @classmethod
    def _match_single_competency(
        cls,
        comp: CompetencyCriterion,
        timeline: CandidateTimeline,
        raw_text: str
    ) -> CompetencyMatch:
        synonyms = comp.synonyms or [comp.name.lower()]
        snippets: List[str] = []
        tenure_months = 0

        # 1. Search within structured job positions (high credibility)
        for pos in timeline.positions:
            pos_text = f"{pos.company} {pos.title} {' '.join(pos.bullet_points)}"
            has_match = False

            for bullet in pos.bullet_points:
                if any(re.search(rf"\b{re.escape(syn.lower())}\b", bullet, re.IGNORECASE) for syn in synonyms):
                    snippets.append(f"[{pos.company} | {pos.title}] {bullet.strip()}")
                    has_match = True

            if has_match:
                tenure_months += pos.tenure_months

        # 2. If not found in bullets, check raw resume text (lower credibility)
        if not snippets:
            for sentence in raw_text.splitlines():
                if any(re.search(rf"\b{re.escape(syn.lower())}\b", sentence, re.IGNORECASE) for syn in synonyms):
                    cleaned = sentence.strip(" -•*")
                    if len(cleaned) > 15:
                        snippets.append(f"[Resume Text] {cleaned}")
                        break

        measured_years = round(tenure_months / 12.0, 2)
        required_years = comp.min_tenure_years

        # Scoring logic:
        # If required tenure > 0, score based on measured vs required
        # If required tenure == 0, binary presence with context bonus
        score = 0.0
        is_satisfied = False

        if snippets:
            if required_years > 0:
                ratio = measured_years / required_years
                score = min(100.0, ratio * 100.0)
                is_satisfied = (ratio >= 0.8) # Within 80% of requirement
            else:
                score = 90.0 if any("[" in s and "Resume Text" not in s for s in snippets) else 60.0
                is_satisfied = True
        else:
            score = 0.0
            is_satisfied = False

        return CompetencyMatch(
            criterion_id=comp.id,
            name=comp.name,
            is_satisfied=is_satisfied,
            measured_tenure_years=measured_years,
            required_tenure_years=required_years,
            evidence_snippets=snippets[:3], # Top 3 proof snippets
            score=round(score, 1)
        )
