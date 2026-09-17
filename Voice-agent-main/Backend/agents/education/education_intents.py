"""
education_intents.py — Intent Classifier for Education Counselling.
Identifies student intents without using real-estate intent rules.
"""

import re
from typing import Dict, Any

EDUCATION_INTENT_PATTERNS = {
    "goodbye": [
        r"\b(bye|goodbye|see you|tata|chalo bye|dhanyawad bye|shubharatri)\b",
        r"\b(exit|stop|terminate|hang up|end call)\b"
    ],
    "acknowledgement": [
        r"^(okay|ok|haan|hoga|theek hai|thik hai|got it|sure|alright|fine)$",
        r"^(accha|achha|sahi hai|samajh gaya|samajh gayi)$"
    ],
    "current_study": [
        r"\b(currently studying|doing|pursuing|completed|passed|in 12th|in 10th|studying in|studying)\b",
        r"\b(bca|mca|btech|mba|bba|bcom|bsc|ba|mbbs)\b"
    ],
    "study_abroad": [
        r"\b(study abroad|abroad|foreign|usa|uk|canada|germany|australia|ireland|overseas)\b"
    ],
    "fees": [
        r"\b(fee|fees|cost|tuition|charge|expenses|how much price|package)\b"
    ],
    "scholarship": [
        r"\b(scholarship|financial aid|stipend|grant|fee waiver|discount)\b"
    ],
    "entrance_exam": [
        r"\b(jee|neet|cat|mat|gate|cet|gre|gmat|ielts|toefl|pte|entrance exam|cutoff|rank|score)\b"
    ],
    "college_discovery": [
        r"\b(college|university|institute|campus|top colleges|best colleges)\b"
    ],
    "course_discovery": [
        r"\b(course|degree|specialization|program|stream|branch|subject|field)\b"
    ],
    "counselling_request": [
        r"\b(counsellor|counselor|advisor|consultation|talk to expert|call back|book session)\b"
    ]
}


def classify_education_intent(text: str) -> Dict[str, Any]:
    clean = text.lower().strip()

    for intent, patterns in EDUCATION_INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, clean):
                return {
                    "intent": intent,
                    "confidence": 0.9
                }

    return {
        "intent": "general_education_question",
        "confidence": 0.7
    }
