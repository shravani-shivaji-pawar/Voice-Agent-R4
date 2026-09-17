"""
education_knowledge.py — Knowledge & Guidance Model for Education Counselling.
Modeled after Shiksha.com discovery architecture (courses, colleges, exams, eligibility, admissions, fees).
Enforces strict anti-hallucination rules.
"""

from typing import Optional, Dict, Any

SHIKSHA_CATEGORY_HELP = {
    "courses": "We provide information on undergraduate (B.Tech, BCA, BBA, BSc, BA) and postgraduate (MCA, MBA, M.Tech, MSc, MA) programs across Computer Science, AI, Data Science, and Management.",
    "colleges": "We help discover top universities and institutes across major education hubs including Pune, Mumbai, Bangalore, Hyderabad, Delhi NCR, and international study destinations.",
    "exams": "We guide students on major entrance exams including JEE, NEET, CAT, MAT, GATE, CET, GRE, GMAT, IELTS, and TOEFL.",
    "study_abroad": "We support study-abroad planning for USA, UK, Canada, Germany, Australia, Ireland, France, and Dubai including SOP/LOR guidance and visa process steps."
}

def get_education_knowledge_response(user_text: str, language: str = "en") -> Optional[str]:
    """
    Returns verified guidance or anti-hallucination responses for specific student queries.
    Never invents exact fee numbers, cutoffs, rankings, or deadlines.
    """
    clean = user_text.lower()

    if "fee" in clean or "fees" in clean or "cost" in clean or "tuition" in clean:
        if language in ("hi", "hinglish"):
            return "फीस और स्कॉलरशिप विवरण विश्वविद्यालय और स्ट्रीम के अनुसार अलग-अलग होते हैं। सटीक जानकारी के लिए मैं आपको ऑफिशियल एडमिशन पेज चेक करने की सलाह दूंगी।"
        return "Fee structures and scholarships vary by university and specialization. I recommend checking the official admission page or letting our counsellor provide the exact breakdown."

    if "cutoff" in clean or "rank" in clean or "eligible" in clean or "eligibility" in clean:
        if language in ("hi", "hinglish"):
            return "एलिजिबिलिटी और कट-ऑफ हर साल प्रवेश परीक्षा के आधार पर बदलते हैं। आप अपनी स्कोर कार्ड के साथ काउंसलर गाइडेंस ले सकते हैं।"
        return "Eligibility criteria and cut-offs fluctuate each year based on entrance exam results. Our counsellor can evaluate your profile score."

    if "ranking" in clean or "best college" in clean or "top college" in clean:
        if language in ("hi", "hinglish"):
            return "कॉलेज रैंकिंग NIRF और NAAC ग्रेडिंग पर आधारित होती है। पुणे, बैंगलोर और दिल्ली में बेहतरीन ऑप्शंस उपलब्ध हैं।"
        return "College rankings are evaluated based on NIRF, NAAC accreditation, and placement metrics across major hubs like Pune, Bangalore, and Delhi NCR."

    return None
