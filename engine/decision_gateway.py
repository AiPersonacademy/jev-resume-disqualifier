"""
Unified Decision Gateway for Resume Disqualification.
Coordinates parsing, deterministic knockouts, contextual evidence matching,
and TypeSafe AI calibrated decision gating.
"""

import time
import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime

from parser.doc_reader import DocumentReader
from parser.timeline_extractor import TimelineExtractor
from criteria.schema import JobProfile, EvaluationResult, EvaluationStatus
from engine.knockout_rules import KnockoutEvaluator
from engine.evidence_matcher import EvidenceMatcher


TYPESAFE_API_URL = os.getenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai/v1/systemone")
TYPESAFE_API_KEY = os.getenv("TYPESAFE_API_KEY", "")


class ResumeEvaluationEngine:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or TYPESAFE_API_KEY

    def evaluate_file(self, file_path: str, profile: JobProfile) -> EvaluationResult:
        """Reads document from disk and runs complete evaluation pipeline."""
        doc = DocumentReader.read_file(file_path)
        return self.evaluate_text(
            raw_text=doc["raw_text"],
            filename=doc["filename"],
            profile=profile
        )

    def evaluate_bytes(self, data: bytes, filename: str, profile: JobProfile) -> EvaluationResult:
        """Reads document bytes and runs complete evaluation pipeline."""
        doc = DocumentReader.read_bytes(data, filename=filename)
        return self.evaluate_text(
            raw_text=doc["raw_text"],
            filename=doc["filename"],
            profile=profile
        )

    def evaluate_text(self, raw_text: str, filename: str, profile: JobProfile) -> EvaluationResult:
        """
        Executes the 3-Layer High-Accuracy Evaluation Pipeline:
        Layer 1: Document & Timeline Date Math
        Layer 2: Hard Knockout Verification Gates
        Layer 3: Evidence-Linked Competency & Calibrated Decision
        """
        audit_trail: list[str] = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Parse Candidate Timeline & Tenure
        timeline = TimelineExtractor.parse_timeline(raw_text)
        candidate_name = self._infer_candidate_name(raw_text, filename)
        audit_trail.append(f"Parsed {len(timeline.positions)} employment periods. Cumulative non-overlapping tenure: {timeline.total_calendar_years} years.")

        # 2. Layer 2: Hard Knockout Verification
        violations = KnockoutEvaluator.evaluate_knockouts(profile.knockouts, timeline, raw_text)

        # 3. Layer 3: Competency & Evidence Matching
        comp_matches, match_score = EvidenceMatcher.evaluate_competencies(profile.competencies, timeline, raw_text)
        audit_trail.append(f"Evaluated {len(profile.competencies)} core competencies. Base match score: {match_score}/100.")

        # 4. Extract Timeline Breakdown
        timeline_breakdown = []
        for p in timeline.positions:
            timeline_breakdown.append({
                "company": p.company,
                "title": p.title,
                "start_date": str(p.start_date) if p.start_date else "Unknown",
                "end_date": str(p.end_date) if p.end_date else ("Present" if p.is_current else "Unknown"),
                "tenure_months": p.tenure_months,
                "tenure_years": p.tenure_years,
                "is_current": p.is_current,
                "bullet_count": len(p.bullet_points)
            })

        # 5. Base Decision Synthesis
        status = EvaluationStatus.ADVANCE
        confidence = 0.95

        if violations:
            status = EvaluationStatus.DISQUALIFIED
            audit_trail.append(f"DISQUALIFIED: Triggered {len(violations)} mandatory knockout violation(s).")
            for v in violations:
                audit_trail.append(f"  • [{v.category}] {v.criterion_name}: {v.deficit_reason}")
        elif match_score < 45.0:
            status = EvaluationStatus.DISQUALIFIED
            audit_trail.append(f"DISQUALIFIED: Overall competency match score ({match_score}%) falls below 45% minimum threshold.")
        elif 45.0 <= match_score < 70.0 or any(g["gap_months"] >= 12 for g in timeline.gaps_months):
            status = EvaluationStatus.MANUAL_REVIEW
            audit_trail.append(f"FLAGGED FOR MANUAL REVIEW: Moderate fit score ({match_score}%) or notable career gaps.")
        else:
            status = EvaluationStatus.ADVANCE
            audit_trail.append(f"ADVANCE: Passed all {len(profile.knockouts)} knockout gates and achieved {match_score}% competency score.")

        # 6. Live TypeSafe AI System One Gating & Telemetry (Active API Integration)
        api_telemetry = {}
        if self.api_key:
            api_res = self._call_typesafe_eval(candidate_name, profile.title, match_score, violations, comp_matches)
            if api_res:
                api_telemetry = api_res
                # If deterministic status was borderline or manual review, allow calibrated API decision to decide
                if status == EvaluationStatus.MANUAL_REVIEW and api_res.get("verdict_status"):
                    status = EvaluationStatus(api_res["verdict_status"])
                    confidence = api_res.get("confidence", 0.9)
                audit_trail.append(
                    f"TypeSafe AI System One Telemetry: Model={api_res.get('model')} | "
                    f"Decision={api_res.get('choice')} | Conf={api_res.get('confidence')}% | "
                    f"Latency={api_res.get('latency_ms')}ms"
                )

        return EvaluationResult(
            candidate_name=candidate_name,
            filename=filename,
            status=status,
            overall_match_score=match_score,
            total_calendar_years=timeline.total_calendar_years,
            knockout_violations=violations,
            competency_matches=comp_matches,
            audit_trail=audit_trail,
            confidence=confidence,
            evaluated_at=now_str,
            api_telemetry=api_telemetry,
            timeline_breakdown=timeline_breakdown,
            raw_resume_text=raw_text
        )

    @staticmethod
    def _infer_candidate_name(text: str, filename: str) -> str:
        """Heuristically infers candidate name from top of resume or filename."""
        first_lines = [l.strip() for l in text.splitlines()[:4] if l.strip()]
        for line in first_lines:
            # Avoid headings like "RESUME", "CURRICULUM VITAE", contact headers
            clean = line.strip("# *:")
            words = clean.split()
            if 2 <= len(words) <= 4 and not any(char in clean for char in ["@", "http", "www", ".com", "|", "/", "+"]):
                if not any(stop in clean.lower() for stop in ["resume", "curriculum", "experience", "education", "profile", "summary"]):
                    return clean

        # Fallback to filename
        base = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
        return base or "Candidate"

    def _call_typesafe_eval(
        self,
        candidate_name: str,
        job_title: str,
        score: float,
        violations: list,
        matches: list
    ) -> Optional[Dict[str, Any]]:
        """Invokes TypeSafe AI System One calibrated micro-decision gateway."""
        t0 = time.time()
        try:
            violation_summary = ", ".join([v.criterion_name for v in violations]) if violations else "None"
            state_text = (
                f"Candidate {candidate_name} applying for {job_title}. "
                f"Verified cumulative tenure: {sum(m.measured_tenure_years for m in matches):.1f} yrs. "
                f"Competency score: {score}%. "
                f"Mandatory knockout violations: {len(violations)} ({violation_summary}). "
                f"Satisfied competencies: {sum(1 for m in matches if m.is_satisfied)}/{len(matches)}."
            )
            payload = {
                "model": "jev-latest",
                "state": state_text,
                "questions": {
                    "decision": {
                        "type": "choice",
                        "instructions": "Determine if candidate should be ADVANCED, DISQUALIFIED, or sent to MANUAL_REVIEW.",
                        "criteria": {
                            "ADVANCE": "Sufficient technical fit with no disqualifying flaws",
                            "DISQUALIFIED": "Inadequate qualifications or critical deficiencies",
                            "MANUAL_REVIEW": "Borderline profile requiring human judgment"
                        }
                    }
                }
            }
            resp = requests.post(
                TYPESAFE_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=4.0
            )
            latency_ms = int((time.time() - t0) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                ans = data.get("answers", {}).get("decision", {})
                choice = ans.get("choice")
                conf = float(ans.get("confidence", 0.85))

                verdict_status = None
                if choice == "ADVANCE":
                    verdict_status = EvaluationStatus.ADVANCE
                elif choice == "DISQUALIFIED":
                    verdict_status = EvaluationStatus.DISQUALIFIED
                elif choice == "MANUAL_REVIEW":
                    verdict_status = EvaluationStatus.MANUAL_REVIEW

                return {
                    "provider": "TypeSafe AI System One",
                    "model": data.get("model", "jev-1.13.0"),
                    "choice": choice,
                    "confidence": round(conf * 100.0, 1),
                    "latency_ms": latency_ms,
                    "probabilities": ans.get("probabilities", {}),
                    "usage": data.get("usage", {}),
                    "verdict_status": verdict_status.value if verdict_status else None
                }
        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            return {
                "provider": "TypeSafe AI System One",
                "error": str(e),
                "latency_ms": latency_ms,
                "model": "jev-offline"
            }
        return None
