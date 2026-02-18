"""
Pipeline Orchestrator v2 — the main pipeline that ties everything together.
Now includes follow-up video support for developing stories.
Scrape -> Cluster -> Analyze -> Generate -> Assemble (+ Follow-ups)
"""

import shutil
import time
import requests
from PIL import Image
from io import BytesIO
from video_creation.media import tts_engine
from pathlib import Path
from typing import Optional
from datetime import datetime

import config
from utils.logger import log
from utils.dedup import DedupDB
from utils.history import TopicHistory
from collection.scraper.feed_scraper import scrape_all_feeds
from collection.scraper.article_extractor import extract_articles_batch
from analysis_layer.clustering.topic_clusterer import cluster_articles, filter_single_source_topics
from analysis_layer.analysis.cross_reference import cross_reference_articles
from analysis_layer.analysis.script_generator import generate_script
from video_creation.media.tts_engine import generate_tts_for_scenes
from video_creation.media.image_generator import generate_images_for_scenes
from video_creation.video.composer import compose_video


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
        from analysis_layer.clustering import visualizer
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
    
    # Collect available images from articles
    article_images = [
        a["top_image"] for a in enriched_articles 
        if a.get("top_image") and a["top_image"].startswith("http")
    ]
    # Deduplicate preserving order
    seen_imgs = set()
    unique_images = []
    for img in article_images:
        if img not in seen_imgs:
            unique_images.append(img)
            seen_imgs.add(img)
    article_images = unique_images

    # Step 8: Generate images (or Anchor Video) for each scene
    log.info(f"  🎨 [{prefix}] Generating visuals...")
    
    # Generate images for English scenes first
    # Implementation detail: We iterate and check for 'is_anchor'
    
    from video_creation.media import image_generator
    from video_creation.media import lip_sync
    import config
    from utils.stock_footage import search_stock_video
    
    anchor_image_path = config.MEDIA_DIR / "anchor.png"
    
    for i, scene in enumerate(scenes):
        scene_idx = i + 1
        
        # 1. Check for Anchor Mode
        if scene.get("is_anchor"):
            if anchor_image_path.exists():
                log.info(f"    Scene {scene_idx}: Anchor mode active.")
                # Try Lip Sync if audio exists
                if scene.get("audio_path"):
                    video_path = lip_sync.generate_lip_sync(
                        Path(scene["audio_path"]), 
                        anchor_image_path, 
                        temp_dir / f"scene_{scene_idx}_anchor.mp4"
                    )
                    if video_path:
                        scene["video_path"] = video_path
                        scene["image_path"] = None 
                        continue
                
                # Fallback to static image if lip sync fails or no audio
                log.info(f"    Scene {scene_idx}: Using static Anchor image (Lip Sync unavailable/failed).")
                scene["image_path"] = str(anchor_image_path)
                continue
            else:
                log.warning(f"    Scene {scene_idx}: Anchor requested but 'anchor.png' missing! logic continues to other media.")

        # 2. Scraped Image Strategy (for non-anchor scenes)
        # [Existing logic for scraped images...]
        if article_images:
            # Try to get a valid image from the scraped list
            # We explicitly want to use real news images first
            try:
                img_url = article_images.pop(0)
                log.info(f"    Scene {scene_idx}: attempting to use news image: {img_url}")
                
                response = requests.get(img_url, timeout=5)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    
                    # Convert to RGB (remove alpha/palettes)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                        
                    # Crop to 9:16 aspect ratio (1080x1920 target, or just ratio)
                    # Target aspect ratio
                    target_ratio = 9/16
                    img_ratio = img.width / img.height
                    
                    if img_ratio > target_ratio:
                        # Image is too wide, need to crop width
                        new_width = int(img.height * target_ratio)
                        offset = (img.width - new_width) // 2
                        img = img.crop((offset, 0, offset + new_width, img.height))
                    else:
                        # Image is too tall (unlikely for news), crop height
                        new_height = int(img.width / target_ratio)
                        offset = (img.height - new_height) // 2
                        img = img.crop((0, offset, img.width, offset + new_height))
                        
                    # Resize to target resolution for consistency (optional but good)
                    img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
                    
                    # Save
                    dest_path = temp_dir / f"scene_{scene_idx}_news.png"
                    img.save(dest_path)
                    
                    scene["image_path"] = str(dest_path)
                    log.info(f"    ✅ Used real news image for Scene {scene_idx}")
                    continue
                else:
                    log.warning(f"    Failed to download news image (Status {response.status_code})")
            except Exception as e:
                log.warning(f"    Error processing news image: {e}")
            
            # Remove the 'pass' that caused indentation error
            # If no image found/processed, we fall through to next strategy

        # 3. Stock Video Strategy (B-Roll)
        if scene.get("media_type") in ["stock_video", "video"]:
            search_term = scene.get("stock_search_term") or scene.get("image_prompt") or scene.get("visual_description", "")
            log.info(f"    Scene {scene_idx}: Searching stock video for '{search_term}'...")
            
            # Try to get a video
            stock_path = search_stock_video(
                query=search_term,
                orientation="portrait", # Vertical video
                duration_min=3
            )
            
            if stock_path:
                scene["video_path"] = str(stock_path)
                scene["image_path"] = None # Video takes precedence
                log.info(f"    ✅ Stock video found: {stock_path.name}")
                continue
            else:
                log.info(f"    ⚠️ Stock video not found for '{search_term}', falling back to AI Image.")
                # Fallback to AI image generation below
        
        # 4. AI Generation Strategy (Fallback or Primary)
        # Prefer 'image_prompt' (new schema), fallback to 'visual_description' (old schema)
        prompt = scene.get("image_prompt") or scene.get("visual_description", "")
        
        # Ensure pure description for image gen if prompt is missing
        if not prompt:
            log.warning(f"    Scene {scene_idx}: Empty prompt!")
        
        img_path = temp_dir / f"scene_{scene_idx}.png"
        
        generated = image_generator.generate_image(prompt, img_path)
        if generated:
            scene["image_path"] = generated
        else:
            log.warning(f"    Scene {scene_idx}: Image gen failed.")

    scenes_en = scenes # Renamed for clarity logic below
    
    # Filter scenes with both audio and (image OR video)
    valid_scenes_en = [
        s for s in scenes_en
        if s.get("audio_path") and (s.get("image_path") or s.get("video_path"))
    ]
    
    video_path_en = None
    if valid_scenes_en:
        # Step 9a: Compose English Video
        prefix_tag = "followup" if is_followup else "lens_ai"
        output_path_en = config.OUTPUT_DIR / f"{prefix_tag}_{timestamp}_{topic_slug}_EN.mp4"
        
        log.info(f"  🎬 [{prefix}] Composing ENGLISH video...")
        video_path_en = compose_video(valid_scenes_en, str(output_path_en))
    else:
        log.error("  No valid English scenes (missing audio or images)")

    # ── Step 10: Multilingual Generation (Hindi) ───────────
    video_path_hi = None
    try:
        from analysis_layer.analysis.script_generator import translate_script
        
        log.info(f"  🌐 [{prefix}] Starting Hindi generation...")
        
        # 1. Translate Script
        # Use the original 'scenes' (before TTS/Image generation modified them? No, use valid_scenes_en to keep image paths!)
        # valid_scenes_en has 'image_path'. We want to REUSE that.
        if valid_scenes_en:
            scenes_hi = translate_script(valid_scenes_en, target_lang="hi")
            
            if scenes_hi:
                # 2. Generate Hindi TTS
                log.info(f"  🎙️  [{prefix}] Generating Hindi voiceover...")
                # Update scenes with new audio paths, keeping image paths
                scenes_hi = generate_tts_for_scenes(scenes_hi, temp_dir, lang="hi")
                
                # 3. specific lang tag for composer
                for s in scenes_hi:
                    s["lang"] = "hi"
                
                # 4. Compose Hindi Video
                output_path_hi = config.OUTPUT_DIR / f"{prefix_tag}_{timestamp}_{topic_slug}_HI.mp4"
                log.info(f"  🎬 [{prefix}] Composing HINDI video...")
                video_path_hi = compose_video(scenes_hi, str(output_path_hi))
                if video_path_hi:
                    log.info(f"✅ HINDI Video complete: {video_path_hi}")
            else:
                 log.warning("  Hindi translation failed.")
    except Exception as e:
        log.error(f"  Hindi generation failed: {e}")

    # Return primary video path (English) for stats/history, or Hindi if EN failed?
    # Stats expects one path usually, but we can return list?
    # run_cycle expects a single string or potentially list. 
    # Let's return English path as primary.
    return video_path_en
