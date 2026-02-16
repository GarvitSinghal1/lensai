"""
Pipeline Orchestrator v2 — the main pipeline that ties everything together.
Now includes follow-up video support for developing stories.
Scrape -> Cluster -> Analyze -> Generate -> Assemble (+ Follow-ups)
"""

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from utils.logger import log
from utils.dedup import DedupDB
from utils.history import TopicHistory
from scraper.feed_scraper import scrape_all_feeds
from scraper.article_extractor import extract_articles_batch
from clustering.topic_clusterer import cluster_articles, filter_single_source_topics
from analysis.cross_reference import cross_reference_articles
from analysis.script_generator import generate_script
from media.tts_engine import generate_tts_for_scenes
from media.image_generator import generate_images_for_scenes
from video.composer import compose_video


def _slugify(text: str) -> str:
    """Create a URL-safe slug from text."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '_', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:60]


def run_cycle() -> dict:
    """
    Run one complete pipeline cycle.
    
    Returns a dict with cycle statistics.
    """
    cycle_start = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    stats = {
        "articles_scraped": 0,
        "topics_found": 0,
        "topics_new": 0,
        "videos_generated": 0,
        "followups_generated": 0,
        "video_paths": [],
        "errors": [],
    }
    
    dedup = DedupDB()
    history = TopicHistory()
    
    log.info("=" * 60)
    log.info(f"🔄 CYCLE START: {timestamp}")
    log.info("=" * 60)
    
    # ── Step 1: Scrape all RSS feeds ────────────────────────
    log.info("\n📰 STEP 1: Scraping RSS feeds...")
    try:
        articles = scrape_all_feeds()
        stats["articles_scraped"] = len(articles)
    except Exception as e:
        log.error(f"Scraping failed: {e}")
        stats["errors"].append(f"Scraping failed: {e}")
        return stats
    
    if not articles:
        log.warning("No articles found. Ending cycle.")
        return stats
    
    # ── Step 2: Cluster articles by topic ───────────────────
    log.info(f"\n🔗 STEP 2: Clustering {len(articles)} articles by topic...")
    try:
        clusters = cluster_articles(articles)
        clusters = filter_single_source_topics(clusters)
        stats["topics_found"] = len(clusters)
    except Exception as e:
        log.error(f"Clustering failed: {e}")
        stats["errors"].append(f"Clustering failed: {e}")
        return stats
    
    if not clusters:
        log.warning("No multi-source topics found. Ending cycle.")
        return stats
    
    log.info(f"Found {len(clusters)} multi-source topics")
    
    # Generate interactive visualization
    try:
        from clustering import visualizer
        viz_path = config.OUTPUT_DIR / "clusters.html"
        visualizer.save_interactive_visualization(clusters, viz_path)
    except Exception as e:
        log.warning(f"Visualization failed: {e}")

    for i, cluster in enumerate(clusters[:10]):
        log.info(f"  [{i+1}] {cluster['representative_title'][:80]} "
                 f"({cluster['article_count']} articles from {cluster['source_names'][:50]})")
    
    # ── Step 3: Filter already-covered topics ───────────────
    log.info("\n🔍 STEP 3: Checking for already-covered topics...")
    new_topics = []
    for cluster in clusters:
        if not dedup.is_topic_covered(cluster["centroid"]):
            new_topics.append(cluster)
        else:
            log.info(f"  ⏭️  Already covered: {cluster['representative_title'][:60]}")
    
    stats["topics_new"] = len(new_topics)
    
    # ── Step 3b: Check for follow-up candidates ─────────────
    followup_candidates = []
    if config.ENABLE_FOLLOWUPS:
        log.info("\n🔄 STEP 3b: Checking for follow-up story opportunities...")
        followup_candidates = history.find_followup_candidates(clusters)
    
    if not new_topics and not followup_candidates:
        log.info("No new topics or follow-ups to process.")
        return stats
    
    log.info(f"📌 {len(new_topics)} new topics + {len(followup_candidates)} follow-ups")
    
    # ── Step 4: Process new topics ──────────────────────────
    topics_to_process = new_topics[:config.MAX_VIDEOS_PER_CYCLE]
    
    for topic_idx, cluster in enumerate(topics_to_process):
        topic_title = cluster["representative_title"]
        log.info(f"\n{'─' * 50}")
        log.info(f"📹 NEW TOPIC {topic_idx + 1}/{len(topics_to_process)}: {topic_title[:70]}")
        log.info(f"{'─' * 50}")
        
        topic_slug = _slugify(topic_title)
        temp_dir = config.TEMP_DIR / f"{timestamp}_{topic_slug}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            video_path = _process_single_topic(
                cluster, temp_dir, timestamp, topic_slug
            )
            
            if video_path:
                stats["videos_generated"] += 1
                stats["video_paths"].append(video_path)
                
                # Mark topic as covered in dedup DB
                dedup.mark_topic_covered(
                    centroid_embedding=cluster["centroid"],
                    representative_title=topic_title,
                    article_count=cluster["article_count"],
                    source_names=cluster["source_names"],
                    video_path=video_path,
                )
                
                # Save to history for future follow-ups
                if hasattr(_process_single_topic, '_last_analysis'):
                    history.save_topic(
                        topic_title=topic_title,
                        analysis=_process_single_topic._last_analysis,
                        centroid_embedding=cluster["centroid"],
                        article_count=cluster["article_count"],
                        source_names=cluster["source_names"],
                    )
                
                log.info(f"✅ Video complete: {video_path}")
            else:
                stats["errors"].append(f"Failed: {topic_title[:50]}")
                log.error(f"❌ Failed: {topic_title[:50]}")
                
        except Exception as e:
            log.error(f"❌ Error: '{topic_title[:50]}': {e}")
            stats["errors"].append(f"Error: {topic_title[:50]}: {e}")
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    
    # ── Step 5: Process follow-up topics ────────────────────
    for fu_idx, candidate in enumerate(followup_candidates):
        hist = candidate["historical_topic"]
        cluster = candidate["new_cluster"]
        topic_title = cluster["representative_title"]
        
        log.info(f"\n{'─' * 50}")
        log.info(f"🔄 FOLLOW-UP {fu_idx + 1}/{len(followup_candidates)}: {topic_title[:70]}")
        log.info(f"   (Update on: '{hist['title'][:60]}')")
        log.info(f"{'─' * 50}")
        
        topic_slug = _slugify(f"followup_{topic_title}")
        temp_dir = config.TEMP_DIR / f"{timestamp}_{topic_slug}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Get full historical context
            historical_context = history.get_topic_context(hist["id"])
            
            video_path = _process_single_topic(
                cluster, temp_dir, timestamp, topic_slug,
                historical_context=historical_context
            )
            
            if video_path:
                stats["followups_generated"] += 1
                stats["video_paths"].append(video_path)
                history.record_followup(
                    hist["id"], video_path,
                    new_developments=f"New articles found about: {topic_title[:100]}"
                )
                log.info(f"✅ Follow-up video complete: {video_path}")
            else:
                log.warning(f"❌ Follow-up failed for: {topic_title[:50]}")
                
        except Exception as e:
            log.error(f"❌ Follow-up error: '{topic_title[:50]}': {e}")
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    
    # ── Summary ─────────────────────────────────────────────
    elapsed = time.time() - cycle_start
    
    log.info(f"\n{'=' * 60}")
    log.info(f"🏁 CYCLE COMPLETE in {elapsed:.1f}s")
    log.info(f"   Articles scraped:     {stats['articles_scraped']}")
    log.info(f"   Topics found:         {stats['topics_found']}")
    log.info(f"   New topics:           {stats['topics_new']}")
    log.info(f"   Videos generated:     {stats['videos_generated']}")
    log.info(f"   Follow-ups generated: {stats['followups_generated']}")
    if stats["errors"]:
        log.info(f"   Errors:               {len(stats['errors'])}")
    log.info(f"{'=' * 60}\n")
    
    # Print dedup stats
    db_stats = dedup.get_stats()
    log.info(f"📊 DB Stats: {db_stats['topics_covered']} topics covered, "
             f"{db_stats['urls_processed']} URLs processed")
    
    return stats


def _process_single_topic(cluster: dict, temp_dir: Path,
                           timestamp: str, topic_slug: str,
                           historical_context: dict = None) -> Optional[str]:
    """
    Process a single topic through the full pipeline:
    extract -> analyze -> script -> TTS -> images -> video
    
    If historical_context is provided, generates a follow-up video.
    """
    is_followup = historical_context is not None
    prefix = "FOLLOW-UP" if is_followup else "NEW"
    
    # Step 4: Extract full article text
    log.info(f"  📄 [{prefix}] Extracting full article text...")
    enriched_articles = extract_articles_batch(cluster["articles"])
    
    if not enriched_articles:
        log.warning("  Could not extract full text, using summaries only")
        enriched_articles = cluster["articles"]
    
    # Step 5: Cross-reference analysis
    log.info(f"  🔬 [{prefix}] Cross-referencing sources...")
    analysis = cross_reference_articles(enriched_articles)
    
    if not analysis:
        log.error("  Cross-reference analysis failed")
        return None
    
    # Store analysis for history tracking (using function attribute hack)
    _process_single_topic._last_analysis = analysis
    
    log.info(f"  Topic: {analysis.get('topic_summary', 'Unknown')[:80]}")
    log.info(f"  Severity: {analysis.get('severity', '?')}")
    
    # Step 6: Generate script
    log.info(f"  ✍️  [{prefix}] Generating video script...")
    scenes = generate_script(analysis, historical_context=historical_context)
    
    if not scenes:
        log.error("  Script generation failed")
        return None
    
    log.info(f"  Script: {len(scenes)} scenes, "
             f"~{sum(s.get('estimated_duration', 5) for s in scenes):.0f}s")
    
    # Step 7: Generate TTS audio for each scene
    log.info(f"  🎙️  [{prefix}] Generating voiceover...")
    scenes = generate_tts_for_scenes(scenes, temp_dir)
    
    if not scenes:
        log.error("  TTS generation failed for all scenes")
        return None
    
    # Step 8: Generate images for each scene
    log.info(f"  🎨 [{prefix}] Generating visuals...")
    scenes = generate_images_for_scenes(scenes, temp_dir)
    
    # Filter scenes with both audio and image
    valid_scenes = [
        s for s in scenes
        if s.get("audio_path") and s.get("image_path")
    ]
    
    if not valid_scenes:
        log.error("  No valid scenes (missing audio or images)")
        return None
    
    # Step 9: Compose video
    prefix_tag = "followup" if is_followup else "lens_ai"
    output_path = config.OUTPUT_DIR / f"{prefix_tag}_{timestamp}_{topic_slug}.mp4"
    
    log.info(f"  🎬 [{prefix}] Composing video from {len(valid_scenes)} scenes...")
    video_path = compose_video(valid_scenes, str(output_path))
    
    return video_path
