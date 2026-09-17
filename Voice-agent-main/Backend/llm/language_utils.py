"""Shared language detection and routing helpers for voice responses."""

from __future__ import annotations

import logging
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


SUPPORTED_LANGUAGES = {"en", "hi", "mr", "hinglish"}
DEVANAGARI_RANGE = ("\u0900", "\u097F")
HINDI_MARKERS = {
    "hindi", "hindi mein", "bol", "boliye", "bataiye", "samajh", "nahi", "haan", "acha", "theek",
    "kya", "kyun", "kaise", "kab", "kaun", "kahan", "hai", "hain", "tha", "thi", "the",
    "kar", "karo", "kar rahe", "baat", "call", "milenge", "do minute", "investment",
    "ghar", "flat", "property", "zaroorat", "chaiye", "chahiye", "mangta",
    "है", "नहीं", "मुझे", "आप", "क्या", "जी", "चाहिए", "करना", "बोलिए", "हाँ", "अच्छा", "ठीक",
}
MARATHI_MARKERS = {
    "marathi", "marathi madhe", "bol", "bola", "sanga", "sangal", "pahije", "ho", "nahi",
    "kai", "kasa", "kiva", "ani", "pan", "tar", "aahe", "aahet", "hote", "hoti", "hota",
    "karaycha", "kartoy", "boltoy", "boltey", "ghetlay", "pahata", "pahat",
    "mala", "tula", "aamhi", "amhi", "majha", "majhi", "majhe", "tujha", "tujhi", "tujhe",
    "kuthe", "kadhi", "kiti", "baghaychay", "ghyaychay", "vikaychay", "bhadane", 
    "zaga", "jaaga", "guntha", "kimmat", "navin", "juna", "changle", "changla",
    "आहे", "नाही", "माझ", "तुम्ह", "काय", "होय", "पाहिजे", "करू", "बोला", "हो", "सांगा",
    "मला", "तुला", "आम्ही", "माझा", "माझी", "माझे", "तुझा", "तुझी", "तुझे", "कुठे", "कधी", "किती",
    "बघायचंय", "घ्यायचंय", "विकायचंय", "भाड्याने", "जागा", "गुंठा", "किंमत", "नवीन", "जुना", "चांगले", "चांगला",
}
HINGLISH_MARKERS = (
    "aap", "apka", "apki", "haan", "han", "ji", "nahi", "nahin",
    "achha", "acha", "kya", "kaise", "karna", "chahiye", "chahiye",
    "thik", "theek", "boliye", "bataiye", "mera", "meri", "mujhe",
)
ROMAN_HINDI_MARKERS = (
    "main", "mai", "mera", "meri", "mere", "mujhe", "mje", "mujhko",
    "aap", "ap", "aapka", "aapki", "aapke", "tum", "tumhara", "tumhari",
    "haan", "han", "nahi", "nahin", "nhi", "kya", "kaunsa", "kaunsi",
    "kaise", "kitna", "kitni", "kitne", "chahiye", "dekh", "dekh raha",
    "dekh rahi", "raha", "rahi", "liye", "ke liye", "ke", "hai", "hoon",
    "khud", "apne liye",
    "rehne", "rehna", "batao", "bolo", "samjha",
    "samajh", "thoda", "bolenge", "pata", "abhi", "baad",
)
# Words that appear naturally in both English real-estate conversations AND
# Hindi transliteration. They must NOT count toward Hindi hit scores — otherwise
# a single "flat" or "property" from an English speaker will trigger a language switch.
_CROSS_LANGUAGE_WORDS = frozenset({
    "ghar", "flat", "plot", "property", "budget", "investment", "area",
    "location", "rent", "clear", "call", "investment", "milenge",
})
ENGLISH_STYLE_MARKERS = (
    "budget", "investment", "invest", "self use", "location", "property",
    "project", "site visit", "callback", "schedule", "timeline", "area",
    "price", "range", "premium", "options", "rent", "rental", "apartment",
)
LOCALIZED_TEMPLATE_MAP = {
    "Hey, this is Neha — I'm with the Real Estate team. Is this {{name}}?": {
        "hi": "Hi, Neha bol rahi hoon. Kya main {{name}} se baat kar rahi hoon?",
        "hinglish": "Hi, Neha bol rahi hoon. Kya main {{name}} se baat kar rahi hoon?",
    },
    "Is this a good time to speak?": {
        "hi": "Abhi baat karne ke liye do minute milenge?",
        "hinglish": "Abhi baat karne ke liye 2 minute milenge?",
    },
    "I actually came across your interest in property. Are you exploring for yourself or as an investment?": {
        "hi": "Aap property khud ke liye dekh rahe ho ya investment ke liye?",
        "hinglish": "Aap property khud ke liye dekh rahe ho ya investment ke liye?",
    },
    "Hello, this is Neha from the Real Estate AI team. Am I speaking with you?": {
        "hi": "Hi, Neha bol rahi hoon Real Estate team se. Kya main aapse baat kar rahi hoon?",
        "hinglish": "Hi, Neha bol rahi hoon Real Estate team se. Kya main aapse baat kar rahi hoon?",
    },
    "I'm calling about some premium property options. Would you have a moment?": {
        "hi": "Premium property options ke baare mein call kiya hai. Ek minute mil jayega?",
        "hinglish": "Premium property options ke baare mein call kiya hai. Ek minute milega?",
    },
    "Thank you for your time. Have a great day!": {
        "hi": "Time dene ke liye thanks. Aapka din achha rahe.",
        "hinglish": "Time dene ke liye thanks. Have a great day.",
    },
    "Do you have two minutes right now? I came across something that might actually be relevant for you.": {
        "hi": "Bas do minute milenge? Aapke liye ek relevant option tha.",
        "hinglish": "Bas 2 minute milenge? Aapke liye ek relevant option tha.",
    },
    "Are you currently looking to buy, rent, or invest in a property?": {
        "hi": "Aap abhi property kharidne, rent par lene, ya invest karne ke liye dekh rahe hain?",
        "hinglish": "Aap currently property buy, rent, ya invest karne ke liye dekh rahe hain?",
        "mr": "तुम्ही सध्या प्रॉपर्टी विकत घेण्यासाठी, भाड्याने घेण्यासाठी, किंवा इन्व्हेस्ट करण्यासाठी पाहत आहात का?",
    },
    "Got it — are you mainly looking for something to move into, or more of an investment angle?": {
        "hi": "Samajh gayi. Aap khud rehne ke liye dekh rahe ho ya investment angle se?",
        "hinglish": "Got it. Aap khud ke liye dekh rahe ho ya investment angle se?",
    },
    "Yeah, totally fair — budget matters. We do have some options in Hinjewadi and Mamurdi that are more accessible, with flexible payment plans. Worth a look?": {
        "hi": "Bilkul, budget matter karta hai. Hinjewadi aur Mamurdi mein kuch options hain jahan payment plan bhi flexible hai, dekhna chahoge?",
        "hinglish": "Bilkul, budget matter karta hai. Hinjewadi aur Mamurdi mein kuch options hain with flexible payment plans, dekhna chahoge?",
    },
    "Got it, no worries. Just so I'm not wasting your time — would it be okay if I sent you something on WhatsApp? You can look at it whenever it suits you.": {
        "hi": "Theek hai, koi issue nahi. Main WhatsApp par details bhej doon? Aap jab time mile tab dekh lena.",
        "hinglish": "No worries. Main WhatsApp par details bhej doon? Aap jab convenient ho tab dekh lena.",
    },
    "Which part of the city are you looking at — and roughly what budget should I work with?": {
        "hi": "Aap kis area mein dekh rahe hain — aur budget roughly kitna rahega?",
        "hinglish": "Aap kis area mein dekh rahe ho — aur budget roughly kitna rahega?",
    },
    "Which city or area are you considering?": {
        "hi": "Kaunsa city ya area dekh rahe ho?",
        "hinglish": "Kaunsa city ya area dekh rahe ho?",
    },
    "What budget range should I keep in mind?": {
        "hi": "Budget range roughly kitni rakhun?",
        "hinglish": "Budget range roughly kitni rakhun?",
    },
    "Actually, I have a property in {{location}} that fits your budget well. Would you like to visit it in person?": {
        "hi": "Mere paas {{location}} mein ek property hai jo aapke budget mein fit baithti hai. Kya aap use dekhne jaana chahenge?",
        "hinglish": "Mere paas {{location}} mein ek property hai jo aapke budget mein fit baithti hai. Kya aap visit karna chahenge?",
    },
    "What works better for you — weekend or a weekday? And any time preference?": {
        "hi": "Aapke liye weekend better rahega ya weekday? Aur koi time preference?",
        "hinglish": "Aapke liye weekend better rahega ya weekday? Aur koi time preference?",
    },
    "Done — I'll send you the location and directions on WhatsApp before {{timeline}}. Looking forward to it.": {
        "hi": "Done — main aapko {{timeline}} se pehle WhatsApp par location bhej dungi. Milte hain fir.",
        "hinglish": "Done — main aapko {{timeline}} se pehle WhatsApp par location bhej dungi. See you then.",
    },
    "All set — see you then. Have a good one!": {
        "hi": "Sab set hai — fir milte hain. Have a good one!",
        "hinglish": "Sab set hai — see you then. Have a good one!",
    },
    "No worries. When's a better time to catch you — morning, afternoon, or evening?": {
        "hi": "Koi baat nahi. Callback ke liye morning, afternoon ya evening mein kya better rahega?",
        "hinglish": "No worries. Callback ke liye morning, afternoon ya evening mein kya better rahega?",
    },
    "I'll ping you around {{timeline}} then. Take care!": {
        "hi": "Theek hai, main aapko {{timeline}} ke around call kar lungi. Take care.",
        "hinglish": "Theek hai, main aapko {{timeline}} ke around call kar lungi. Take care.",
    },
    "Alright, take care. Talk soon!": {
        "hi": "Theek hai, take care. Jaldi baat karte hain.",
        "hinglish": "Alright, take care. Jaldi baat karte hain.",
    },
    "Sure, I can help with that. Which area is the property in, and what kind of price are you targeting?": {
        "hi": "Bilkul, usmein help kar sakti hoon. Property kis area mein hai, aur aap kya price expect kar rahe ho?",
        "hinglish": "Sure, usmein help kar sakti hoon. Property kis area mein hai, aur aap kya price target kar rahe ho?",
    },
    "Got it — what type of property is it, roughly how old, and any standout features? I'll have someone from our team reach out with a proper eval.": {
        "hi": "Samajh gayi. Property ka type kya hai, roughly kitni purani hai, aur koi key feature? Hamari team ka koi person proper eval ke saath connect karega.",
        "hinglish": "Got it. Property type kya hai, roughly kitni purani hai, aur koi standout feature? Hamari team proper eval ke saath connect karegi.",
    },
    "No worries, I'll be quick — it's about a property inquiry from earlier. Do you have two minutes, or should I call back later?": {
        "hi": "Koi baat nahi, main jaldi bolti hoon. Ye pehle wali property inquiry ke baare mein hai, do minute hain ya main baad mein call karun?",
        "hinglish": "No worries, main quick rahoongi. Ye earlier property inquiry ke baare mein hai, 2 minute hain ya baad mein call karun?",
    },
    "Thanks for chatting — have a great rest of your day!": {
        "hi": "Baat karne ke liye thanks. Aapka din achha rahe.",
        "hinglish": "Baat karne ke liye thanks. Have a great day ahead.",
    },
    "No problem at all — take care!": {
        "hi": "Bilkul theek hai. Take care.",
        "hinglish": "No problem at all. Take care.",
    },
    "Sorry, I missed that. Just to clarify, are you looking to buy, rent, or invest in a property?": {
        "hi": "माफ़ कीजिये, मैं समझ नहीं पाई। क्या आप प्रॉपर्टी खरीदना, किराए पर लेना, या इन्वेस्ट करना चाहते हैं?",
        "hinglish": "Sorry, main samjh nahi paayi. Kya aap property buy karna, rent karna, ya invest karna chahte hain?",
        "mr": "माफ करा, मला समजलं नाही. तुम्ही प्रॉपर्टी खरेदी करायला, भाड्याने घ्यायला की इन्वेस्ट करायला बघताय?"
    },
    "Sorry, which area was that? Somewhere like Wakad or Baner, or maybe Hinjewadi?": {
        "hi": "Thoda clear bolenge? Agar open ho to Wakad, Baner, Hinjewadi ya Kharadi achhe options hain. Aap kis side dekh rahe ho?",
        "hinglish": "Thoda clear bolenge? Agar open ho to Wakad, Baner, Hinjewadi ya Kharadi achhe options hain. Aap kis side dekh rahe ho?",
    },
    "I didn't get the budget clearly. Are we looking around 50 lakhs, or perhaps closer to 2 crores?": {
        "hi": "Thoda clear bolenge? 50 lakh se 2 crore tak options hain. Aapka budget roughly kitna hai?",
        "hinglish": "Thoda clear bolenge? 50 lakh se 2 crore tak options hain. Aapka budget roughly kitna hai?",
    },
    "Could you repeat the property type? Is it a 2 BHK you're looking for, or something else?": {
        "hi": "Thoda clear bolenge? Aap 1 BHK, 2 BHK ya kuch aur dekh rahe ho?",
        "hinglish": "Thoda clear bolenge? Aap 1 BHK, 2 BHK ya kuch aur dekh rahe ho?",
    },
    "What works better for you — weekend or a weekday? And any time preference?": {
        "hi": "Thoda clear bolenge? Weekend better rahega ya weekday? Time ka bhi koi preference hai?",
        "hinglish": "Thoda clear bolenge? Weekend better rahega ya weekday? Time ka bhi koi preference hai?",
    },
    "That's alright. When would be a convenient time for a callback?": {
        "hi": "Koi baat nahi. Callback ke liye kaunsa time convenient rahega?",
        "hinglish": "Koi baat nahi. Callback ke liye kaunsa time convenient rahega?",
    },
    "No problem — are you thinking more budget-friendly, mid-range, or premium?": {
        "hi": "Koi issue nahi. Aap budget-friendly, mid-range ya premium mein kya prefer karoge?",
        "hinglish": "No problem. Aap budget-friendly, mid-range ya premium mein kya prefer karoge?",
    },
    "Popular areas include Wakad, Baner, Hinjewadi, and Kharadi. Which location interests you?": {
        "hi": "Popular options Wakad, Baner, Hinjewadi aur Kharadi mein hain. Aapko kaunsi location better lag rahi hai?",
        "hinglish": "Popular options Wakad, Baner, Hinjewadi aur Kharadi mein hain. Aapko kaunsi location better lag rahi hai?",
    },
    "Would next week work better for the visit?": {
        "hi": "Agar aapko theek lage to next week visit rakh lete hain?",
        "hinglish": "Agar theek lage to next week visit rakh lete hain?",
    },
    "Sorry about that. Thank you for your time. Goodbye.": {
        "hi": "Theek hai, time dene ke liye thanks. Namaste.",
        "hinglish": "Theek hai, time dene ke liye thanks. Bye.",
    },
    "Could you help me understand what you're looking for?": {
        "hi": "Aap exactly kis type ka option dekh rahe ho?",
        "hinglish": "Aap exactly kis type ka option dekh rahe ho?",
    },
    "Sorry, I didn't catch that clearly. Could you repeat that once?": {
        "hi": "Thoda clear bolenge? Main wahi se continue karti hoon.",
        "hinglish": "Thoda clear bolenge? Main wahi se continue karti hoon.",
    },
    "I'm sorry, I missed that. Could you say it again?": {
        "hi": "Maaf kijiyega, main sun nahi paayi. Ek baar aur bolenge?",
        "hinglish": "Maaf kijiyega, main sun nahi paayi. Ek baar aur bolenge?",
    },
    "Apologies, my line dropped for a second. What was that?": {
        "hi": "Shayad aawaz cut gayi thi. Kya kaha aapne?",
        "hinglish": "Shayad aawaz cut gayi thi. Kya kaha aapne?",
    },
    "Give me just one moment...": {
        "hi": "Ek second dijiye...",
        "hinglish": "Ek second dijiye...",
    },
}


