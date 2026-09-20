"""
Job Description Decomposition & Criteria Extractor.
Parses raw Job Descriptions into structured Knockouts and Competencies.
Includes industry-standard preset profiles.
"""

import re
import uuid
from typing import List, Dict, Any, Optional
from criteria.schema import KnockoutCriterion, CompetencyCriterion, JobProfile, KnockoutCategory


COMMON_SYNONYMS = {
    "golang": ["go", "golang"],
    "go": ["go", "golang"],
    "python": ["python", "py", "python3"],
    "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript", "ts"],
    "react": ["react", "react.js", "reactjs"],
    "node": ["node", "node.js", "nodejs"],
    "postgres": ["postgres", "postgresql", "psql"],
    "postgresql": ["postgres", "postgresql", "psql"],
    "k8s": ["k8s", "kubernetes"],
    "kubernetes": ["k8s", "kubernetes"],
    "aws": ["aws", "amazon web services"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "docker": ["docker", "containerization", "containers"],
    "c#": ["c#", "csharp", ".net", "dotnet"],
    "java": ["java", "jvm"],
    "cpp": ["c++", "cpp"],
    "sql": ["sql", "relational database", "rdbms"]
}


class CriteriaExtractor:
    @classmethod
    def decompose_job_description(cls, raw_jd: str, title: str = "", company: str = "") -> JobProfile:
        """
        Decomposes a raw job description string into Knockout Criteria and Competencies.
        """
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        title = title or cls._infer_job_title(raw_jd)
        company = company or "Target Company"

        knockouts: List[KnockoutCriterion] = []
        competencies: List[CompetencyCriterion] = []

        # 1. Detect Visa / Sponsorship Knockouts
        visa_ko = cls._detect_visa_knockouts(raw_jd)
        if visa_ko:
            knockouts.append(visa_ko)

        # 2. Detect Clearance Knockouts
        clearance_ko = cls._detect_clearance_knockouts(raw_jd)
        if clearance_ko:
            knockouts.append(clearance_ko)

        # 3. Detect Minimum Experience Years
        tenure_ko = cls._detect_total_tenure_knockouts(raw_jd)
        if tenure_ko:
            knockouts.append(tenure_ko)

        # 4. Detect Mandatory Certifications / Licenses
        cert_ko = cls._detect_cert_knockouts(raw_jd)
        knockouts.extend(cert_ko)

        # 5. Detect Mandatory Degrees (if marked strictly required)
        degree_ko = cls._detect_degree_knockouts(raw_jd)
        if degree_ko:
            knockouts.append(degree_ko)

        # 6. Extract Core Technical Competencies & Skill Tenures
        comps, skill_kos = cls._extract_skills_and_competencies(raw_jd)
        competencies.extend(comps)
        knockouts.extend(skill_kos)

        return JobProfile(
            job_id=job_id,
            title=title,
            company=company,
            location=cls._infer_location(raw_jd),
            raw_jd=raw_jd,
            knockouts=knockouts,
            competencies=competencies
        )

    @staticmethod
    def _infer_job_title(text: str) -> str:
        first_few = text.strip().splitlines()[:5]
        for line in first_few:
            clean = line.strip(" #*:-")
            if any(term in clean.lower() for term in ["engineer", "developer", "manager", "lead", "architect", "analyst", "nurse", "director"]):
                return clean
        return "Target Position"

    @staticmethod
    def _infer_location(text: str) -> str:
        text_lower = text.lower()
        if "remote" in text_lower:
            return "Remote"
        if "hybrid" in text_lower:
            return "Hybrid"
        return "On-Site"

    @staticmethod
    def _detect_visa_knockouts(text: str) -> Optional[KnockoutCriterion]:
        patterns = [
            r"no\s+(?:visa\s+)?sponsorship",
            r"must\s+be\s+authorized\s+to\s+work\s+in\s+the\s+u\.?s\.?",
            r"without\s+(?:the\s+need\s+for\s+)?sponsorship",
            r"u\.?s\.?\s+citizen(?:ship)?\s+or\s+permanent\s+resident",
            r"green\s+card\s+holder"
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return KnockoutCriterion(
                    id="ko_visa",
                    name="Work Authorization (No Sponsorship)",
                    category=KnockoutCategory.VISA,
                    requirement_text=match.group(0),
                    target_keywords=["citizen", "green card", "authorized to work", "permanent resident", "us person"],
                    mandatory=True,
                    strict_silence_fails=False
                )
        return None

    @staticmethod
    def _detect_clearance_knockouts(text: str) -> Optional[KnockoutCriterion]:
        match = re.search(r"(active\s+)?(?:secret|top\s+secret|ts/sci|security\s+clearance)", text, re.IGNORECASE)
        if match:
            return KnockoutCriterion(
                id="ko_clearance",
                name="Security Clearance Required",
                category=KnockoutCategory.CLEARANCE,
                requirement_text=match.group(0),
                target_keywords=["security clearance", "secret clearance", "top secret", "ts/sci"],
                mandatory=True,
                strict_silence_fails=True
            )
        return None

    @staticmethod
    def _detect_total_tenure_knockouts(text: str) -> Optional[KnockoutCriterion]:
        patterns = [
            r"(?P<years>\d+)\+?\s*(?:to\s*\d+)?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+professional|\s+relevant|\s+industry)?\s+experience",
            r"minimum\s+(?:of\s+)?(?P<years>\d+)\+?\s*years?"
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                years = float(match.group("years"))
                return KnockoutCriterion(
                    id="ko_total_tenure",
                    name=f"Minimum {int(years)}+ Years Professional Experience",
                    category=KnockoutCategory.TOTAL_TENURE,
                    requirement_text=match.group(0),
                    min_value=years,
                    mandatory=True,
                    strict_silence_fails=True
                )
        return None

    @staticmethod
    def _detect_cert_knockouts(text: str) -> List[KnockoutCriterion]:
        certs = [
            ("CPA", ["cpa", "certified public accountant"]),
            ("RN License", ["rn", "registered nurse", "rn license"]),
            ("PMP", ["pmp", "project management professional"]),
            ("CISSP", ["cissp", "certified information systems security professional"]),
            ("Bar Admission", ["bar admission", "licensed attorney", "admitted to the bar"])
        ]
        results = []
        for name, kws in certs:
            if any(re.search(rf"\b{kw}\b", text, re.IGNORECASE) for kw in kws):
                results.append(KnockoutCriterion(
                    id=f"ko_cert_{name.lower().replace(' ', '_')}",
                    name=f"Mandatory Licensure / Certification: {name}",
                    category=KnockoutCategory.MANDATORY_LICENSE,
                    requirement_text=f"Must hold active {name}",
                    target_keywords=kws,
                    mandatory=True,
                    strict_silence_fails=True
                ))
        return results

    @staticmethod
    def _detect_degree_knockouts(text: str) -> Optional[KnockoutCriterion]:
        if re.search(r"ph\.?d\.?\s+(?:required|is\s+a\s+must)", text, re.IGNORECASE):
            return KnockoutCriterion(
                id="ko_degree_phd",
                name="Mandatory Doctorate Degree (PhD)",
                category=KnockoutCategory.MANDATORY_DEGREE,
                requirement_text="PhD required",
                target_keywords=["phd", "ph.d", "doctorate"],
                mandatory=True,
                strict_silence_fails=True
            )
        return None

    @classmethod
    def _extract_skills_and_competencies(cls, text: str) -> tuple[List[CompetencyCriterion], List[KnockoutCriterion]]:
        """Extracts key skills and associated required tenures."""
        comps: List[CompetencyCriterion] = []
        skill_kos: List[KnockoutCriterion] = []

        # Find "X+ years of [Skill]"
        skill_tenure_regex = re.compile(
            r"(?P<years>\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+hands-on|\s+production|\s+practical)?\s+experience\s+(?:with|in)\s+(?P<skill>[a-zA-Z0-9#+.-]+(?:\s+[a-zA-Z0-9#+.-]+)?)",
            re.IGNORECASE
        )

        for match in skill_tenure_regex.finditer(text):
            years = float(match.group("years"))
            raw_skill = match.group("skill").strip().lower()
            if len(raw_skill) > 20 or any(stop in raw_skill for stop in ["building", "leading", "designing", "scaling"]):
                continue

            synonyms = COMMON_SYNONYMS.get(raw_skill, [raw_skill])

            # If required years >= 3, treat as hard knockout; otherwise standard competency
            if years >= 3.0:
                skill_kos.append(KnockoutCriterion(
                    id=f"ko_skill_{raw_skill.replace(' ', '_')}",
                    name=f"Minimum {int(years)}+ Years Experience in {raw_skill.title()}",
                    category=KnockoutCategory.SKILL_TENURE,
                    requirement_text=match.group(0),
                    min_value=years,
                    target_keywords=synonyms,
                    mandatory=True
                ))

            comps.append(CompetencyCriterion(
                id=f"comp_{raw_skill.replace(' ', '_')}",
                name=raw_skill.title(),
                category="TECHNICAL_SKILL",
                requirement_text=match.group(0),
                min_tenure_years=years,
                synonyms=synonyms,
                weight=2.0 if years >= 3.0 else 1.0
            ))

        # Also search for standalone notable keywords if none found
        if len(comps) < 3:
            default_techs = ["python", "go", "react", "sql", "kubernetes", "aws", "docker"]
            for tech in default_techs:
                if re.search(rf"\b{tech}\b", text, re.IGNORECASE):
                    synonyms = COMMON_SYNONYMS.get(tech, [tech])
                    comps.append(CompetencyCriterion(
                        id=f"comp_{tech}",
                        name=tech.title(),
                        category="TECHNICAL_SKILL",
                        requirement_text=f"Experience with {tech.title()}",
                        min_tenure_years=1.0,
                        synonyms=synonyms,
                        weight=1.0
                    ))

        return comps, skill_kos
