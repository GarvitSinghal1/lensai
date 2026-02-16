"""
Lens AI — Central Configuration
AI News Video Factory that scrapes, fact-checks, and generates videos.
Loads environment variables and defines all constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ─── Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "news.db"
HISTORY_DIR = BASE_DIR / "history"  # Stores past topic analyses for follow-ups

# Create directories
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

# ─── API Keys ────────────────────────────────────────────
HF_API_KEY = os.getenv("hff_key", "")

# ─── HF Model Config ────────────────────────────────────
# Text generation (for analysis & script writing)
# Kimi K2.5 — native multimodal agentic model by Moonshot AI
LLM_MODEL = "moonshotai/Kimi-K2.5"
LLM_FALLBACK = "mistralai/Mistral-7B-Instruct-v0.3"
LLM_FALLBACK_2 = "HuggingFaceH4/zephyr-7b-beta"

# TTS (text-to-speech)
TTS_MODEL = "hexgrad/Kokoro-82M"
TTS_FALLBACK = "facebook/mms-tts-eng"

# Image generation
IMAGE_MODEL = "black-forest-labs/FLUX.1-dev"
IMAGE_FALLBACK = "stabilityai/stable-diffusion-xl-base-1.0"
IMAGE_FALLBACK_2 = "black-forest-labs/FLUX.1-schnell"

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
FOLLOWUP_MIN_AGE_HOURS = 6        # Must be at least this old to follow up
FOLLOWUP_MAX_AGE_HOURS = 72       # Don't follow up on stories older than this
MAX_FOLLOWUPS_PER_CYCLE = 2       # Max follow-up videos per cycle

# ─── Video Config ────────────────────────────────────────
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
ZOOM_FACTOR = 1.15                 # Ken Burns: zoom from 1.0 to this
CROSSFADE_DURATION = 0.3           # Seconds of crossfade between scenes

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

# ─── HF API Config ──────────────────────────────────────
HF_API_BASE = "https://api-inference.huggingface.co/models"
HF_API_TIMEOUT = 180               # Seconds to wait for HF model response (K2.5 needs more)
HF_MAX_RETRIES = 3                 # Retry failed API calls

# ─── Image Prompt Guidelines ────────────────────────────
# These are appended to every image generation prompt for consistency
IMAGE_STYLE_SUFFIX = (
    "Photorealistic, cinematic lighting, dramatic composition, "
    "ultra-detailed, 4K quality, professional news photography style, "
    "moody color grading, shallow depth of field, editorial quality"
)
IMAGE_NEGATIVE_PROMPT = (
    "cartoon, anime, illustration, drawing, sketch, painting, "
    "watermark, text overlay, blurry, low quality, distorted faces, "
    "extra limbs, deformed, ugly, duplicate"
)
