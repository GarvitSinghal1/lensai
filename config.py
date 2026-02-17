"""
Lens AI — Central Configuration
AI News Video Factory that scrapes, fact-checks, and generates videos.
Loads environment variables and defines all constants.
"""

import os
from pathlib import Path
# ─── Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "video_creation" / "output"
TEMP_DIR = BASE_DIR / "video_creation" / "temp"
DB_DIR = BASE_DIR / "collection" / "db"
DB_PATH = Path(os.getenv("DB_PATH_OVERRIDE")) if os.getenv("DB_PATH_OVERRIDE") else DB_DIR / "news.db"
HISTORY_DIR = BASE_DIR / "collection" / "history"

# Load .env (explicit path)
from dotenv import load_dotenv
env_path = BASE_DIR / ".env"
try:
    load_dotenv(dotenv_path=env_path, verbose=True)
except Exception as e:
    print(f"DEBUG: Could not load .env file via dotenv: {e}")

# Manual fallback for .env loading (if dotenv fails)
if not os.getenv("HF_TOKEN"):
    print("DEBUG: Attempting manual .env parsing (fallback)...")
    try:
        env_content = env_path.read_text()
        for line in env_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            # Remove quotes if present
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            if v.startswith("'") and v.endswith("'"):
                v = v[1:-1]
            os.environ[k] = v
        print("DEBUG: Manual .env parsing successful.")
    except Exception as e:
        print(f"DEBUG: Manual .env parsing failed: {e}")

# Debug: Print loaded keys (masked)
print(f"DEBUG: Loading .env from {env_path}")
print("DEBUG: Loaded Environment Variables:")
for key in os.environ:
    if "HF_TOKEN" in key or "GROQ" in key:
        val = os.environ[key]
        masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
        print(f"  {key}: {masked}")  # Stores past topic analyses for follow-ups

# Create directories
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

# ─── API Keys ────────────────────────────────────────────
# ─── API Keys ────────────────────────────────────────────
# Support multiple keys for rotation (Follow-the-Sun / Free Tier Cycling)
HF_TOKENS = []

# 1. Primary key (legacy preference order)
_primary = os.getenv("hff_key") or os.getenv("HF_TOKEN")
if _primary:
    HF_TOKENS.append(_primary)

# 2. Additional numbered keys (HF_TOKEN_1 ... HF_TOKEN_10 OR HF_TOKEN1 ... HF_TOKEN10)
for i in range(1, 11):
    _token = os.getenv(f"HF_TOKEN_{i}") or os.getenv(f"HF_TOKEN{i}")
    if _token and _token.strip() and _token not in HF_TOKENS:
        HF_TOKENS.append(_token.strip())

if not HF_TOKENS:
    HF_TOKENS = [""] # Fallback to empty string if no keys found

HF_API_KEY = HF_TOKENS[0] # Default to first key for legacy compatibility

# ─── HF API Config ──────────────────────────────────────
# Standard Inference API (router didn't work for MMS/SpeechT5)
HF_API_BASE = "https://api-inference.huggingface.co/models"
HF_API_TIMEOUT = 180               # Seconds to wait for HF model response (K2.5 needs more)
HF_MAX_RETRIES = 3                 # Retry failed API calls

# ─── Groq API Config ────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_KEY") or os.getenv("GROQ_API_KEY")

# ─── LLM Model Config ────────────────────────────────────
# Text generation (using Groq)
# Kimi K2 (Groq provider)
LLM_MODEL = "moonshotai/kimi-k2-instruct-0905"
# Fallback models (if Groq fails or rate limited)
LLM_FALLBACK = "llama-3.1-70b-versatile" # Good alternative on Groq
LLM_FALLBACK_2 = "mixtral-8x7b-32768"

# TTS (text-to-speech) — Using Kokoro-82M via Replicate provider
TTS_MODEL = "hexgrad/Kokoro-82M" 
TTS_API_URL = ""
TTS_FALLBACK = "" 
TTS_FALLBACK_2 = ""

