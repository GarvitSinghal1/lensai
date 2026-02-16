<p align="center">
  <h1 align="center">🔮 Lens AI</h1>
  <p align="center"><strong>Autonomous AI News Video Factory</strong></p>
  <p align="center">
    Scrapes 22 global news sources → Clusters by topic → Cross-references for truth vs exaggeration → Generates cinematic 9:16 short-form videos with AI voiceover & visuals — fully autonomously, every 3 hours.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/LLM-Kimi_K2.5-purple?style=flat-square" alt="Kimi K2.5">
  <img src="https://img.shields.io/badge/Images-FLUX.2--dev_(ELO_1209)-orange?style=flat-square" alt="FLUX.2">
  <img src="https://img.shields.io/badge/TTS-Kokoro--82M-green?style=flat-square" alt="Kokoro TTS">
  <img src="https://img.shields.io/badge/Video-MoviePy_v2-red?style=flat-square" alt="MoviePy">
  <img src="https://img.shields.io/badge/Cost-Free_(HF_API)-brightgreen?style=flat-square" alt="Free">
</p>

---

## 🎯 What It Does

Lens AI is a **zero-human-intervention** pipeline that automatically:

1. **Scrapes** 22 RSS feeds from BBC, Reuters, CNN, Al Jazeera, Times of India, The Guardian, and more
2. **Clusters** articles about the same story using local sentence embeddings
3. **Cross-references** multiple sources with a Kimi K2.5–powered investigative AI — identifying consensus facts, disputed claims, and exaggerations
4. **Writes scripts** in punchy 30–45 second short-form format (hook → context → facts → twist → kicker)
5. **Generates voiceover** using Kokoro-82M TTS with word-level timestamps
6. **Creates cinematic visuals** for each scene via FLUX.2-dev — #3 on HF image leaderboard (ELO 1209)
7. **Assembles final videos** with Ken Burns zoom, word-by-word captions, and crossfade transitions
8. **Detects developing stories** and auto-generates follow-up videos with historical context

All of this runs on the **free** Hugging Face Inference API.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LENS AI PIPELINE                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   📰 RSS Feeds (22 sources)                                │
│      ↓                                                      │
│   🔗 Topic Clustering (sentence-transformers, local)        │
│      ↓                                                      │
│   🔍 Deduplication Check (SQLite)                           │
│      ↓                                                      │
│   📄 Full Article Extraction (BeautifulSoup)                │
│      ↓                                                      │
│   🔬 Cross-Reference Analysis (Kimi K2.5 → Mistral → Zephyr)│
│      ↓                                                      │
│   ✍️  Script Generation (Kimi K2.5, fresh or follow-up)     │
│      ↓                                                      │
│   🎙️  TTS Voiceover (Kokoro-82M → MMS-TTS)                 │
│      ↓                                                      │
│   🎨 Image Generation (FLUX.2-dev → FLUX.1-dev → SDXL)     │
│      ↓                                                      │
│   🎬 Video Assembly (MoviePy v2, 1080×1920, 30fps)          │
│      ↓                                                      │
│   📁 output/ (ready for upload)                             │
│                                                             │
│   🔄 Follow-up System: tracks covered topics in history DB, │
│      detects developing stories, generates update videos    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
lensai/
├── main.py                    # Entry point + 3-hour scheduler
├── run.sh                     # Shell wrapper (sets PYTHONPATH)
├── config.py                  # All configuration in one place
├── requirements.txt           # Python dependencies
│
├── scraper/                   # News ingestion
│   ├── rss_feeds.py           #   22 feeds: BBC, Reuters, CNN, Al Jazeera, etc.
│   ├── feed_scraper.py        #   Parallel RSS fetcher
│   └── article_extractor.py   #   Full text extraction (BeautifulSoup)
│
├── clustering/                # Topic detection
│   └── topic_clusterer.py     #   Agglomerative clustering + embeddings
│
├── analysis/                  # AI brain
│   ├── cross_reference.py     #   Multi-source fact analysis (Kimi K2.5)
│   └── script_generator.py    #   Video script writer (fresh + follow-up)
│
├── media/                     # Asset generation
│   ├── tts_engine.py          #   Voiceover (Kokoro-82M)
│   └── image_generator.py     #   Scene visuals (FLUX.1-dev)
│
├── video/                     # Final assembly
│   └── composer.py            #   Ken Burns + captions + transitions
│
├── pipeline/                  # Orchestration
│   └── orchestrator.py        #   End-to-end pipeline runner
│
├── utils/                     # Shared utilities
│   ├── logger.py              #   Console + file logging
│   ├── dedup.py               #   SQLite deduplication
│   ├── history.py             #   Topic history for follow-ups
│   └── hf_client.py           #   Centralized LLM caller (3-model fallback)
│
├── output/                    # Generated videos land here
├── db/                        # SQLite databases
├── history/                   # Past topic analyses (JSON)
└── lib/                       # pip --target dependencies
```

---

## ⚡ Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/GarvitSinghal1/lensai.git
cd lensai
```

Create a `.env` file with your Hugging Face API key:

```env
hff_key=hf_your_api_key_here
```

> 💡 Get a free API key at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

### 2. Install Dependencies

