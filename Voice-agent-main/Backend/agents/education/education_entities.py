"""
education_entities.py — Entity Extraction for Student Profiles.
Contains robust regex & NLP pattern matchers for academic qualifications,
courses, specializations, entrance exams, locations, and budgets.
"""

import re
from typing import Dict, Any, Optional

QUALIFICATION_PATTERNS = {
    r"\b(10th|class 10|tenth|ssc)\b": "10th",
    r"\b(12th|class 12|twelfth|hsc|higher secondary)\b": "12th",
    r"\b(bca|b\.c\.a)\b": "BCA",
    r"\b(mca|m\.c\.a)\b": "MCA",
    r"\b(btech|b\.tech|b\.e\.|bachelor of technology|bachelor of engineering)\b": "B.Tech",
    r"\b(mtech|m\.tech|m\.e\.|master of technology|master of engineering)\b": "M.Tech",
    r"\b(mba|m\.b\.a|master of business administration)\b": "MBA",
    r"\b(bba|b\.b\.a)\b": "BBA",
    r"\b(bcom|b\.com|bachelor of commerce)\b": "B.Com",
    r"\b(mcom|m\.com)\b": "M.Com",
    r"\b(bsc|b\.sc|bachelor of science)\b": "BSc",
    r"\b(msc|m\.sc|master of science)\b": "MSc",
    r"\b(ba|b\.a|bachelor of arts)\b": "BA",
    r"\b(ma|m\.a|master of arts)\b": "MA",
    r"\b(mbbs|m\.b\.b\.s)\b": "MBBS",
    r"\b(llb|l\.l\.b)\b": "LLB",
    r"\b(llm|l\.l\.m)\b": "LLM",
    r"\b(phd|ph\.d|doctorate)\b": "PhD",
    r"\b(diploma)\b": "Diploma",
}

SPECIALIZATION_PATTERNS = {
    r"\b(computer science|cs|cse)\b": "Computer Science",
    r"\b(artificial intelligence|ai)\b": "Artificial Intelligence",
    r"\b(machine learning|ml)\b": "Machine Learning",
    r"\b(data science|data analytics)\b": "Data Science",
    r"\b(cybersecurity|cyber security)\b": "Cybersecurity",
    r"\b(cloud computing|cloud)\b": "Cloud Computing",
    r"\b(software engineering|software dev)\b": "Software Engineering",
    r"\b(finance)\b": "Finance",
    r"\b(marketing)\b": "Marketing",
    r"\b(human resources|hr)\b": "HR",
}

EXAM_PATTERNS = {
    r"\b(jee|jee main|jee advanced)\b": "JEE",
    r"\b(neet)\b": "NEET",
    r"\b(cat)\b": "CAT",
    r"\b(mat)\b": "MAT",
    r"\b(gate)\b": "GATE",
    r"\b(cet|mht-cet|mht cet)\b": "CET",
    r"\b(gre)\b": "GRE",
    r"\b(gmat)\b": "GMAT",
    r"\b(ielts)\b": "IELTS",
    r"\b(toefl)\b": "TOEFL",
    r"\b(pte)\b": "PTE",
    r"\b(sat)\b": "SAT",
}

CITY_PATTERNS = {
    r"\b(pune)\b": "Pune",
    r"\b(mumbai|bombay)\b": "Mumbai",
    r"\b(bangalore|bengaluru)\b": "Bangalore",
    r"\b(hyderabad)\b": "Hyderabad",
    r"\b(delhi|ncr|gurgaon|noida)\b": "Delhi NCR",
    r"\b(jaipur)\b": "Jaipur",
    r"\b(chennai|madras)\b": "Chennai",
    r"\b(nashik)\b": "Nashik",
    r"\b(nagpur)\b": "Nagpur",
    r"\b(kolkata)\b": "Kolkata",
    r"\b(ahmedabad)\b": "Ahmedabad",
}

