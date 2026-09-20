"""
Resume Disqualifier Web Cockpit Server.
AIOHTTP backend providing:
- Web GUI serving
- REST endpoints for dynamic JD decomposition, custom knockout rule management
- Multi-file drag-and-drop batch upload handler (PDF, DOCX, TXT, MD)
- Real-time TypeSafe AI System One / Jev decision gateway integration
- CSV / JSON ATS Compliance Audit export
"""

import os
import sys
import json
import time
import uuid
import csv
import io
import requests
from pathlib import Path
from typing import List, Dict, Any
from aiohttp import web

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from criteria.extractor import CriteriaExtractor
from criteria.schema import (
    JobProfile,
    KnockoutCriterion,
    KnockoutCategory,
    EvaluationResult,
    EvaluationStatus
)
from engine.decision_gateway import ResumeEvaluationEngine, TYPESAFE_API_URL, TYPESAFE_API_KEY
from parser.doc_reader import DocumentReader

SAMPLE_JDS = {
    "senior_go": {
        "title": "Senior Distributed Systems Engineer (Go/Cloud)",
        "company": "Stripe",
        "raw_jd": """Title: Senior Distributed Systems Engineer
Company: Stripe
Location: Remote (US-only)

About the Role:
We are looking for a Senior Distributed Systems Engineer to scale our core payment ledger.

Minimum Qualifications:
- Must be authorized to work in the US without sponsorship (No visa sponsorship provided).
- Minimum 5+ years of professional software engineering experience.
- At least 3+ years of production experience in Go (Golang).
- Strong experience with distributed systems, Kafka, and cloud infrastructure (AWS or GCP).
- Experience with relational database performance and SQL tuning (PostgreSQL).
"""
    },
    "icu_nurse": {
        "title": "ICU Registered Nurse (Staff RN)",
        "company": "Northwestern Memorial Hospital",
        "raw_jd": """Position: ICU Staff Nurse
Hospital: Northwestern Memorial Hospital
Location: Chicago, IL

Qualifications:
- Active Registered Nurse (RN) license in the State of Illinois is required.
- Minimum 2+ years of acute care or ICU clinical nursing experience.
- BLS and ACLS certifications required.
- Bachelor of Science in Nursing (BSN) preferred.
"""
    },
    "cyber_security": {
        "title": "Lead Cyber Security Analyst (Clearance Required)",
        "company": "Lockheed Martin",
        "raw_jd": """Position: Lead Cyber Security Analyst
Company: Lockheed Martin
Location: Bethesda, MD

Requirements:
- Active Top Secret / TS/SCI Security Clearance is mandatory.
- Minimum 4+ years in threat hunting, incident response, or SOC operations.
- CISSP or GIAC certification required.
- Bachelor's degree in Computer Science or related field.
"""
    }
}


