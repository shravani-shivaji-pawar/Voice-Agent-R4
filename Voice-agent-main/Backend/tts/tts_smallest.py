"""
tts_smallest.py — Smallest AI Lightning v3.1 & v3.1 Pro (Waves) REST TTS Adapter.

File Path: Backend/tts/tts_smallest.py

Contract: generate_speech_stream(text, preferred_language, agent_id, speaker, model) -> Iterator[bytes]
          Yields raw PCM16 mono chunks at 24kHz.

API Docs: https://docs.smallest.ai
Endpoints:
  - POST https://api.smallest.ai/waves/v1/tts
  - GET  https://api.smallest.ai/waves/v1/get_voices
Auth: Authorization: Bearer SMALLEST_API_KEY
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Iterator, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration & Endpoints ────────────────────────────────────────────────
SMALLEST_TTS_ENDPOINT = "https://api.smallest.ai/waves/v1/tts"
SMALLEST_VOICES_ENDPOINT = "https://api.smallest.ai/waves/v1/get_voices"
DEFAULT_MODEL = "lightning_v3.1"
SAMPLE_RATE = 24_000
CHUNK_BYTES = 2048

SUPPORTED_MODELS = [
    {"id": "lightning_v3.1", "name": "Lightning v3.1", "description": "Ultra-low latency model for real-time voice agents"},
    {"id": "lightning_v3.1_pro", "name": "Lightning v3.1 Pro", "description": "High-prosody premium model for expressive human-like delivery"},
]

ALL_LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "hi", "name": "Hindi"},
    {"code": "mr", "name": "Marathi"},
    {"code": "ta", "name": "Tamil"},
    {"code": "te", "name": "Telugu"},
    {"code": "kn", "name": "Kannada"},
    {"code": "ml", "name": "Malayalam"},
    {"code": "gu", "name": "Gujarati"},
    {"code": "pa", "name": "Punjabi"},
    {"code": "bn", "name": "Bengali"},
    {"code": "or", "name": "Odia"},
]

# Language normalization mapping
LANGUAGE_MAP: dict[str, str] = {
    "en": "en", "english": "en",
    "hi": "hi", "hindi": "hi", "hinglish": "hi",
    "mr": "mr", "marathi": "mr",
    "ta": "ta", "tamil": "ta",
    "te": "te", "telugu": "te",
    "kn": "kn", "kannada": "kn",
    "ml": "ml", "malayalam": "ml",
    "bn": "bn", "bengali": "bn",
    "gu": "gu", "gujarati": "gu",
    "pa": "pa", "punjabi": "pa",
    "or": "or", "odia": "or",
}

# ── Verified Static Voice Catalog Fallback ───────────────────────────────────
# Official Smallest AI voice catalog mapped by voice_id, model compatibility,
# supported languages, gender, and accent.
FALLBACK_VOICE_CATALOG: List[Dict[str, Any]] = [
    # ── Lightning v3.1 Voices (Indian Accent Priority) ────────────────────────
    {
        "voice_id": "anika",
        "name": "Anika",
        "gender": "female",
        "accent": "Indian",
        "description": "Sales & Conversational — Natural, warm female voice",
        "models": ["lightning_v3.1", "lightning_v3.1_pro"],
        "languages": ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn", "or"],
    },
    {
        "voice_id": "devansh",
        "name": "Devansh",
        "gender": "male",
        "accent": "Indian",
        "description": "Sales & Professional — Clear, confident male voice",
        "models": ["lightning_v3.1", "lightning_v3.1_pro"],
        "languages": ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn", "or"],
    },
    {
        "voice_id": "divya",
        "name": "Divya",
        "gender": "female",
        "accent": "Indian",
        "description": "Customer Support — Friendly, clear tone",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr", "gu", "bn"],
    },
    {
        "voice_id": "karan",
        "name": "Karan",
        "gender": "male",
        "accent": "Indian",
        "description": "Insurance & Finance — Professional, grounded male tone",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr", "ta", "te"],
    },
    {
        "voice_id": "avni",
        "name": "Avni",
        "gender": "female",
        "accent": "Indian",
        "description": "Conversational — Polished, approachable female voice",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr", "pa", "gu"],
    },
    {
        "voice_id": "dhruv",
        "name": "Dhruv",
        "gender": "male",
        "accent": "Indian",
        "description": "Sales & Narration — Deep, articulate male voice",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr", "kn", "te"],
    },
    {
        "voice_id": "kavya",
        "name": "Kavya",
        "gender": "female",
        "accent": "Indian",
        "description": "Real Estate & Support — Confident female tone",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr", "ta", "ml"],
    },
    {
        "voice_id": "vivaan",
        "name": "Vivaan",
        "gender": "male",
        "accent": "Indian",
        "description": "Conversational — Energetic, youthful male voice",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr", "pa"],
    },
    {
        "voice_id": "naina",
        "name": "Naina",
        "gender": "female",
        "accent": "Indian",
        "description": "Educational & Narration — Calm, clear female voice",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr", "bn", "gu"],
    },
    {
        "voice_id": "arjun",
        "name": "Arjun",
        "gender": "male",
        "accent": "Indian",
        "description": "Executive & Counseling — Authoritative, reassuring male voice",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr", "te", "ta"],
    },
    {
        "voice_id": "siya",
        "name": "Siya",
        "gender": "female",
        "accent": "Indian",
        "description": "Support — Polite, conversational tone",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr"],
    },
    {
        "voice_id": "veer",
        "name": "Veer",
        "gender": "male",
        "accent": "Indian",
        "description": "Customer Support — Friendly, steady male tone",
        "models": ["lightning_v3.1"],
        "languages": ["en", "hi", "mr"],
    },

    # ── Lightning v3.1 Pro Voices (High Prosody & Expressiveness) ──────────────
    {
        "voice_id": "meher",
        "name": "Meher",
        "gender": "female",
        "accent": "Indian",
        "description": "Pro Expressive — Premium warm conversational female voice",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn", "or"],
    },
    {
        "voice_id": "diya",
        "name": "Diya",
        "gender": "female",
        "accent": "Indian",
        "description": "Pro Conversational — Natural, highly expressive female tone",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
    },
    {
        "voice_id": "arav",
        "name": "Arav",
        "gender": "male",
        "accent": "Indian",
        "description": "Pro Executive — Rich, articulate male voice for sales & counseling",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn", "or"],
    },
    {
        "voice_id": "kabir",
        "name": "Kabir",
        "gender": "male",
        "accent": "Indian",
        "description": "Pro Smooth — Calm, human-like male voice with premium cadence",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa"],
    },
    {
        "voice_id": "anika_pro",
        "name": "Anika Pro",
        "gender": "female",
        "accent": "Indian",
        "description": "Pro Sales — Enhanced pitch stability & prosody",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn", "or"],
    },
    {
        "voice_id": "devansh_pro",
        "name": "Devansh Pro",
        "gender": "male",
        "accent": "Indian",
        "description": "Pro Commercial — High-clarity executive voice",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn", "or"],
    },
    {
        "voice_id": "rachel",
        "name": "Rachel",
        "gender": "female",
        "accent": "American",
        "description": "Pro Natural — Clear US accent female voice",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en"],
    },
    {
        "voice_id": "emily",
        "name": "Emily",
        "gender": "female",
        "accent": "British",
        "description": "Pro Professional — Elegant UK accent female voice",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en"],
    },
    {
        "voice_id": "james",
        "name": "James",
        "gender": "male",
        "accent": "American",
        "description": "Pro Corporate — Professional US accent male voice",
        "models": ["lightning_v3.1_pro"],
        "languages": ["en"],
    },
]

_CACHED_CATALOG: List[Dict[str, Any]] | None = None
_LAST_CATALOG_FETCH: float = 0.0
CATALOG_CACHE_TTL_SECONDS = 3600.0  # 1 hour in-memory cache


def fetch_voice_catalog(api_key: str | None = None) -> List[Dict[str, Any]]:
    """
    Fetch the available voice catalog from Smallest AI API or return cached/fallback catalog.
    Handles API outages gracefully without crashing.
    """
    global _CACHED_CATALOG, _LAST_CATALOG_FETCH

    now = time.time()
    if _CACHED_CATALOG and (now - _LAST_CATALOG_FETCH) < CATALOG_CACHE_TTL_SECONDS:
        return _CACHED_CATALOG

    key = api_key or os.getenv("SMALLEST_API_KEY", "").strip()
    if key:
        try:
            headers = {"Authorization": f"Bearer {key}"}
            resp = requests.get(SMALLEST_VOICES_ENDPOINT, headers=headers, timeout=4.0)
            if resp.status_code == 200:
                data = resp.json()
                raw_voices = data.get("voices") or data.get("data") or []
                if isinstance(raw_voices, list) and len(raw_voices) > 0:
                    parsed_catalog: List[Dict[str, Any]] = []
                    for v in raw_voices:
                        vid = v.get("voice_id") or v.get("id")
                        if not vid:
                            continue
                        parsed_catalog.append({
                            "voice_id": vid,
                            "name": v.get("name") or v.get("display_name") or vid.capitalize(),
                            "gender": (v.get("gender") or "female").lower(),
                            "accent": v.get("accent") or ("Indian" if any(lang in (v.get("languages") or []) for lang in ["hi", "mr", "ta"]) else "Global"),
                            "description": v.get("description") or f"{vid.capitalize()} voice",
                            "models": v.get("models") or ["lightning_v3.1", "lightning_v3.1_pro"],
                            "languages": v.get("languages") or ["en", "hi"],
                        })
                    if parsed_catalog:
                        _CACHED_CATALOG = parsed_catalog
                        _LAST_CATALOG_FETCH = now
                        logger.info("[SmallestTTS] Successfully loaded %d voices from Smallest AI API", len(parsed_catalog))
                        return parsed_catalog
        except Exception as exc:
            logger.warning("[SmallestTTS] Could not fetch live voice catalog from API: %s; using fallback catalog.", exc)

    _CACHED_CATALOG = FALLBACK_VOICE_CATALOG
    _LAST_CATALOG_FETCH = now
    return FALLBACK_VOICE_CATALOG


def get_voices_for_model_and_language(model: str = DEFAULT_MODEL, language: str = "en") -> List[Dict[str, Any]]:
    """
    Return all voices compatible with both the specified model AND language.
    Prioritizes Indian accent voices first.
    """
    catalog = fetch_voice_catalog()
    norm_lang = _resolve_language_code(language)
    norm_model = model.strip().lower() if model else DEFAULT_MODEL

    matched: List[Dict[str, Any]] = []
    for v in catalog:
        models = [m.lower() for m in v.get("models", [])]
        languages = [l.lower() for l in v.get("languages", [])]

        if norm_model in models and (norm_lang in languages or "all" in languages):
            matched.append(v)

    # Sort Indian accent voices first
    matched.sort(key=lambda x: 0 if x.get("accent") == "Indian" else 1)
    return matched


def _resolve_language_code(preferred_language: str | None) -> str:
    """Map language string to ISO 2-letter language code."""
    if not preferred_language:
        return "en"
    lang = preferred_language.strip().lower()
    return LANGUAGE_MAP.get(lang, "en")


def _resolve_speaker(speaker: str | None, model: str = DEFAULT_MODEL, language: str = "en") -> str:
    """
    Resolve requested speaker/voice to a valid, model-compatible Smallest AI voice_id.
    Ensures model/voice pairing is 100% correct.
    """
    if speaker:
        key = speaker.strip().lower()
        # Direct match check in catalog
        catalog = fetch_voice_catalog()
        for v in catalog:
            if v["voice_id"].lower() == key:
                # If model compatible, return direct
                if model.lower() in [m.lower() for m in v.get("models", [])]:
                    return v["voice_id"]

    # Fallback: pick the first compatible voice for model & language
    compatible = get_voices_for_model_and_language(model=model, language=language)
    if compatible:
        return compatible[0]["voice_id"]

    # Final hard defaults per model
    if model == "lightning_v3.1_pro":
        return "meher"
    return "anika"


def clean_text_for_tts(text: str) -> str:
    """
    Clean text for spoken TTS generation:
    - Strips markdown formatting (*, **, #, bullet points, blockquotes, code blocks)
    - Removes emojis and hidden metadata
    - Preserves numbers, currency, dates, proper nouns, and addresses.
    """
    if not text:
        return ""

    cleaned = text
    # Remove markdown code blocks & JSON
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    cleaned = re.sub(r"`[^`]*`", "", cleaned)
    # Remove bold, italics, headers, bullet points
    cleaned = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    # Remove URL links
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    # Normalize excessive whitespace & linebreaks
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# Persistent HTTP Session for connection reuse & Keep-Alive
_SESSION: requests.Session | None = None


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=1,
        )
        _SESSION.mount("https://", adapter)
        _SESSION.mount("http://", adapter)
    return _SESSION


def generate_speech_stream(
    text: str,
    preferred_language: str | None = None,
    agent_id: str = "default",
    speaker: str | None = None,
    model: str | None = None,
) -> Iterator[bytes]:
    """
    Synthesize speech using the Smallest AI REST API (supports lightning_v3.1 and lightning_v3.1_pro).
    Yields raw PCM16 mono chunks at 24 kHz.
    """
    cleaned_text = clean_text_for_tts(text)
    if not cleaned_text:
        return

    api_key = os.getenv("SMALLEST_API_KEY", "").strip()
    if not api_key:
        logger.error("[SmallestTTS] SMALLEST_API_KEY environment variable is missing or empty.")
        return

    selected_model = (model or os.getenv("SMALLEST_MODEL") or DEFAULT_MODEL).strip().lower()
    if selected_model not in ["lightning_v3.1", "lightning_v3.1_pro"]:
        selected_model = DEFAULT_MODEL

    lang_code = _resolve_language_code(preferred_language)
    voice_id = _resolve_speaker(speaker, model=selected_model, language=lang_code)

    payload = {
        "text": cleaned_text,
        "voice_id": voice_id,
        "model": selected_model,
        "sample_rate": SAMPLE_RATE,
        "language": lang_code,
        "speed": 1.0,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start_time = time.perf_counter()
    first_chunk_time: float | None = None
    total_bytes = 0
    session = _get_session()

    try:
        response = session.post(
            SMALLEST_TTS_ENDPOINT,
            json=payload,
            headers=headers,
            stream=True,
            timeout=5.0,
        )
        response.raise_for_status()

        ttfb_ms = (time.perf_counter() - start_time) * 1000.0
        header_stripped = False
        buffer = bytearray()

        for raw_chunk in response.iter_content(chunk_size=CHUNK_BYTES):
            if not raw_chunk:
                continue

            if not header_stripped:
                buffer.extend(raw_chunk)
                if len(buffer) >= 44:
                    pcm_data = bytes(buffer[44:]) if buffer[:4] == b"RIFF" else bytes(buffer)
                    buffer.clear()
                    header_stripped = True
                    if pcm_data:
                        if first_chunk_time is None:
                            first_chunk_time = time.perf_counter()
                        total_bytes += len(pcm_data)
                        yield pcm_data
            else:
                if first_chunk_time is None:
                    first_chunk_time = time.perf_counter()
                total_bytes += len(raw_chunk)
                yield raw_chunk

        if buffer and not header_stripped:
            pcm_data = bytes(buffer[44:]) if buffer[:4] == b"RIFF" and len(buffer) > 44 else bytes(buffer)
            if pcm_data:
                if first_chunk_time is None:
                    first_chunk_time = time.perf_counter()
                total_bytes += len(pcm_data)
                yield pcm_data

        ttfa_ms = ((first_chunk_time - start_time) * 1000.0) if first_chunk_time is not None else ttfb_ms
        total_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            "[SmallestTTS] TTFB=%.1fms | TTFA=%.1fms | Total=%.1fms | %d PCM bytes | model=%s | lang=%s | voice=%s",
            ttfb_ms,
            ttfa_ms,
            total_ms,
            total_bytes,
            selected_model,
            lang_code,
            voice_id,
        )

    except requests.exceptions.HTTPError as http_err:
        logger.error(
            "[SmallestTTS] HTTP Error (%s): %s",
            response.status_code,
            response.text[:500] if hasattr(response, "text") else str(http_err),
        )
    except requests.exceptions.Timeout:
        logger.error("[SmallestTTS] Request timed out calling Smallest AI API after 5s.")
    except requests.exceptions.RequestException as req_err:
        logger.error("[SmallestTTS] Request failed: %s", req_err)
    except Exception as exc:
        logger.error("[SmallestTTS] Unexpected synthesis error: %s", exc, exc_info=True)