@dataclass(frozen=True)
class UserTextAnalysis:
    original_text: str
    cleaned_text: str
    detected_language: str
    confidence: float
    actionable: bool
    reason: str
    latin_letters: int
    devanagari_letters: int
    unsupported_letters: int


CONTROL_TOKEN_REGEX = re.compile(r"<\|[a-zA-Z0-9_\-]+\|>")


def strip_stt_control_tokens(text: str) -> tuple[str, str | None]:
    """
    Strips STT/Whisper language and control tokens like <|hi|>, <|en|>, <|transcribe|>, <|hi|><|hi|>.
    Returns (cleaned_text, detected_control_language_code).
    """
    if not text:
        return "", None

    found_langs = []
    tokens = CONTROL_TOKEN_REGEX.findall(text)
    for token in tokens:
        tag = token.strip("<|>").lower()
        if tag in {"hi", "hindi"}:
            found_langs.append("hi")
        elif tag in {"en", "english"}:
            found_langs.append("en")
        elif tag in {"mr", "marathi"}:
            found_langs.append("mr")
        elif tag in {"hinglish"}:
            found_langs.append("hinglish")

    cleaned = CONTROL_TOKEN_REGEX.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    detected_lang = found_langs[0] if found_langs else None
    return cleaned, detected_lang


