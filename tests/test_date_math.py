"""
Unit tests for Timeline & Date Math.
Verifies overlapping job merging, tenure calculation, and gap detection.
"""

import unittest
from datetime import date
from parser.timeline_extractor import TimelineExtractor


class TestDateMath(unittest.TestCase):
    def test_overlapping_jobs_no_double_counting(self):
        """Two overlapping jobs from Jan 2020 to Dec 2022 should be 3 years, not 6."""
        resume_text = """
        John Doe
        Experience:
        Senior Cloud Architect
        Acme Corp
        Jan 2020 - Dec 2022
        - Built distributed cloud services in Go and AWS

        Open Source Tech Lead
        Linux Foundation
        Jun 2020 - Dec 2021
        - Maintained container tooling
        """
        timeline = TimelineExtractor.parse_timeline(resume_text)
        self.assertEqual(len(timeline.positions), 2)
        # 36 months = 3.0 years
        self.assertEqual(timeline.total_calendar_years, 3.0)

    def test_present_anchor_calculation(self):
        """Job running to 'Present' should be calculated against anchor date."""
        resume_text = """
        Software Engineer
        TechGiant Inc
        Jan 2022 - Present
        - Developing backend APIs
        """
        anchor = date(2025, 1, 1) # ~3 years
        timeline = TimelineExtractor.parse_timeline(resume_text, current_anchor_date=anchor)
        self.assertAlmostEqual(timeline.total_calendar_years, 3.0, delta=0.15)
        self.assertTrue(timeline.positions[0].is_current)

    def test_career_gap_detection(self):
        """Detects gaps greater than or equal to 6 months."""
        resume_text = """
        DevOps Engineer
        Company B
        Jan 2023 - Dec 2023
        - Kubernetes deployment

        Junior Engineer
        Company A
        Jan 2020 - Dec 2021
        - Linux server admin
        """
        # Gap is all of 2022 (12 months)
        timeline = TimelineExtractor.parse_timeline(resume_text)
        self.assertEqual(len(timeline.gaps_months), 1)
        self.assertGreaterEqual(timeline.gaps_months[0]["gap_months"], 12)

    def test_numeric_slash_date_format(self):
        """Tests parsing dates in MM/YYYY format."""
        resume_text = """
        Data Analyst
        DataCorp
        03/2018 - 09/2021
        - SQL and Python dashboards
        """
        timeline = TimelineExtractor.parse_timeline(resume_text)
        self.assertAlmostEqual(timeline.total_calendar_years, 3.5, delta=0.1)


if __name__ == "__main__":
    unittest.main()