```bash
pip install --no-compile --target lib -r requirements.txt
```

### 3. Run

```bash
# Single cycle (scrape → analyze → generate → done)
./run.sh --once

# Continuous mode (auto-runs every 3 hours)
./run.sh
```

---

## 🧠 AI Models Used

| Component | Primary Model | Fallback 1 | Fallback 2 |
|-----------|--------------|-------------|------------|
| **Analysis & Scripts** | Kimi K2.5 (`moonshotai/Kimi-K2.5`) | Mistral 7B Instruct | Zephyr 7B Beta |
| **Image Generation** | FLUX.2-dev · *ELO 1209* | FLUX.1-dev | SDXL Base 1.0 |
| **Text-to-Speech** | Kokoro 82M · *7.4M downloads* | MiniMax Speech-02-Turbo · *ELO 1107* | MMS-TTS English |
| **Embeddings** | all-MiniLM-L6-v2 (local) | — | — |

Every API call has a **3-model fallback chain** — if the primary model is loading or rate-limited, it silently tries the next one.

---

## 📰 News Sources (22 Feeds)

| Region | Sources |
|--------|---------|
| 🌍 Global | Reuters, AP News |
| 🇬🇧 UK | BBC (World, Top, Tech, Business), The Guardian |
| 🇺🇸 US | CNN, NPR, CBS News |
| 🇮🇳 India | Times of India, NDTV, The Hindu, Hindustan Times |
| 🌏 Middle East | Al Jazeera |
| 🇪🇺 Europe | Deutsche Welle, France 24 |
| 🌏 Asia-Pacific | ABC Australia, NHK World, SCMP |
| 💻 Tech | Ars Technica, TechCrunch |

---

## 🔄 Follow-Up System

Lens AI doesn't just cover news — it **tracks developing stories**:

- After covering a topic, the analysis is saved to a SQLite history database with vector embeddings
- On each cycle, new article clusters are compared against past topics using cosine similarity
- If a developing story is detected (similarity > 0.75, aged 6–72 hours), a **follow-up video** is auto-generated
- Follow-up scripts reference previous coverage: *"Remember X? Here's what just happened..."*
- Up to 2 follow-ups per cycle alongside 5 new topic videos

---

## 🎬 Video Output Specs

| Property | Value |
|----------|-------|
| Resolution | 1080 × 1920 (9:16 vertical) |
| FPS | 30 |
| Duration | 30–45 seconds |
| Scenes | 4–5 per video |
| Format | MP4 (H.264 + AAC) |
| Captions | Word-by-word highlight with stroke outline |
| Transitions | 0.3s crossfade between scenes |
| Image Effect | Ken Burns zoom (1.0x → 1.15x) with horizontal drift |

---

## ⚙️ Configuration

All settings live in `config.py`. Key tunables:

```python
# Scraping
MAX_ARTICLE_AGE_HOURS = 6       # Only recent articles
MAX_WORKERS = 8                 # Parallel feed fetchers

# Clustering
CLUSTER_SIMILARITY_THRESHOLD = 0.65   # Group similar articles
MIN_ARTICLES_PER_TOPIC = 2            # Need 2+ sources

# Video
TARGET_VIDEO_DURATION = 40      # Seconds
MAX_SCENES = 5                  # Per video
MAX_VIDEOS_PER_CYCLE = 5        # Credit budget

# Scheduler
CYCLE_INTERVAL_HOURS = 3        # Auto-run frequency

# Follow-ups
ENABLE_FOLLOWUPS = True
FOLLOWUP_SIMILARITY_THRESHOLD = 0.75
```

---

## 🛡️ Truth Engine

The cross-reference analysis isn't a summarizer — it's an **investigative fact-checker**:

- ✅ **Consensus facts** — only claims confirmed by 2+ independent sources
- ⚠️ **Disputed claims** — flagged with source attribution and reason for dispute
- 🚩 **Exaggeration detection** — compares sensationalized language against actual evidence
- 📊 **Severity classification** — low (lifestyle) / medium (politics) / high (crisis)
- 👥 **Key data extraction** — structured who/what/where/when/impact

The system prompt instructs the AI to act as an "elite investigative journalist" — no vague generalizations, only specific numbers, names, and dates.

---

## 🔧 Technical Details

### Dependency Management
Dependencies are installed via `pip install --target lib/` to avoid Google Drive filesystem `.pyc` permission conflicts. The `run.sh` wrapper auto-sets `PYTHONPATH=lib`.

### Error Resilience
- Every HF API call retries up to 3× with exponential backoff
- Model-loading 503s trigger wait-and-retry (respects `estimated_time`)
- Rate limit (429) responses trigger 10s cooldown
- Per-topic error isolation — one failed topic doesn't kill the cycle
- Fallback gradient images when all image models fail
- Logger falls back to `/tmp` if project directory isn't writable

### Local vs API
- **Local** (no API cost): sentence embeddings (all-MiniLM-L6-v2), deduplication, clustering
- **API** (free HF tier): LLM analysis, script generation, TTS, image generation

---

## 📄 License

MIT

---

<p align="center">
  Built with caffeine and APIs that are somehow free<br>
  <strong>Lens AI</strong> — because the news should explain itself
</p>