def _detect_explicit_language_request(text: str) -> str | None:
    t = (text or "").lower()
    # Check English requests
    if any(phrase in t for phrase in ["speak english", "speak in english", "talk in english", "continue in english", "in english", "english please", "english mein baat", "english me baat"]):
        return "en"
    # Check Hindi requests
    if any(phrase in t for phrase in ["speak hindi", "speak in hindi", "talk in hindi", "continue in hindi", "in hindi", "hindi please", "hindi mein baat", "hindi me baat", "hindi bol", "hindi me baat karo", "hindi mein baat karo"]):
        return "hi"
    # Check Marathi requests
    if any(phrase in t for phrase in ["speak marathi", "speak in marathi", "talk in marathi", "continue in marathi", "in marathi", "marathi please", "marathi mein baat", "marathi me baat", "marathi bol"]):
        return "mr"
    return None


def normalize_language_code(lang_str: str | None) -> str:
    """Normalize any user/dashboard/agent language string to canonical code ('en', 'hi', 'mr', 'hinglish')."""
    if not lang_str:
        return "en"
    l = str(lang_str).strip().lower()
    if l in {"hi", "hindi", "hin"}:
        return "hi"
    if l in {"mr", "marathi", "mar"}:
        return "mr"
    if l in {"hinglish", "hi-en", "hindi/english"}:
        return "hinglish"
    if l in {"en", "english", "eng"}:
        return "en"
    return "en"


