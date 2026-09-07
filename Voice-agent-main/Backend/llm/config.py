"""
LLM configuration constants.

All tunable parameters for the LLM (Groq) integration.
Change values here to adjust model, temperature, token limits, etc.
without touching any logic code.

Set GROQ_API_KEY via the environment variable:
  Windows:  $env:GROQ_API_KEY = "your_key_here"
  Linux:    export GROQ_API_KEY="your_key_here"
"""

import os
from dotenv import load_dotenv

load_dotenv() # Load variables from .env if it exists

# ── API ────────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── Model ──────────────────────────────────────────────────────────────────────
# Active default models (fastest, low-latency for voice turns):
#   "groq/compound-mini"     - Groq's active fast mini model
#   "gpt-4o-mini"            - OpenAI's smallest fast model (when OPENAI_API_KEY is active)
MODEL_NAME: str = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
FAST_MODEL_NAME: str = os.getenv("LLM_FAST_MODEL", "openai/gpt-oss-120b")
VERSATILE_MODEL_NAME: str = os.getenv("LLM_VERSATILE_MODEL", "openai/gpt-oss-120b")

# ── Generation Parameters ──────────────────────────────────────────────────────
TEMPERATURE: float = 0.35      # balanced: not robotic (0.0) but not hallucinating (>0.7)
MAX_TOKENS: int = 400           # enough for complete reasoning + voice response content
TOP_P: float = 0.9             # slight nucleus cap for consistency

# ── Retry & Timeout ────────────────────────────────────────────────────────────
REQUEST_TIMEOUT_S: int = 6     # tighter: 8→6s to fail fast and not block the pipeline
MAX_RETRIES: int = 2           # Number of retries on transient failure

# Runtime response shaping
MAX_HISTORY_MESSAGES: int = 10  # trimmed from 12 for faster context processing
MAX_RESPONSE_SENTENCES: int = 2
MAX_RESPONSE_WORDS: int = 30

ENABLE_SINGLE_CALL_FAST_PATH: bool = True

# Phrase-constrained LLM response composition
PHRASE_RESPONSE_MAX_TOKENS: int = 120
PHRASE_RESPONSE_TEMPERATURE: float = 0.70

# ── Supported Languages ────────────────────────────────────────────────────────
# Matches the STT module's language support
SUPPORTED_LANGUAGES: list[str] = ["en", "hi", "mr", "hinglish"]
DEFAULT_LANGUAGE: str = "en"