COUNTRY_PATTERNS = {
    r"\b(india)\b": "India",
    r"\b(usa|america|united states|us)\b": "USA",
    r"\b(uk|united kingdom|britain|england)\b": "UK",
    r"\b(canada)\b": "Canada",
    r"\b(germany)\b": "Germany",
    r"\b(australia)\b": "Australia",
    r"\b(ireland)\b": "Ireland",
    r"\b(france)\b": "France",
    r"\b(singapore)\b": "Singapore",
    r"\b(dubai|uae)\b": "Dubai",
}


def extract_qualification(text: str) -> Optional[str]:
    clean = text.lower()
    for pattern, val in QUALIFICATION_PATTERNS.items():
        if re.search(pattern, clean):
            return val
    return None


def extract_specialization(text: str) -> Optional[str]:
    clean = text.lower()
    for pattern, val in SPECIALIZATION_PATTERNS.items():
        if re.search(pattern, clean):
            return val
    return None


def extract_exam(text: str) -> Optional[str]:
    clean = text.lower()
    for pattern, val in EXAM_PATTERNS.items():
        if re.search(pattern, clean):
            return val
    return None


def extract_city(text: str) -> Optional[str]:
    clean = text.lower()
    for pattern, val in CITY_PATTERNS.items():
        if re.search(pattern, clean):
            return val
    return None


def extract_country(text: str) -> Optional[str]:
    clean = text.lower()
    for pattern, val in COUNTRY_PATTERNS.items():
        if re.search(pattern, clean):
            return val
    return None


def extract_percentage(text: str) -> Optional[str]:
    m = re.search(r"(\b\d{2}(?:\.\d{1,2})?\b)\s*(?:percent|percentage|%|pr)", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}%"
    m2 = re.search(r"\bgot\s+(\d{2})\b", text, re.IGNORECASE)
    if m2:
        return f"{m2.group(1)}%"
    return None


def extract_budget(text: str) -> Optional[str]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:to|-)?\s*(\d+(?:\.\d+)?)?\s*(lakh|lakhs|lac|lacs|k|thousand)?", text, re.IGNORECASE)
    if m and ("budget" in text.lower() or "lakh" in text.lower() or "fees" in text.lower()):
        val1 = m.group(1)
        val2 = m.group(2)
        unit = m.group(3) or "lakhs"
        if val2:
            return f"₹{val1}–{val2} {unit}"
        return f"₹{val1} {unit}"
    return None


def extract_study_abroad(text: str) -> Optional[bool]:
    clean = text.lower()
    if any(k in clean for k in ["abroad", "foreign", "outside india", "another country"]):
        return True
    if any(k in clean for k in ["in india", "domestic", "here only"]):
        return False
    return None


def extract_education_entities(text: str) -> Dict[str, Any]:
    """
    Extracts all student profile entities from raw user transcript text.
    """
    entities = {}

    qual = extract_qualification(text)
    if qual:
        # Determine whether this is current qualification vs preferred target course
        clean = text.lower()
        if any(k in clean for k in ["doing", "completed", "pursuing", "studying", "passed", "got"]):
            entities["current_qualification"] = qual
        elif any(k in clean for k in ["want", "looking for", "apply", "plan", "thinking of", "interested in"]):
            entities["preferred_course"] = qual
        else:
            entities["current_qualification"] = qual

    spec = extract_specialization(text)
    if spec:
        entities["preferred_specialization"] = spec

    exam = extract_exam(text)
    if exam:
        entities["entrance_exam"] = exam

    city = extract_city(text)
    if city:
        entities["preferred_city"] = city

    country = extract_country(text)
    if country:
        entities["preferred_country"] = country

    abroad = extract_study_abroad(text)
    if abroad is not None:
        entities["study_abroad"] = abroad

    pct = extract_percentage(text)
    if pct:
        entities["percentage"] = pct

    bgt = extract_budget(text)
    if bgt:
        entities["budget"] = bgt

    return entities