class LanguageTracker:
    """Keep language switching stable across noisy turns. Hard Session Language Lock enforced."""

    def __init__(self, initial_language: str = "en"):
        self.current_language = normalize_language_code(initial_language)
        self._history: list[str] = []

    def observe(self, text: str, allowed_languages: list[str] = None) -> tuple[str, UserTextAnalysis]:
        if allowed_languages is None:
            allowed_languages = ["en", "hi", "mr", "hinglish"]

        analysis = analyze_user_text(text, fallback=self.current_language)
        
        # Log transcript and detected language for diagnostic telemetry ONLY
        logger.info(
            "\n[LANGUAGE DIAGNOSTICS]\n"
            "RAW TRANSCRIPT: \"%s\"\n"
            "DETECTED LANGUAGE: %s\n"
            "CONFIDENCE: %.2f\n"
            "LOCKED SESSION LANGUAGE: %s",
            text,
            analysis.detected_language,
            analysis.confidence,
            self.current_language
        )

        # Check ONLY explicit user spoken request (e.g. "speak in Hindi", "talk in English")
        explicit_req = _detect_explicit_language_request(text)
        if explicit_req in allowed_languages and explicit_req != self.current_language:
            self.current_language = explicit_req
            logger.info("Session language changed via explicit spoken request to: %s", self.current_language)

        return self.current_language, analysis


