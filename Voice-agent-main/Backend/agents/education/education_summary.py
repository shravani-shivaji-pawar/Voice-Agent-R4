"""
education_summary.py — Generates Personalized Student Profile Summaries.
"""

from typing import Dict, Any

def generate_student_summary(profile: Dict[str, Any], language: str = "en") -> str:
    """
    Constructs a clear, concise summary of the student's background and goals.
    """
    qual = profile.get("current_qualification") or "Not specified"
    course = profile.get("preferred_course") or "Under exploration"
    city = profile.get("preferred_city") or profile.get("preferred_country") or "Flexible"
    budget = profile.get("budget") or "Flexible"
    score = profile.get("percentage") or profile.get("entrance_exam") or "Not provided"

    if language in ("hi", "hinglish"):
        return (
            f"स्टूडेंट प्रोफाइल समरी:\n"
            f"- वर्तमान योग्यता: {qual}\n"
            f"- इच्छित कोर्स: {course}\n"
            f"- पसंदीदा लोकेशन: {city}\n"
            f"- बजट/फीस: {budget}\n"
            f"- अकेडेमिक स्कोर: {score}"
        )
    
    return (
        f"Student Profile Summary:\n"
        f"- Current Qualification: {qual}\n"
        f"- Target Course: {course}\n"
        f"- Preferred Location: {city}\n"
        f"- Budget Expectation: {budget}\n"
        f"- Academic Score/Exam: {score}"
    )