class ResumeDisqualifierServer:
    def __init__(self, port: int = 8990):
        self.port = port
        self.engine = ResumeEvaluationEngine()
        self.evaluated_candidates: List[EvaluationResult] = []
        self.current_profile: JobProfile = CriteriaExtractor.decompose_job_description(
            SAMPLE_JDS["senior_go"]["raw_jd"],
            title=SAMPLE_JDS["senior_go"]["title"],
            company=SAMPLE_JDS["senior_go"]["company"]
        )

    async def index_handler(self, request):
        html_path = Path(__file__).parent / "index.html"
        with open(html_path, "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")

    async def get_profile_handler(self, request):
        return web.json_response({
            "status": "success",
            "profile": self.current_profile.to_dict(),
            "sample_jds": {k: {"title": v["title"], "company": v["company"]} for k, v in SAMPLE_JDS.items()},
            "api_online": bool(self.engine.api_key),
            "candidate_count": len(self.evaluated_candidates)
        })

    async def load_sample_jd_handler(self, request):
        data = await request.json()
        key = data.get("key", "senior_go")
        if key in SAMPLE_JDS:
            sample = SAMPLE_JDS[key]
            self.current_profile = CriteriaExtractor.decompose_job_description(
                sample["raw_jd"],
                title=sample["title"],
                company=sample["company"]
            )
            return web.json_response({"status": "success", "profile": self.current_profile.to_dict()})
        return web.json_response({"status": "error", "message": "Unknown sample JD key"}, status=400)

    async def update_jd_handler(self, request):
        data = await request.json()
        raw_jd = data.get("raw_jd", "")
        title = data.get("title", "")
        company = data.get("company", "")
        if not raw_jd.strip():
            return web.json_response({"status": "error", "message": "Job description cannot be empty"}, status=400)

        self.current_profile = CriteriaExtractor.decompose_job_description(raw_jd, title=title, company=company)
        return web.json_response({"status": "success", "profile": self.current_profile.to_dict()})

    async def add_knockout_handler(self, request):
        """Allows recruiters to define custom knockout dealbreakers dynamically."""
        data = await request.json()
        name = data.get("name", "").strip()
        category_str = data.get("category", "CUSTOM").upper()
        requirement_text = data.get("requirement_text", "").strip() or name
        min_value = float(data.get("min_value")) if data.get("min_value") is not None and data.get("min_value") != "" else None
        raw_keywords = data.get("target_keywords", [])
        if isinstance(raw_keywords, str):
            target_keywords = [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]
        else:
            target_keywords = [str(k).strip().lower() for k in raw_keywords if str(k).strip()]

        mandatory = bool(data.get("mandatory", True))
        strict_silence_fails = bool(data.get("strict_silence_fails", True))

        if not name:
            return web.json_response({"status": "error", "message": "Rule name is required"}, status=400)

        try:
            category = KnockoutCategory[category_str]
        except KeyError:
            category = KnockoutCategory.CUSTOM

        rule_id = f"ko_custom_{uuid.uuid4().hex[:6]}"
        criterion = KnockoutCriterion(
            id=rule_id,
            name=name,
            category=category,
            requirement_text=requirement_text,
            min_value=min_value,
            target_keywords=target_keywords,
            mandatory=mandatory,
            strict_silence_fails=strict_silence_fails,
            enabled=True
        )

        self.current_profile.knockouts.append(criterion)
        return web.json_response({
            "status": "success",
            "rule": criterion.to_dict(),
            "profile": self.current_profile.to_dict()
        })

    async def toggle_knockout_handler(self, request):
        data = await request.json()
        rule_id = data.get("id")
        enabled = data.get("enabled")
        for ko in self.current_profile.knockouts:
            if ko.id == rule_id:
                ko.enabled = bool(enabled)
                return web.json_response({"status": "success", "profile": self.current_profile.to_dict()})
        return web.json_response({"status": "error", "message": "Rule ID not found"}, status=404)

    async def delete_knockout_handler(self, request):
        data = await request.json()
        rule_id = data.get("id")
        initial_len = len(self.current_profile.knockouts)
        self.current_profile.knockouts = [k for k in self.current_profile.knockouts if k.id != rule_id]
        if len(self.current_profile.knockouts) < initial_len:
            return web.json_response({"status": "success", "profile": self.current_profile.to_dict()})
        return web.json_response({"status": "error", "message": "Rule ID not found"}, status=404)

    async def get_candidates_handler(self, request):
        return web.json_response({
            "status": "success",
            "candidates": [c.to_dict() for c in self.evaluated_candidates]
        })

    async def clear_candidates_handler(self, request):
        self.evaluated_candidates.clear()
        return web.json_response({"status": "success", "message": "Candidate session cleared"})

    async def evaluate_text_handler(self, request):
        """Direct evaluation of pasted resume text."""
        data = await request.json()
        raw_text = data.get("text", "")
        filename = data.get("filename", "Pasted_Resume.txt")

        if not raw_text.strip():
            return web.json_response({"status": "error", "message": "Resume text cannot be empty"}, status=400)

        result = self.engine.evaluate_text(raw_text, filename=filename, profile=self.current_profile)
        self.evaluated_candidates.insert(0, result)
        return web.json_response({"status": "success", "result": result.to_dict()})

    async def upload_evaluate_handler(self, request):
        """Handles real multi-file batch upload (PDF, DOCX, TXT, MD)."""
        reader = await request.multipart()
        new_results = []

        while True:
            part = await reader.next()
            if part is None:
                break

            if part.filename:
                file_bytes = await part.read()
                try:
                    res = self.engine.evaluate_bytes(file_bytes, filename=part.filename, profile=self.current_profile)
                    self.evaluated_candidates.insert(0, res)
                    new_results.append(res.to_dict())
                except Exception as e:
                    new_results.append({
                        "filename": part.filename,
                        "status": "ERROR",
                        "error": str(e)
                    })

        return web.json_response({"status": "success", "results": new_results})

    async def test_api_key_handler(self, request):
        """Pings TypeSafe AI System One with current or passed key."""
        data = await request.json()
        key = data.get("api_key", "").strip() or self.engine.api_key
        t0 = time.time()
        try:
            test_payload = {
                "model": "jev-latest",
                "state": "Recruiter ATS ping test to verify high-accuracy decision gateway.",
                "questions": {
                    "health": {
                        "type": "choice",
                        "instructions": "Verify connectivity.",
                        "criteria": {
                            "ONLINE": "Connection verified",
                            "OFFLINE": "Connection failed"
                        }
                    }
                }
            }
            resp = requests.post(
                TYPESAFE_API_URL,
                json=test_payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=4.0
            )
            latency = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                res_data = resp.json()
                if key != self.engine.api_key:
                    self.engine.api_key = key
                return web.json_response({
                    "status": "success",
                    "online": True,
                    "model": res_data.get("model", "jev-1.13.0"),
                    "latency_ms": latency,
                    "message": f"Connected to TypeSafe AI System One ({res_data.get('model', 'jev-1.13.0')}) in {latency}ms."
                })
            else:
                return web.json_response({
                    "status": "error",
                    "online": False,
                    "code": resp.status_code,
                    "message": f"HTTP {resp.status_code}: {resp.text}"
                }, status=400)
        except Exception as e:
            return web.json_response({
                "status": "error",
                "online": False,
                "message": str(e)
            }, status=500)

    async def export_csv_handler(self, request):
        """Exports all evaluated candidates as a downloadable CSV legal compliance audit."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Candidate Name",
            "Filename",
            "Verdict Status",
            "Match Score (%)",
            "Verified Tenure (Yrs)",
            "Knockout Violations Count",
            "Primary Deficit Reason",
            "Resume Citation Evidence",
            "TypeSafe System One Model",
            "TypeSafe Decision",
            "TypeSafe Confidence (%)",
            "Evaluation Timestamp"
        ])

        for c in self.evaluated_candidates:
            primary_deficit = c.knockout_violations[0].deficit_reason if c.knockout_violations else "N/A (Passed All Gates)"
            primary_evidence = c.knockout_violations[0].resume_evidence if c.knockout_violations else "Meets or exceeds minimum requirements"
            api_info = c.api_telemetry or {}

            writer.writerow([
                c.candidate_name,
                c.filename,
                c.status.value,
                f"{c.overall_match_score:.1f}%",
                f"{c.total_calendar_years:.2f}",
                len(c.knockout_violations),
                primary_deficit,
                primary_evidence,
                api_info.get("model", "jev-1.13.0"),
                api_info.get("choice", c.status.value),
                f"{api_info.get('confidence', 95.0):.1f}%",
                c.evaluated_at
            ])

        csv_content = output.getvalue()
        output.close()

        return web.Response(
            text=csv_content,
            content_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=ats_disqualification_compliance_audit.csv"
            }
        )

    async def export_json_handler(self, request):
        """Exports candidate evaluations and job profile as a JSON audit package."""
        data = {
            "job_profile": self.current_profile.to_dict(),
            "total_candidates": len(self.evaluated_candidates),
            "disqualified_count": sum(1 for c in self.evaluated_candidates if c.status == EvaluationStatus.DISQUALIFIED),
            "advanced_count": sum(1 for c in self.evaluated_candidates if c.status == EvaluationStatus.ADVANCE),
            "review_count": sum(1 for c in self.evaluated_candidates if c.status == EvaluationStatus.MANUAL_REVIEW),
            "candidates": [c.to_dict() for c in self.evaluated_candidates]
        }
        return web.Response(
            text=json.dumps(data, indent=2),
            content_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=ats_disqualification_audit.json"
            }
        )

    def start(self):
        app = web.Application(client_max_size=50 * 1024 * 1024)  # 50MB upload limit
        app.router.add_get("/", self.index_handler)
        app.router.add_get("/api/profile", self.get_profile_handler)
        app.router.add_post("/api/load_sample_jd", self.load_sample_jd_handler)
        app.router.add_post("/api/update_jd", self.update_jd_handler)

        # Dynamic Knockout Management
        app.router.add_post("/api/add_knockout", self.add_knockout_handler)
        app.router.add_post("/api/toggle_knockout", self.toggle_knockout_handler)
        app.router.add_post("/api/delete_knockout", self.delete_knockout_handler)

        # Candidate Evaluation & Ingestion
        app.router.add_get("/api/candidates", self.get_candidates_handler)
        app.router.add_post("/api/clear_candidates", self.clear_candidates_handler)
        app.router.add_post("/api/evaluate_text", self.evaluate_text_handler)
        app.router.add_post("/api/upload_resumes", self.upload_evaluate_handler)

        # Live API Telemetry & Exports
        app.router.add_post("/api/test_api_key", self.test_api_key_handler)
        app.router.add_get("/api/export_csv", self.export_csv_handler)
        app.router.add_get("/api/export_json", self.export_json_handler)

        runner = web.AppRunner(app)
        return runner


def main():
    server = ResumeDisqualifierServer(port=8990)
    runner = server.start()
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner.setup())

    site = web.TCPSite(runner, "0.0.0.0", 8990)
    loop.run_until_complete(site.start())
    print(f"\n[RESUME DISQUALIFIER ONLINE] Interactive Cockpit active at http://localhost:8990")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nStopping server cleanly...")


if __name__ == "__main__":
    main()