def analyze_user_text(text: str, fallback: str = "en") -> UserTextAnalysis:
    """Classify user text for language and whether it is safe to act on."""
    normalized_fallback = fallback if fallback in SUPPORTED_LANGUAGES else "en"
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return UserTextAnalysis(text, "", normalized_fallback, 0.0, False, "empty", 0, 0, 0)

    latin_letters = 0
    devanagari_letters = 0
    unsupported_letters = 0
    for ch in cleaned:
        if not ch.isalpha():
            continue
        if DEVANAGARI_RANGE[0] <= ch <= DEVANAGARI_RANGE[1]:
            devanagari_letters += 1
        elif ch.isascii():
            latin_letters += 1
        else:
            unsupported_letters += 1

    if latin_letters == 0 and devanagari_letters == 0 and unsupported_letters == 0:
        return UserTextAnalysis(
            text, cleaned, normalized_fallback, 0.0, False, "punctuation_only", 0, 0, 0
        )

    # Whitelist common Unicode punctuation Whisper sometimes inserts
    # (curly apostrophes/quotes, em-dashes, ellipsis) — these are NOT
    # foreign scripts and should not cause a transcript to be rejected.
    _PUNCT_WHITELIST = {
        '\u2019', '\u2018',  # curly apostrophes
        '\u201c', '\u201d',  # curly double quotes
        '\u2013', '\u2014',  # en-dash / em-dash
        '\u2026',            # ellipsis
        '\u00e9', '\u00e8', '\u00e0', '\u00e2',  # French accented vowels (common in names)
    }
    # Count only truly foreign-alphabet letters (not the whitelisted punctuation)
    adjusted_unsupported = sum(
        1 for ch in cleaned
        if ch.isalpha()
        and ch not in _PUNCT_WHITELIST
        and not (DEVANAGARI_RANGE[0] <= ch <= DEVANAGARI_RANGE[1])
        and not ch.isascii()
    )
    total_letters = latin_letters + devanagari_letters + adjusted_unsupported
    unsupported_ratio = adjusted_unsupported / total_letters if total_letters > 0 else 0.0

    # Only reject as unsupported_script if foreign chars dominate (>60%)
    # AND there is very little usable Latin or Devanagari content (<3 chars each).
    # This prevents over-dropping Hinglish turns that happen to contain a
    # curly apostrophe or a single accented character.
    if adjusted_unsupported > 0 and unsupported_ratio > 0.60 and latin_letters < 3 and devanagari_letters < 3:
        return UserTextAnalysis(
            text,
            cleaned,
            normalized_fallback,
            0.0,
            False,
            "unsupported_script",
            latin_letters,
            devanagari_letters,
            unsupported_letters,
        )

    if devanagari_letters > 0:
        marathi_hits = _count_markers(cleaned, MARATHI_MARKERS)
        hindi_hits = _count_markers(cleaned, HINDI_MARKERS)
        if marathi_hits > hindi_hits and marathi_hits > 0:
            return UserTextAnalysis(text, cleaned, "mr", 0.96, True, "clear_marathi", latin_letters, devanagari_letters, unsupported_letters)
        if hindi_hits > 0:
            return UserTextAnalysis(text, cleaned, "hi", 0.96, True, "clear_hindi", latin_letters, devanagari_letters, unsupported_letters)
        return UserTextAnalysis(text, cleaned, "hi", 0.84, True, "devanagari", latin_letters, devanagari_letters, unsupported_letters)

    latin_text = cleaned.casefold()
    hinglish_hits = _count_markers(latin_text, HINGLISH_MARKERS)
    roman_hindi_hits = _count_markers(latin_text, ROMAN_HINDI_MARKERS)
    english_style_hits = _count_markers(latin_text, ENGLISH_STYLE_MARKERS)
    english_words = re.findall(r"\b[a-z]{2,}\b", latin_text)

    # Subtract cross-language words from hits to avoid false positives when
    # English speakers say real-estate terms like "flat", "budget", "property".
    cross_hits = sum(1 for w in _CROSS_LANGUAGE_WORDS if re.search(rf"\b{re.escape(w)}\b", latin_text))
    effective_roman_hindi = max(0, roman_hindi_hits - cross_hits)

    # Raise thresholds from 1/2 → 3/4 to prevent single-word language flips.
    if effective_roman_hindi >= 4 and english_style_hits == 0:
        return UserTextAnalysis(text, cleaned, "hi", 0.86, True, "roman_hindi", latin_letters, devanagari_letters, unsupported_letters)
    if effective_roman_hindi >= 3 and english_style_hits >= 1:
        return UserTextAnalysis(text, cleaned, "hinglish", 0.88, True, "clear_hinglish", latin_letters, devanagari_letters, unsupported_letters)
    if hinglish_hits >= 3 or (hinglish_hits >= 2 and english_style_hits >= 2):
        return UserTextAnalysis(text, cleaned, "hinglish", 0.85, True, "clear_hinglish", latin_letters, devanagari_letters, unsupported_letters)
    # Single roman-hindi word is never enough to classify as Hindi — fall through to English
    if effective_roman_hindi == 2 and english_style_hits == 0 and word_count >= 6:
        return UserTextAnalysis(text, cleaned, "hi", 0.72, True, "possible_roman_hindi", latin_letters, devanagari_letters, unsupported_letters)
    
    # C5 FIX: Removed the hinglish_hits == 1 check so single Hinglish filler words 
    # fall through to English, preventing permanent language switching on "haan".

    confidence = 0.87 if len(english_words) >= 2 else 0.68
    return UserTextAnalysis(text, cleaned, "en", confidence, True, "latin_text", latin_letters, devanagari_letters, unsupported_letters)


