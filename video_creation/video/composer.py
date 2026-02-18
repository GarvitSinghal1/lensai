"""
Video Composer v2 — assembles final 9:16 short-form videos using MoviePy v2.
Features: Ken Burns effect, word-by-word captions, crossfade transitions.
Compatible with MoviePy >= 2.0
"""

import os
import math
from pathlib import Path
import random
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config
from utils.logger import log

# MoviePy v2 imports
from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, TextClip, ColorClip, VideoClip, vfx,
    VideoFileClip
)


# ─── Font Discovery ──────────────────────────────────────

def _find_system_font() -> str:
    """Find a suitable system font for captions."""
    font_paths = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFCompact.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]

    for path in font_paths:
        if os.path.exists(path):
            return path

    return "Helvetica"


def _find_font_for_lang(lang: str = "en") -> str:
    """Find a suitable system font for a specific language."""
    if lang == "hi":
        hindi_fonts = [
            # macOS
            "/System/Library/Fonts/KohinoorDevanagari.ttc",
            "/System/Library/Fonts/Supplemental/DevanagariMT.ttc",
            "/System/Library/Fonts/Supplemental/Nirmala.ttc",
            # Linux
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf", # often has wide coverage
        ]
        for path in hindi_fonts:
            if os.path.exists(path):
                return path
        # Fallback to system font if no specific Hindi font found (might fail to render)
        return _find_system_font()

    return _find_system_font()

SYSTEM_FONT = _find_system_font() # Default


# ─── Ken Burns Effect ────────────────────────────────────

