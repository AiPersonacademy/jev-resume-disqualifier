"""
Unit tests for Deterministic Knockout Rules.
Tests tenure deficit rejections, visa sponsorship dealbreakers, and license verifications.
"""

import unittest
from datetime import date
from criteria.schema import KnockoutCriterion, KnockoutCategory, JobProfile
from engine.decision_gateway import ResumeEvaluationEngine
from criteria.schema import EvaluationStatus


class TestKnockoutRules(unittest.TestCase):
    def setUp(self):
        self.engine = ResumeEvaluationEngine(api_key="")

    def test_tenure_deficit_disqualification(self):
        """Candidate with 2 years experience is strictly disqualified when JD requires 5+ years."""
        job = JobProfile(
            job_id="job_senior_dev",
            title="Senior Backend Engineer",
            company="Stripe",
            location="Remote",
            raw_jd="Requires minimum 5+ years of experience in backend software engineering.",
            knockouts=[
                KnockoutCriterion(
                    id="ko_tenure_5y",
                    name="Minimum 5+ Years Experience",
                    category=KnockoutCategory.TOTAL_TENURE,
                    requirement_text="Minimum 5+ years of experience",
                    min_value=5.0,
                    mandatory=True
                )
            ]
        )

        junior_resume = """
        Alex Smith
        Summary: Eager software engineer with passion for cloud systems.
        Experience:
        Junior Engineer
        StartupCo
        Jan 2022 - Dec 2023
        - Built REST APIs in Python and FastAPI
        """
        result = self.engine.evaluate_text(junior_resume, "alex_junior.txt", job)
        self.assertEqual(result.status, EvaluationStatus.DISQUALIFIED)
        self.assertEqual(len(result.knockout_violations), 1)
        self.assertIn("Experience Tenure Deficit", result.knockout_violations[0].deficit_reason)

    def test_visa_sponsorship_disqualification(self):
        """Candidate requiring H1B visa sponsorship is disqualified when JD forbids sponsorship."""
        job = JobProfile(
            job_id="job_fed",
            title="Systems Engineer",
            company="DefenseCorp",
            location="Washington, DC",
            raw_jd="Must be authorized to work in US without sponsorship. No visa sponsorship provided.",
            knockouts=[
                KnockoutCriterion(
                    id="ko_visa",
                    name="Work Authorization (No Sponsorship)",
                    category=KnockoutCategory.VISA,
                    requirement_text="Must be authorized to work without sponsorship",
                    mandatory=True
                )
            ]
        )

        h1b_resume = """
        Rajesh Patel
        Senior Java Developer
        Summary: Skilled backend engineer. Currently on H1B visa; will require visa sponsorship / H1B transfer.
        Experience:
        Java Developer
        FinTech LLC
        Jan 2018 - Present
        - Spring Boot and Microservices
        """
        result = self.engine.evaluate_text(h1b_resume, "rajesh_h1b.txt", job)
        self.assertEqual(result.status, EvaluationStatus.DISQUALIFIED)
        self.assertEqual(len(result.knockout_violations), 1)
        self.assertIn("Visa Ineligibility", result.knockout_violations[0].deficit_reason)

    def test_mandatory_license_disqualification(self):
        """Candidate missing mandatory RN license is disqualified for Nursing role."""
        job = JobProfile(
            job_id="job_nurse",
            title="ICU Staff Nurse",
            company="General Hospital",
            location="Chicago, IL",
            raw_jd="Active Registered Nurse (RN) license in Illinois is required.",
            knockouts=[
                KnockoutCriterion(
                    id="ko_rn",
                    name="Registered Nurse License",
                    category=KnockoutCategory.MANDATORY_LICENSE,
                    requirement_text="Active Registered Nurse (RN) license required",
                    target_keywords=["rn", "registered nurse", "rn license"],
                    mandatory=True
                )
            ]
        )

        cna_resume = """
        Sarah Jenkins
        Healthcare Specialist
        Certifications: Certified Nursing Assistant (CNA), BLS, CPR
        Experience:
        Nursing Assistant
        CareClinic
        Jan 2019 - Present
        - Patient vital monitoring
        """
        result = self.engine.evaluate_text(cna_resume, "sarah_cna.txt", job)
        self.assertEqual(result.status, EvaluationStatus.DISQUALIFIED)
        self.assertEqual(len(result.knockout_violations), 1)
        self.assertIn("Missing Mandatory Credential", result.knockout_violations[0].deficit_reason)

    def test_fully_qualified_candidate_advances(self):
        """Candidate who satisfies all requirements and knockouts advances."""
        job = JobProfile(
            job_id="job_senior_go",
            title="Senior Go Engineer",
            company="Uber",
            location="Remote",
            raw_jd="Requires 4+ years of software engineering. Strong Go and distributed systems experience.",
            knockouts=[
                KnockoutCriterion(
                    id="ko_tenure",
                    name="Minimum 4+ Years Experience",
                    category=KnockoutCategory.TOTAL_TENURE,
                    requirement_text="4+ years software engineering",
                    min_value=4.0,
                    mandatory=True
                )
            ]
        )

        qualified_resume = """
        Elena Rostova
        US Citizen | San Francisco, CA
        Senior Systems Engineer
        Experience:
        Lead Backend Engineer
        CloudScale Networks
        Jan 2018 - Present
        - Designed high-throughput microservices in Go and Kafka handling 80,000 requests per second.
        - Deployed scalable distributed clusters on AWS and Kubernetes.
        """
        anchor = date(2024, 1, 1) # 6 years of experience
        result = self.engine.evaluate_text(qualified_resume, "elena_qualified.txt", job)
        self.assertEqual(result.status, EvaluationStatus.ADVANCE)
        self.assertEqual(len(result.knockout_violations), 0)


if __name__ == "__main__":
    unittest.main()