def detect_language_from_text(text: str, fallback: str = "en") -> str:
    """Infer the user's language from a short utterance."""
    return analyze_user_text(text, fallback=fallback).detected_language


def is_actionable_user_text(text: str, fallback: str = "en") -> bool:
    """Return whether a transcript is safe to send into the conversation state machine."""
    return analyze_user_text(text, fallback=fallback).actionable


def get_language_label(language: str) -> str:
    normalized = language if language in SUPPORTED_LANGUAGES else "en"
    return {
        "en": "English",
        "hi": "Hindi",
        "mr": "Marathi",
        "hinglish": "Hinglish",
    }[normalized]


def get_language_instruction(language: str) -> str:
    """Return a concise generation directive for the active language."""
    normalized = normalize_language_code(language)
    instructions = {
        "en": (
            "Current conversation language: English. Respond in clear, natural English. Maintain English throughout."
        ),
        "hi": (
            "Current conversation language: Hindi.\n"
            "Respond ONLY in natural spoken Hindi. Do NOT translate the user's message into English before responding.\n"
            "Do NOT switch to English automatically even if the user uses English words or real-estate terms.\n"
            "Maintain Hindi throughout the entire conversation unless explicitly requested."
        ),
        "mr": (
            "Current conversation language: Marathi. Respond in conversational, respectful Marathi. Keep it natural and polished."
        ),
        "hinglish": (
            "Current conversation language: Hinglish.\n"
            "Respond naturally in conversational Hinglish (Hindi grammar with English education terms like 'BCA', 'MCA', 'course', 'college', 'location').\n"
            "Do NOT automatically convert the conversation to full English. Maintain Hinglish throughout."
        ),
    }
    return instructions[normalized]