def apply_ken_burns(image_path: str, duration: float, zoom_start: float = 1.0,
                     zoom_end: float = None, visual_effect: str = "none") -> VideoClip:
    """
    Create a video clip from a still image with Ken Burns zoom or other effects.
    """
    zoom_end = zoom_end or config.ZOOM_FACTOR
    
    # Handle specific visual effects overrides
    if visual_effect == "zoom_fast":
        zoom_end = 1.5  # More aggressive zoom
    elif visual_effect == "zoom_slow":
        zoom_end = 1.05 # Subtle zoom

    # Load image at higher resolution for zoom headroom
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Ensure image is large enough for zooming
    target_w = int(config.VIDEO_WIDTH * max(zoom_end, 1.2)) # Extra buffer for shake
    target_h = int(config.VIDEO_HEIGHT * max(zoom_end, 1.2))

    if img.width < target_w or img.height < target_h:
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    img_array = np.array(img)
    h, w = img_array.shape[:2]

    def make_frame(t):
        """Generate a frame at time t with zoom/shake applied."""
        progress = t / max(duration, 0.01)
        progress = min(progress, 1.0)
        
        # dynamic zoom
        current_zoom = zoom_start + (zoom_end - zoom_start) * progress
        
        # Calculate crop region (zoom into center)
        crop_w = int(config.VIDEO_WIDTH / current_zoom)
        crop_h = int(config.VIDEO_HEIGHT / current_zoom)
        
        # Center crop
        cx = w // 2
        cy = h // 2
        
        # Apply standard drift
        drift_x = int(20 * math.sin(progress * math.pi))
        
        # Apply SHAKE effect
        if visual_effect == "shake":
            intensity = 40 * (1 - progress) # Shake fades out
            drift_x += int(random.uniform(-intensity, intensity))
            cy += int(random.uniform(-intensity, intensity))
            
        cx += drift_x

        x1 = max(0, cx - crop_w // 2)
        y1 = max(0, cy - crop_h // 2)
        x2 = min(w, x1 + crop_w)
        y2 = min(h, y1 + crop_h)

        # Clamp bounds
        if x2 - x1 < 2:
            x1, x2 = 0, min(crop_w, w)
        if y2 - y1 < 2:
            y1, y2 = 0, min(crop_h, h)

        # Crop and resize to target
        cropped = img_array[y1:y2, x1:x2]

        # Resize using PIL for quality
        pil_img = Image.fromarray(cropped)
        pil_img = pil_img.resize(
            (config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
            Image.Resampling.LANCZOS
        )

        return np.array(pil_img)

    # Create VideoClip with custom frame function
    clip = VideoClip(make_frame, duration=duration)
    clip = clip.with_fps(config.VIDEO_FPS)
    
    # Apply FLASH effect (overlay)
    if visual_effect == "flash":
        flash = ColorClip(size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT), color=(255, 255, 255))
        flash = flash.with_duration(0.2).with_opacity(0.8)
        # Composite flash over clip (this returns a CompositeVideoClip, so we wrap appropriately)
        # But apply_ken_burns usually returns raw VideoClip. 
        # Simpler: just return the clip, and let compose_scene handle overlay if possible?
        # Or just execute it here.
        # Let's keep it simple: we want to return a VideoClip. 
        # A CompositeVideoClip IS a VideoClip.
        clip = CompositeVideoClip([clip, flash.with_start(0)])

    return clip


# ─── Caption Generation (PIL-based for reliability) ──────

def _render_caption_frame(text: str, highlight_word_idx: int,
                           words: list, video_size: tuple, font_path: str = None) -> np.ndarray:
    """Render a caption frame using PIL (more reliable than TextClip)."""
    w, h = video_size
    # Create transparent-ish overlay
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        # Use provided font path or default
        f_path = font_path or SYSTEM_FONT
        
        # Adjust font size for Hindi? (Devanagari often looks smaller)
        # Check if Hindi font
        is_hindi = "Devanagari" in f_path or "Nirmala" in f_path
        size = config.CAPTION_FONT_SIZE
        if is_hindi:
             size = int(size * 0.9) # Slightly smaller to avoid vertical clipping? Or larger?
             # Actually Devanagari has tall ascenders/descenders.
             
        font = ImageFont.truetype(f_path, size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Build text with current word highlighted
    y_pos = int(h * config.CAPTION_POSITION[1])

    # Draw each word
    total_text = " ".join(words)
    bbox = draw.textbbox((0, 0), total_text, font=font)
    text_width = bbox[2] - bbox[0]
    x_start = (w - text_width) // 2

    current_x = x_start
    for i, word in enumerate(words):
        word_bbox = draw.textbbox((0, 0), word, font=font)
        word_w = word_bbox[2] - word_bbox[0]

        # Stroke/outline
        for dx in range(-config.CAPTION_STROKE_WIDTH, config.CAPTION_STROKE_WIDTH + 1):
            for dy in range(-config.CAPTION_STROKE_WIDTH, config.CAPTION_STROKE_WIDTH + 1):
                if dx != 0 or dy != 0:
                    draw.text((current_x + dx, y_pos + dy), word,
                              fill=config.CAPTION_STROKE_COLOR, font=font)

        # Word color (highlight current word)
        color = config.CAPTION_HIGHLIGHT_COLOR if i == highlight_word_idx else config.CAPTION_COLOR
        draw.text((current_x, y_pos), word, fill=color, font=font)

        # Add space
        space_bbox = draw.textbbox((0, 0), " ", font=font)
        space_w = space_bbox[2] - space_bbox[0]
        current_x += word_w + space_w

    return np.array(img)


def create_caption_clips(narration: str, duration: float,
                          video_size: tuple = None, lang: str = "en") -> list:
    """
    Create word-by-word highlighted caption clips using PIL rendering.
    Shows groups of 4 words at a time with the current word highlighted.
    """
    if not narration.strip():
        return []

    video_size = video_size or (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
    
    # Resolve font for language
    font_path = _find_font_for_lang(lang)
    
    words = narration.split()

    if not words:
        return []

    time_per_word = duration / len(words)
    caption_clips = []
    words_per_group = 4

    for group_start in range(0, len(words), words_per_group):
        group_words = words[group_start:group_start + words_per_group]

        for word_offset in range(len(group_words)):
            abs_word_idx = group_start + word_offset
            word_start_time = abs_word_idx * time_per_word
            word_duration = time_per_word

            if word_start_time + word_duration > duration:
                word_duration = max(0.1, duration - word_start_time)

            try:
                # Render caption frame with PIL
                frame = _render_caption_frame(
                    " ".join(group_words), word_offset,
                    group_words, video_size, font_path=font_path
                )

                clip = ImageClip(frame)
                clip = (clip
                    .with_start(word_start_time)
                    .with_duration(word_duration)
                    .with_position(("center", "bottom")))

                caption_clips.append(clip)

            except Exception as e:
                log.debug(f"Caption creation error: {e}")
                continue

    return caption_clips


# ─── Visual Overlays ──────────────────────────────────────

def create_lower_third(headline: str, duration: float, lang: str = "en") -> Optional[VideoClip]:
    """Create a professional lower-third headline overlay."""
    if not headline:
        return None

    w, h = 600, 100
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Stylish background (Blue gradient-ish or solid with design)
    # Main box
    draw.rectangle([0, 0, w, h], fill="#0033cc") # Deep Blue
    # Accent strip
    draw.rectangle([0, 0, 20, h], fill="#cc0000") # Red strip on left

    # Text
    try:
        font_path = _find_font_for_lang(lang)
        font = ImageFont.truetype(font_path, 50)
    except:
        font = ImageFont.load_default()
    
    # Draw text centered vertically, left aligned with padding
    draw.text((40, h // 2), headline.upper(), font=font, fill="white", anchor="lm")

    # Create clip
    # Calculate position: Left=30, Bottom=180 (from bottom edge)
    # y = VIDEO_HEIGHT - h - 180
    y_pos = config.VIDEO_HEIGHT - h - 180
    
    clip = (
        ImageClip(np.array(img))
        .with_duration(duration)
        .with_position((30, y_pos))
        .with_effects([vfx.CrossFadeIn(0.5)])
    )
    return clip


def create_outro_clip() -> Optional[VideoClip]:
    """Create a branded 3s outro sequence."""
    duration = 2.5
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    
    # Black background opacity handled by composition? 
    # Better to create a ColorClip background
    bg = ColorClip(size=(w, h), color=(0, 0, 0)).with_duration(duration)
    
    # Logo
    logo_path = config.MEDIA_DIR / "logo.png" # Assuming high-res logo exists
    if not logo_path.exists():
        return None

    logo = (
        ImageClip(str(logo_path))
        .with_duration(duration)
        .resized(width=400)
        .with_position("center")
        .with_effects([vfx.CrossFadeIn(0.5)])
    )
    
    # Combine
    intro = CompositeVideoClip([bg, logo]).with_duration(duration)
    
    # Audio for outro (Whoosh + Boom)
    audio_clips = []
    try:
        if (config.SFX_DIR / "whoosh.wav").exists():
            whoosh = AudioFileClip(str(config.SFX_DIR / "whoosh.wav")).with_start(0.2)
            audio_clips.append(whoosh)
        if (config.SFX_DIR / "boom.wav").exists():
            boom = AudioFileClip(str(config.SFX_DIR / "boom.wav")).with_start(1.0)
            audio_clips.append(boom)
        
        if audio_clips:
            from moviepy import CompositeAudioClip
            intro = intro.with_audio(CompositeAudioClip(audio_clips))
    except Exception as e:
        log.warning(f"Outro audio failed: {e}")

    return intro


# ─── Scene Assembly ───────────────────────────────────────

def compose_scene(scene: dict) -> Optional[CompositeVideoClip]:
    """
    Compose a single scene: image with Ken Burns + audio + captions + lower third.
    """
    image_path = scene.get("image_path")
    audio_path = scene.get("audio_path")
    narration = scene.get("narration", "")
    headline = scene.get("headline", "")
    visual_effect = scene.get("visual_effect", "none")
    audio_effect = scene.get("audio_effect", "none")
    lang = scene.get("lang", "en") # Get language from scene
    
    duration = scene.get("actual_duration", scene.get("estimated_duration", 5.0))

    if not image_path or not os.path.exists(image_path):
        log.warning(f"Scene missing image: {image_path}")
        return None

    try:
        # Create Ken Burns clip from image with VFX
        video_clip = apply_ken_burns(image_path, duration, visual_effect=visual_effect)

        layers = [video_clip]

        # Add semi-transparent overlay at bottom for caption readability
        overlay_height = int(config.VIDEO_HEIGHT * 0.25)
        overlay = ColorClip(
            size=(config.VIDEO_WIDTH, overlay_height),
            color=(0, 0, 0)
        )
        overlay = (overlay
            .with_opacity(0.5)
            .with_duration(duration)
            .with_position(("center", config.VIDEO_HEIGHT - overlay_height)))
        layers.append(overlay)

        # Add Lower Third (if headline exists)
        if headline:
            lower_third = create_lower_third(headline, duration, lang=lang)
            if lower_third:
                layers.append(lower_third)

        # Add captions
        caption_clips = create_caption_clips(
            scene.get("text", ""), 
            duration, 
            (config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
            lang=lang
        )
        layers.extend(caption_clips)

        # Composite visual layers
        scene_clip = CompositeVideoClip(
            layers,
            size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
        ).with_duration(duration)

        # Handle Audio (Narration + SFX)
        audio_clips = []
        
        # 1. Narration
        if audio_path and os.path.exists(audio_path):
            try:
                narration_audio = AudioFileClip(audio_path)
                # Match audio duration to video
                if abs(narration_audio.duration - duration) > 0.5:
                    duration = narration_audio.duration
                    scene_clip = scene_clip.with_duration(duration)
                audio_clips.append(narration_audio)
            except Exception as e:
                log.warning(f"Failed to attach audio: {e}")
        
        # 2. Sound Effects
        if audio_effect and audio_effect != "none":
            sfx_path = config.SFX_DIR / f"{audio_effect}.wav"
            if sfx_path.exists():
                try:
                    sfx_audio = AudioFileClip(str(sfx_path))
                    # Lower volume for SFX so narration is clear
                    sfx_audio = sfx_audio.with_volume_scaled(0.10)
                    # SFX usually starts at 0, or maybe slight offset? Start at 0 for punchiness.
                    audio_clips.append(sfx_audio)
                except Exception as e:
                    log.warning(f"Failed to load SFX {sfx_path}: {e}")
            else:
                 log.debug(f"SFX not found: {sfx_path}")

        # Mix audio
        if audio_clips:
            from moviepy import CompositeAudioClip
            final_audio = CompositeAudioClip(audio_clips)
            scene_clip = scene_clip.with_audio(final_audio)

        return scene_clip

    except Exception as e:
        log.error(f"Failed to compose scene: {e}")
        return None


# ─── Full Video Assembly ─────────────────────────────────

def compose_video(scenes: list[dict], output_path: str) -> Optional[str]:
    """
    Compose a full video from all scenes.

    Args:
        scenes: list of scene dicts with image_path, audio_path, narration, actual_duration
        output_path: where to save the final MP4

    Returns:
        output path string on success, None on failure
    """
    if not scenes:
        log.error("No scenes to compose")
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"Composing video from {len(scenes)} scenes...")
    scene_clips = []



    # Create Outro Clip (Bonus Feature)
    try:
        outro_clip = create_outro_clip()
        if outro_clip:
            log.info("Adding brand outro sequence...")
            scene_clips.append(outro_clip)
    except Exception as e:
        log.warning(f"Outro creation failed: {e}")

    try:
        scene_clips = []
        for i, scene in enumerate(scenes):
            try:
                # 1. Check for pre-rendered Video (Anchor/Intro)
                video_path = scene.get("video_path")
                if video_path and os.path.exists(video_path):
                    log.info(f"Processing Anchor Video Scene {i+1}...")
                    
                    # Compute duration from audio or video
                    audio_path = scene.get("audio_path")
                    if audio_path and os.path.exists(audio_path):
                        audio = AudioFileClip(audio_path)
                        duration = audio.duration
                    else:
                        duration = VideoFileClip(video_path).duration
                        
                    # Load Video
                    clip = VideoFileClip(video_path).resized(new_size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))
                    
                    # Loop visual if audio is longer (common for short lip-sync clips)
                    if clip.duration < duration:
                         clip = vfx.loop(clip, duration=duration)
                    else:
                         clip = clip.with_duration(duration)
                         
                    # Attach specific audio if different from video's track
                    if audio_path:
                        clip = clip.with_audio(AudioFileClip(audio_path))
                        
                    # Add standard overlays (Ticker/Captions) if desired?
                    # For now, let's keep Anchor "clean" or assume it has them?
                    # Actually, Composer usually adds captions. Let's add captions.
                    caption_clips = create_caption_clips(
                        scene.get("text", ""), 
                        duration, 
                        (config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
                        lang=scene.get("lang", "en")
                    )
                    
                    final_clip = CompositeVideoClip([clip, *caption_clips]).with_duration(duration)
                    scene_clips.append(final_clip)
                    continue

                # 2. Standard Image Scene
                clip = compose_scene(scene)
                if clip:
                    scene_clips.append(clip)
            except Exception as e:
                log.error(f"Failed to compose scene {i+1}: {e}")
                continue

        if not scene_clips:
            log.error("No valid clips were created!")
            return None

        # Concatenate scenes with crossfade
        if len(scene_clips) > 1 and config.CROSSFADE_DURATION > 0:
            final = concatenate_videoclips(
                scene_clips,
                method="compose",
                padding=-config.CROSSFADE_DURATION
            )
        else:
            final = concatenate_videoclips(scene_clips, method="compose")

        # Resize to target
        final = final.resized(new_size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))

        # Add "Lens AI" Logo Overlay (top-right corner)
        try:

            logo_path = Path("video_creation/media/logo.png")
            if logo_path.exists():
                logo_clip = (
                    ImageClip(str(logo_path))
                    .with_duration(final.duration)
                    .resized(height=70) # Slightly larger
                    .with_position((final.w - 220, 30))  # top-right with ONE padding (220px from right)
                    .with_opacity(0.90)
                )
                final = CompositeVideoClip([final, logo_clip])
                log.info("Logo overlay added.")
        except Exception as e:
             log.warning(f"Failed to add logo overlay: {e}")

        # Add Scrolling News Ticker + LIVE Badge (PIL frame-by-frame)
        try:
            from PIL import Image, ImageDraw, ImageFont
            import numpy as np


            narration_text = "Breaking News"
            if scenes and len(scenes) > 0:
                narration_text = scenes[0].get('narration', 'Developing Story')
            
            ticker_content = f"  BREAKING NEWS  •  {narration_text[:60]}  •  LENS AI REPORTING  •  LIVE UPDATES  •  " * 3
            
            font_size = 32
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except:
                try:
                    font = ImageFont.truetype("Arial", font_size)
                except:
                    font = ImageFont.load_default()
            
            live_font_size = 28
            try:
                live_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", live_font_size)
            except:
                live_font = font

            # Pre-calculate text width
            dummy_img = Image.new("RGB", (1, 1))
            dummy_draw = ImageDraw.Draw(dummy_img)
            text_bbox = dummy_draw.textbbox((0, 0), ticker_content, font=font)
            text_total_w = text_bbox[2] - text_bbox[0]
            
            bar_h = 70
            vid_w = final.w
            vid_h = final.h
            scroll_speed = 150  # pixels per second

            def make_ticker_frame(t):
                """Render one frame of the news ticker bar."""
                frame = Image.new("RGBA", (vid_w, bar_h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(frame)
                
                # Red background bar
                draw.rectangle([0, 0, vid_w, bar_h], fill=(180, 0, 0, 230))
                
                # Scrolling text
                x_offset = int(vid_w - scroll_speed * t) % (text_total_w + vid_w) - text_total_w
                draw.text((x_offset, bar_h // 2), ticker_content, font=font, fill="white", anchor="lm")
                
                return np.array(frame)
            
            ticker_overlay = (
                VideoClip(make_ticker_frame, duration=final.duration)
                .with_position((0, vid_h - bar_h))
                .with_fps(config.VIDEO_FPS)
            )

            # LIVE Badge (static PIL image, with blink)
            badge_w, badge_h = 130, 45
            img_live = Image.new("RGBA", (badge_w, badge_h), (220, 0, 0, 255))
            draw_live = ImageDraw.Draw(img_live)
            # Rounded corners effect (simple)
            draw_live.text((badge_w // 2, badge_h // 2), "● LIVE", font=live_font, fill="white", anchor="mm")
            
            live_badge = (
                ImageClip(np.array(img_live))
                .with_position((30, 30))
                .with_duration(final.duration)
                .with_effects([vfx.Blink(duration_on=0.7, duration_off=0.3)])
            )

            # Compose everything
            final = CompositeVideoClip([final, ticker_overlay, live_badge])
            log.info("News overlays added (ticker + LIVE badge).")

        except Exception as e:
            log.warning(f"Failed to add news overlays: {e}")
            import traceback
            traceback.print_exc()

        # Add Background Music (Loop) - NEW PRO TRACK
        bgm_path = config.SFX_DIR / "news_background_pro.wav"
        if not bgm_path.exists():
             bgm_path = config.SFX_DIR / "music_loop.wav" # Fallback

        if bgm_path.exists():
            try:
                from moviepy import CompositeAudioClip, afx
                
                bgm = AudioFileClip(str(bgm_path))
                # Loop BGM
                bgm = bgm.with_effects([afx.AudioLoop(duration=final.duration)])
                
                # Volume - louder for impact if pro track, cleaner mix
                bgm = bgm.with_volume_scaled(0.20)
                
                # Mix with existing video audio
                if final.audio:
                    final_audio = CompositeAudioClip([final.audio, bgm])
                    final = final.with_audio(final_audio)
                else:
                    final = final.with_audio(bgm)
                    
                log.info("Background music added.")
            except Exception as e:
                log.warning(f"Failed to add background music using 'AudioLoop': {e}")
                # Fallback: simple manual loop
                try:
                    bgm = AudioFileClip(str(bgm_path))
                    loops = int(final.duration / bgm.duration) + 1
                    bgm = concatenate_audioclips([bgm] * loops).with_duration(final.duration)
                    bgm = bgm.with_volume_scaled(0.20)
                    if final.audio:
                        final_audio = CompositeAudioClip([final.audio, bgm])
                        final = final.with_audio(final_audio)
                    else:
                        final = final.with_audio(bgm)
                    log.info("Background music added (fallback method).")
                except Exception as e2:
                    log.error(f"Fallback BGM failed: {e2}")

        # Export
        log.info(f"Exporting video ({final.duration:.1f}s) to {output_path.name}...")

        final.write_videofile(
            str(output_path),
            fps=config.VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger=None,
        )

        # Cleanup
        final.close()
        for clip in scene_clips:
            clip.close()

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        log.info(f"Video exported: {output_path.name} ({file_size_mb:.1f}MB)")

        return str(output_path)

    except Exception as e:
        log.error(f"Failed to export video: {e}")
        for clip in scene_clips:
            try:
                clip.close()
            except Exception:
                pass
        return None
