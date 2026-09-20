"""
End-to-end integration tests for Resume Disqualifier.
Tests DOCX and TXT generation, decomposition, and complete evaluation pipeline.
"""

import unittest
import io
from pathlib import Path
import docx

from criteria.extractor import CriteriaExtractor
from engine.decision_gateway import ResumeEvaluationEngine
from criteria.schema import EvaluationStatus


class TestE2EIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = ResumeEvaluationEngine(api_key="")

    def test_docx_ingestion_and_knockout(self):
        """Generates an in-memory DOCX resume and verifies deterministic knockout."""
        doc = docx.Document()
        doc.add_heading("Marcus Vance", 0)
        doc.add_paragraph("Chicago, IL | marcus.v@email.com")
        doc.add_paragraph("Summary: Energetic junior developer with 1.5 years experience.")
        doc.add_heading("Experience", level=1)
        doc.add_paragraph("Junior Web Developer | DigitalApp Inc | Jan 2022 - Jun 2023")
        doc.add_paragraph("• Created HTML/CSS templates and maintained small Python scripts.")

        doc_io = io.BytesIO()
        doc.save(doc_io)
        docx_bytes = doc_io.getvalue()

        # Job requires 4+ years
        raw_jd = """
        Title: Senior Python Engineer
        Company: Citadel
        Minimum Qualifications:
        - Must have minimum 4+ years professional software engineering experience.
        - Strong Python development skills.
        """
        profile = CriteriaExtractor.decompose_job_description(raw_jd)

        result = self.engine.evaluate_bytes(docx_bytes, filename="marcus_junior.docx", profile=profile)
        self.assertEqual(result.status, EvaluationStatus.DISQUALIFIED)
        self.assertEqual(result.candidate_name, "Marcus Vance")
        self.assertTrue(any("Experience Tenure Deficit" in v.deficit_reason for v in result.knockout_violations))

    def test_jd_decomposition_knockouts_extraction(self):
        """Tests that auto-decomposition extracts Visa, Tenure, and Tech knockouts."""
        raw_jd = """
        Position: Lead Cloud SRE
        Company: Palantir
        Requirements:
        - Must be authorized to work in the US without sponsorship.
        - Minimum 5+ years of experience in SRE or DevOps engineering.
        - At least 3+ years of experience with Kubernetes.
        - Active Top Secret clearance required.
        """
        profile = CriteriaExtractor.decompose_job_description(raw_jd)
        self.assertEqual(len(profile.knockouts), 4) # Visa, Total tenure, Kubernetes skill tenure, Clearance
        categories = [k.category.value for k in profile.knockouts]
        self.assertIn("VISA", categories)
        self.assertIn("TOTAL_TENURE", categories)
        self.assertIn("SKILL_TENURE", categories)
        self.assertIn("CLEARANCE", categories)


if __name__ == "__main__":
    unittest.main()