EDUCATION_VOCABULARY_MAP = {
    r"\baarohi\b": "Aarohi",
    r"\b(bca|b\.c\.a\.)\b": "BCA",
    r"\b(mca|m\.c\.a\.)\b": "MCA",
    r"\b(btech|b\.tech|b\.\s*tech|b\.\s*e\.|be)\b": "B.Tech",
    r"\b(mtech|m\.tech|m\.\s*tech|m\.\s*e\.|me)\b": "M.Tech",
    r"\b(mba|m\.b\.a\.)\b": "MBA",
    r"\b(bcom|b\.com)\b": "B.Com",
    r"\b(bsc|b\.sc)\b": "B.Sc",
    r"\b(msc|m\.sc)\b": "M.Sc",
    r"\b(mbbs|m\.b\.b\.s\.)\b": "MBBS",
    r"\b(12th|12\s*th|hsc|intermediate|senior\s*secondary)\b": "12th",
    r"\b(computer\s*science|cs)\b": "Computer Science",
    r"\b(artificial\s*intelligence|ai)\b": "AI",
    r"\b(machine\s*learning|ml)\b": "Machine Learning",
    r"\b(data\s*science|data\s*analytics)\b": "Data Science",
    r"\b(cyber\s*security|cybersecurity)\b": "Cyber Security",
    r"\b(ielts|i\.e\.l\.t\.s\.)\b": "IELTS",
    r"\b(toefl|t\.o\.e\.f\.l\.)\b": "TOEFL",
    r"\b(gre)\b": "GRE",
    r"\b(gmat)\b": "GMAT",
    r"\b(study\s*abroad|abroad|foreign|foreign\s*country)\b": "study abroad",
    r"\b(pune|pune\s*mein|pune\s*me|पुणे)\b": "Pune",
    r"\b(jaipur|jaipur\s*mein|jaipur\s*me|जयपुर|जयपूर)\b": "Jaipur",
    r"\b(jodhpur|jodhpur\s*mein|jodhpur\s*me|जोधपुर)\b": "Jodhpur",
    r"\b(mumbai|mumbai\s*mein|mumbai\s*me|मुंबई)\b": "Mumbai",
    r"\b(delhi|delhi\s*mein|delhi\s*me|दिल्ली)\b": "Delhi",
    r"\b(bangalore|bengaluru|बेंगलुरु|बैंगलोर)\b": "Bangalore",
    r"\b(usa|united\s*states|america)\b": "USA",
    r"\b(uk|united\s*kingdom|england)\b": "UK",
    r"\b(canada)\b": "Canada",
    r"\b(germany)\b": "Germany",
    r"\b(australia)\b": "Australia",
}

