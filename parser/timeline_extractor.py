"""
Timeline & Work Experience Extractor.
Extracts job positions, start/end dates, calculates true non-overlapping
calendar tenure, detects career gaps, and prevents date inflation.
"""

import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict


MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}

# Regex to match date ranges like:
# "Jan 2020 - Present", "03/2018 to 11/2022", "2019 – 2023", "October 2017 - Current"
MONTH_REGEX = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DATE_RANGE_REGEX = re.compile(
    rf"(?P<start_month>{MONTH_REGEX}|\d{{1,2}})?[\s/.-]*"
    rf"(?P<start_year>(?:19|20)\d{{2}})"
    rf"\s*(?:–|-|—|to|until)\s*"
    rf"(?:(?P<present>present|current|now|ongoing)|"
    rf"(?:(?P<end_month>{MONTH_REGEX}|\d{{1,2}})?[\s/.-]*(?P<end_year>(?:19|20)\d{{2}})))",
    re.IGNORECASE
)


@dataclass
class JobPeriod:
    company: str
    title: str
    start_date: date
    end_date: date
    is_current: bool
    tenure_months: int
    bullet_points: List[str]

    @property
    def tenure_years(self) -> float:
        return round(self.tenure_months / 12.0, 2)


@dataclass
class CandidateTimeline:
    total_calendar_years: float
    total_experience_months: int
    positions: List[JobPeriod]
    gaps_months: List[Dict[str, Any]]
    earliest_job_date: Optional[str]
    most_recent_job_date: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calendar_years": self.total_calendar_years,
            "total_experience_months": self.total_experience_months,
            "positions_count": len(self.positions),
            "positions": [asdict(p) for p in self.positions],
            "gaps": self.gaps_months,
            "earliest_date": self.earliest_job_date,
            "latest_date": self.most_recent_job_date
        }


class TimelineExtractor:
    @classmethod
    def parse_timeline(cls, raw_text: str, current_anchor_date: Optional[date] = None) -> CandidateTimeline:
        """
        Parses work experience sections, extracts date intervals, and computes true tenure.
        """
        if current_anchor_date is None:
            current_anchor_date = date.today()

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        intervals: List[Tuple[date, date, str, str, List[str]]] = []

        current_company = ""
        current_title = ""
        current_bullets = []
        current_dates = None

        for line in lines:
            match = DATE_RANGE_REGEX.search(line)
            if match:
                # If we were tracking a previous job, finalize it
                if current_dates:
                    start_d, end_d, is_curr = current_dates
                    intervals.append((start_d, end_d, current_company or "Organization", current_title or "Role", current_bullets))
                    current_bullets = []

                start_d, end_d, is_curr = cls._parse_date_match(match, current_anchor_date)
                current_dates = (start_d, end_d, is_curr)

                # Try to extract title/company from surrounding text on that line
                line_without_date = DATE_RANGE_REGEX.sub("", line).strip(" ,|-•")
                if line_without_date:
                    if not current_title:
                        current_title = line_without_date
                    elif not current_company:
                        current_company = line_without_date
            else:
                # Is it a bullet point or title?
                if line.startswith(("-", "•", "*", "–")):
                    current_bullets.append(line.lstrip("-•*– ").strip())
                else:
                    if not current_title and current_dates:
                        current_title = line
                    elif not current_company and current_dates:
                        current_company = line
                    elif current_dates:
                        current_bullets.append(line)

        # Flush the final block
        if current_dates:
            start_d, end_d, is_curr = current_dates
            intervals.append((start_d, end_d, current_company or "Organization", current_title or "Role", current_bullets))

        # Build JobPeriod objects
        positions: List[JobPeriod] = []
        date_intervals: List[Tuple[date, date]] = []

        for start_d, end_d, comp, tit, bullets in intervals:
            months = (end_d.year - start_d.year) * 12 + (end_d.month - start_d.month) + 1
            months = max(1, months)
            is_current = (end_d >= current_anchor_date)
            positions.append(JobPeriod(
                company=comp,
                title=tit,
                start_date=start_d,
                end_date=end_d,
                is_current=is_current,
                tenure_months=months,
                bullet_points=bullets
            ))
            date_intervals.append((start_d, end_d))

        # Calculate true merged calendar tenure (no double-counting overlapping jobs)
        merged_months, gaps = cls._merge_date_intervals(date_intervals, current_anchor_date)
        total_years = round(merged_months / 12.0, 2)

        earliest = min([p.start_date for p in positions]).isoformat() if positions else None
        latest = max([p.end_date for p in positions]).isoformat() if positions else None

        return CandidateTimeline(
            total_calendar_years=total_years,
            total_experience_months=merged_months,
            positions=positions,
            gaps_months=gaps,
            earliest_job_date=earliest,
            most_recent_job_date=latest
        )

    @classmethod
    def _parse_date_match(cls, match: re.Match, anchor: date) -> Tuple[date, date, bool]:
        """Converts regex match groups into start_date and end_date."""
        start_year = int(match.group("start_year"))
        start_month_raw = match.group("start_month")
        start_month = cls._normalize_month(start_month_raw)

        start_date = date(start_year, start_month, 1)

        is_present = bool(match.group("present"))
        if is_present:
            end_date = anchor
            return start_date, end_date, True

        end_year = int(match.group("end_year")) if match.group("end_year") else start_year
        end_month_raw = match.group("end_month")
        end_month = cls._normalize_month(end_month_raw, default=12)

        end_date = date(end_year, end_month, 1)
        if end_date < start_date:
            end_date = start_date

        return start_date, end_date, False

    @staticmethod
    def _normalize_month(val: Optional[str], default: int = 1) -> int:
        """Maps string or numeric month representation to 1-12 integer."""
        if not val:
            return default
        clean = val.strip().lower()
        if clean in MONTH_MAP:
            return MONTH_MAP[clean]
        if clean.isdigit():
            m = int(clean)
            if 1 <= m <= 12:
                return m
        return default

    @staticmethod
    def _merge_date_intervals(intervals: List[Tuple[date, date]], anchor: date) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Merges overlapping date ranges to get true calendar tenure.
        Also returns list of significant career gaps (> 6 months).
        """
        if not intervals:
            return 0, []

        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged: List[Tuple[date, date]] = []

        for start, end in sorted_intervals:
            if not merged:
                merged.append((start, end))
            else:
                prev_start, prev_end = merged[-1]
                if start <= prev_end:
                    # Overlap or contiguous
                    merged[-1] = (prev_start, max(prev_end, end))
                else:
                    merged.append((start, end))

        # Calculate total non-overlapping months
        total_months = 0
        for s, e in merged:
            m = (e.year - s.year) * 12 + (e.month - s.month) + 1
            total_months += max(1, m)

        # Detect gaps between disjoint intervals
        gaps = []
        for i in range(len(merged) - 1):
            curr_end = merged[i][1]
            next_start = merged[i + 1][0]
            gap_m = (next_start.year - curr_end.year) * 12 + (next_start.month - curr_end.month)
            if gap_m >= 6:
                gaps.append({
                    "gap_months": gap_m,
                    "from_date": curr_end.strftime("%b %Y"),
                    "to_date": next_start.strftime("%b %Y")
                })

        return total_months, gaps