# Image generation (Flux 2 is paid, fallback to SD v1.5 for free tier)
# Image generation (Flux 1 Schnell is fast and high quality)
IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell" 
IMAGE_STYLE_SUFFIX = "cinematic lighting, realistic, 4k, detailed, dramatic angle"
IMAGE_NEGATIVE_PROMPT = "blur, haze, deformed, ugly, cartoon, anime, text, watermark"
IMAGE_FALLBACK = "stabilityai/stable-diffusion-xl-base-1.0"
IMAGE_FALLBACK_2 = "stabilityai/stable-diffusion-2-1"

# TTS Fallback flags
ENABLE_GTTS_FALLBACK = True

# Sentence embeddings (runs locally, no API cost)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ─── Scraping Config ────────────────────────────────────
MAX_ARTICLE_AGE_HOURS = 6          # Only process articles from the last N hours
SCRAPE_TIMEOUT = 15                # Seconds per request
SCRAPE_DELAY = 0.5                 # Seconds between article extractions (rate limit)
MAX_WORKERS = 8                    # Parallel RSS feed fetchers

# ─── Clustering Config ───────────────────────────────────
CLUSTER_SIMILARITY_THRESHOLD = 0.65  # Articles above this similarity → same topic
DEDUP_SIMILARITY_THRESHOLD = 0.80    # Topics above this similarity → already covered
MIN_ARTICLES_PER_TOPIC = 2           # Need at least N sources to cover a topic

# ─── Script Config ───────────────────────────────────────
TARGET_VIDEO_DURATION = 40         # Target seconds for the video
MAX_SCENES = 5                     # Max scenes per video
SCRIPT_STYLE = "punchy"            # Hook → facts → kicker style

# ─── History / Follow-up Config ──────────────────────────
ENABLE_FOLLOWUPS = True            # Generate follow-up videos on developing stories
FOLLOWUP_SIMILARITY_THRESHOLD = 0.75  # Topic must be this similar to trigger follow-up
FOLLOWUP_MIN_AGE_HOURS = 12        # Must be at least this old to follow up
FOLLOWUP_MAX_AGE_HOURS = 720       # Don't follow up on stories older than this
MAX_FOLLOWUPS_PER_CYCLE = 2       # Max follow-up videos per cycle

# ─── Video Config ────────────────────────────────────────
# ─── Video Config ────────────────────────────────────────
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
ZOOM_FACTOR = 1.15                 # Ken Burns: zoom from 1.0 to this
CROSSFADE_DURATION = 0.0           # 0.0 for hard cuts (fast pacing)

# SFX Config
SFX_DIR = BASE_DIR / "video_creation" / "media" / "sfx"

# Caption style
CAPTION_FONT_SIZE = 60
CAPTION_COLOR = "white"
CAPTION_HIGHLIGHT_COLOR = "yellow"
CAPTION_STROKE_COLOR = "black"
CAPTION_STROKE_WIDTH = 3
CAPTION_POSITION = ("center", 0.80)  # 80% down the screen

# ─── Scheduler Config ───────────────────────────────────
CYCLE_INTERVAL_HOURS = 3           # Run pipeline every N hours
MAX_VIDEOS_PER_CYCLE = 5           # Cap videos per cycle to save credits

# ─── Image Prompt Guidelines ────────────────────────────
# These are appended to every image generation prompt for consistency
IMAGE_STYLE_SUFFIX = (
    "Photorealistic, cinematic lighting, dramatic composition, "
    "ultra-detailed, 4K quality, professional news photography style, "
    "moody color grading, shallow depth of field, editorial quality, "
    "grounded generation, accurate spatial relationships"
)
IMAGE_NEGATIVE_PROMPT = (
    "cartoon, anime, illustration, drawing, sketch, painting, "
    "watermark, text overlay, blurry, low quality, distorted faces, "
    "extra limbs, deformed, ugly, duplicate"
)