REAL_ESTATE_VOCABULARY_MAP = {
    r"\b(suncity|sun\s*city)\b": "Suncity",
    r"\b(1\s*bhk|1bhk|one\s*bhk)\b": "1 BHK",
    r"\b(2\s*bhk|2bhk|two\s*bhk)\b": "2 BHK",
    r"\b(3\s*bhk|3bhk|three\s*bhk)\b": "3 BHK",
    r"\b(4\s*bhk|4bhk|four\s*bhk)\b": "4 BHK",
    r"\b(wakad|wakad\s*mein|wakad\s*me|वाकड)\b": "Wakad",
    r"\b(baner|baner\s*mein|baner\s*me|बानेर)\b": "Baner",
    r"\b(hinjewadi|hinjawadi|हिंजवडी)\b": "Hinjewadi",
    r"\b(mamurdi|मामुर्डी)\b": "Mamurdi",
    r"\b(kharadi|खराडी)\b": "Kharadi",
    r"\b(pune|pune\s*mein|pune\s*me|पुणे)\b": "Pune",
    r"\b(jaipur|jaipur\s*mein|jaipur\s*me|जयपुर|जयपूर)\b": "Jaipur",
    r"\b(jodhpur|jodhpur\s*mein|jodhpur\s*me|जोधपुर)\b": "Jodhpur",
    r"\b(mumbai|mumbai\s*mein|mumbai\s*me|मुंबई)\b": "Mumbai",
    r"\b(delhi|delhi\s*mein|delhi\s*me|दिल्ली)\b": "Delhi",
}


def normalize_domain_vocabulary(user_text: str, domain: str = "real_estate") -> str:
    """Normalize domain-specific terms in user transcript based on active domain."""
    if not user_text:
        return ""
    text = user_text
    vocab_map = EDUCATION_VOCABULARY_MAP if domain == "education" else REAL_ESTATE_VOCABULARY_MAP
    for pattern, replacement in vocab_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def validate_response_language(text: str, expected_lang: str) -> tuple[bool, str]:
    """
    Validates if the generated LLM text complies with expected conversation language.
    Returns (is_valid: bool, reason: str).
    """
    if not text or not text.strip():
        return True, "empty"
    
    norm_lang = normalize_language_code(expected_lang)
    if norm_lang == "en":
        return True, "english_expected"

    has_devanagari = any('\u0900' <= ch <= '\u097f' for ch in text)
    clean_lower = text.lower()
    hindi_marker_hits = sum(1 for word in ["namaste", "aap", "chahiye", "hai", "hain", "hoon", "kar", "karte", "hum", "sab", "rahe", "ho", "ji", "samajh", "bataiye", "bol", "boliye", "bhej", "raha", "rahi"] if re.search(rf"\b{word}\b", clean_lower))

    if norm_lang == "hi":
        if has_devanagari or hindi_marker_hits >= 1:
            return True, "valid_hindi"
        words = [w for w in re.findall(r"\b[a-z]+\b", clean_lower) if w not in {"suncity", "apartments", "bhk", "jaipur", "jodhpur", "madurai", "wakad", "baner", "rera"}]
        if len(words) >= 4 and hindi_marker_hits == 0 and not has_devanagari:
            return False, "Expected Hindi, but generated response was in English."
            
    elif norm_lang == "hinglish":
        if has_devanagari or hindi_marker_hits >= 1:
            return True, "valid_hinglish"
        words = [w for w in re.findall(r"\b[a-z]+\b", clean_lower) if w not in {"suncity", "apartments", "bhk", "jaipur", "jodhpur", "madurai", "wakad", "baner", "rera"}]
        if len(words) >= 4 and hindi_marker_hits == 0:
            return False, "Expected Hinglish, but generated response was in English."

    return True, "valid"


def localize_template(template: str, language: str) -> str:
    """Map shared-flow English templates to Hindi/Hinglish without changing the flow."""
    normalized = language if language in SUPPORTED_LANGUAGES else "en"
    if normalized not in {"hi", "hinglish", "mr"}:
        return template
    variants = LOCALIZED_TEMPLATE_MAP.get(template)
    if not variants:
        return template
    return variants.get(normalized, template)


def _count_markers(text: str, markers: tuple[str, ...]) -> int:
    count = 0
    for marker in markers:
        # H2 FIX: \b only works on ASCII words. For Devanagari, use plain containment check.
        if any('\u0900' <= ch <= '\u097f' for ch in marker):
            if marker in text:
                count += 1
        else:
            if re.search(rf"\b{re.escape(marker)}\b", text):
                count += 1
    return count

