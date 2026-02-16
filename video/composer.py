"""
Video Composer — assembles final 9:16 short-form videos using MoviePy.
Features: Ken Burns effect, word-by-word captions, crossfade transitions.
"""

import os
import re
import math
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config
from utils.logger import log

# MoviePy imports
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, CompositeAudioClip,
    TextClip, ColorClip
)
import moviepy.video.fx.all as vfx


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
    
    return "Helvetica"  # MoviePy default


SYSTEM_FONT = _find_system_font()


# ─── Ken Burns Effect ────────────────────────────────────

def apply_ken_burns(image_path: str, duration: float, zoom_start: float = 1.0, 
                     zoom_end: float = None) -> ImageClip:
    """
    Create a video clip from a still image with Ken Burns zoom effect.
    
    The image slowly zooms from zoom_start to zoom_end over the duration.
    """
    zoom_end = zoom_end or config.ZOOM_FACTOR
    
    # Load image at higher resolution for zoom headroom
    img = Image.open(image_path)
    
    # Ensure image is large enough for zooming
    target_w = int(config.VIDEO_WIDTH * zoom_end * 1.1)
    target_h = int(config.VIDEO_HEIGHT * zoom_end * 1.1)
    
    if img.width < target_w or img.height < target_h:
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    img_array = np.array(img)
    
    def make_frame(t):
        """Generate a frame at time t with zoom applied."""
        progress = t / max(duration, 0.01)
        current_zoom = zoom_start + (zoom_end - zoom_start) * progress
        
        # Calculate crop region (zoom into center)
        h, w = img_array.shape[:2]
        crop_w = int(config.VIDEO_WIDTH / current_zoom)
        crop_h = int(config.VIDEO_HEIGHT / current_zoom)
        
        # Center crop with slight drift for more dynamic feel
        drift_x = int(20 * math.sin(progress * math.pi))  # Subtle horizontal drift
        cx = w // 2 + drift_x
        cy = h // 2
        
        x1 = max(0, cx - crop_w // 2)
        y1 = max(0, cy - crop_h // 2)
        x2 = min(w, x1 + crop_w)
        y2 = min(h, y1 + crop_h)
        
        # Adjust if crop goes out of bounds
        if x2 - x1 < crop_w:
            x1 = max(0, x2 - crop_w)
        if y2 - y1 < crop_h:
            y1 = max(0, y2 - crop_h)
        
        # Crop and resize to target
        cropped = img_array[y1:y2, x1:x2]
        
        # Resize using PIL for quality
        pil_img = Image.fromarray(cropped)
        pil_img = pil_img.resize(
            (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), 
            Image.Resampling.LANCZOS
        )
        
        return np.array(pil_img)
    
    clip = ImageClip(image_path).set_duration(duration)
    clip = clip.fl(lambda gf, t: make_frame(t))
    clip = clip.set_duration(duration)
    
    return clip


# ─── Caption Generation ──────────────────────────────────

def _split_into_word_groups(text: str, words_per_group: int = 4) -> list[str]:
    """Split narration text into display groups of N words."""
    words = text.split()
    groups = []
    for i in range(0, len(words), words_per_group):
        group = " ".join(words[i:i + words_per_group])
        groups.append(group)
    return groups


def create_caption_clips(narration: str, duration: float, 
                          video_size: tuple = None) -> list:
    """
    Create word-by-word highlighted caption clips.
    
    Shows groups of 3-4 words at a time, with the current word highlighted.
    Returns a list of TextClip objects with proper timing.
    """
    if not narration.strip():
        return []
    
    video_size = video_size or (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
    words = narration.split()
    
    if not words:
        return []
    
    # Time per word (evenly distributed)
    time_per_word = duration / len(words)
    
    caption_clips = []
    words_per_group = 4
    
    for group_idx in range(0, len(words), words_per_group):
        group_words = words[group_idx:group_idx + words_per_group]
        group_start = group_idx * time_per_word
        group_end = min((group_idx + len(group_words)) * time_per_word, duration)
        group_duration = group_end - group_start
        
        # For each word in the group, create a highlight moment
        for word_offset, current_word_idx in enumerate(range(group_idx, group_idx + len(group_words))):
            word_start = current_word_idx * time_per_word
            word_end = min((current_word_idx + 1) * time_per_word, duration)
            word_duration = word_end - word_start
            
            if word_duration <= 0:
                continue
            
            # Build the caption text with highlighted current word
            # We'll create the full group text, then overlay a highlight
            full_text = " ".join(group_words)
            
            try:
                # Base text (all white)
                base_clip = TextClip(
                    full_text,
                    fontsize=config.CAPTION_FONT_SIZE,
                    color=config.CAPTION_COLOR,
                    font=SYSTEM_FONT,
                    stroke_color=config.CAPTION_STROKE_COLOR,
                    stroke_width=config.CAPTION_STROKE_WIDTH,
                    method="caption",
                    size=(video_size[0] - 80, None),
                    align="center",
                )
                
                base_clip = (base_clip
                    .set_start(word_start)
                    .set_duration(word_duration)
                    .set_position(("center", config.CAPTION_POSITION[1]), relative=True))
                
                caption_clips.append(base_clip)
                
            except Exception as e:
                log.debug(f"Caption creation error: {e}")
                # Simplified fallback
                try:
                    simple_clip = TextClip(
                        full_text,
                        fontsize=config.CAPTION_FONT_SIZE - 10,
                        color="white",
                        method="label",
                    )
                    simple_clip = (simple_clip
                        .set_start(word_start)
                        .set_duration(word_duration)
                        .set_position(("center", 0.80), relative=True))
                    caption_clips.append(simple_clip)
                except Exception:
                    pass
    
    return caption_clips


# ─── Scene Assembly ───────────────────────────────────────

def compose_scene(scene: dict) -> Optional[CompositeVideoClip]:
    """
    Compose a single scene: image with Ken Burns + audio + captions.
    """
    image_path = scene.get("image_path")
    audio_path = scene.get("audio_path")
    narration = scene.get("narration", "")
    duration = scene.get("actual_duration", scene.get("estimated_duration", 5.0))
    
    if not image_path or not os.path.exists(image_path):
        log.warning(f"Scene missing image: {image_path}")
        return None
    
    try:
        # Create Ken Burns clip from image
        video_clip = apply_ken_burns(image_path, duration)
        
        layers = [video_clip]
        
        # Add semi-transparent overlay at bottom for caption readability
        overlay_height = int(config.VIDEO_HEIGHT * 0.3)
        overlay = ColorClip(
            size=(config.VIDEO_WIDTH, overlay_height),
            color=(0, 0, 0)
        ).set_opacity(0.5).set_duration(duration)
        overlay = overlay.set_position(("center", config.VIDEO_HEIGHT - overlay_height))
        layers.append(overlay)
        
        # Add captions
        caption_clips = create_caption_clips(
            narration, duration,
            (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
        )
        layers.extend(caption_clips)
        
        # Composite everything
        scene_clip = CompositeVideoClip(
            layers,
            size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
        ).set_duration(duration)
        
        # Add audio
        if audio_path and os.path.exists(audio_path):
            try:
                audio = AudioFileClip(audio_path)
                # Match audio duration to video
                if abs(audio.duration - duration) > 0.5:
                    duration = audio.duration
                    scene_clip = scene_clip.set_duration(duration)
                scene_clip = scene_clip.set_audio(audio)
            except Exception as e:
                log.warning(f"Failed to attach audio: {e}")
        
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
    
    # Compose each scene
    scene_clips = []
    for i, scene in enumerate(scenes):
        log.info(f"  Composing scene {i+1}/{len(scenes)}: {scene.get('scene_type', 'unknown')}")
        clip = compose_scene(scene)
        if clip:
            scene_clips.append(clip)
        else:
            log.warning(f"  Skipping scene {i+1} (composition failed)")
    
    if not scene_clips:
        log.error("No scenes could be composed")
        return None
    
    try:
        # Concatenate scenes with crossfade
        if len(scene_clips) > 1 and config.CROSSFADE_DURATION > 0:
            # Apply crossfade method
            final = concatenate_videoclips(
                scene_clips,
                method="compose",
                padding=-config.CROSSFADE_DURATION
            )
        else:
            final = concatenate_videoclips(scene_clips, method="compose")
        
        # Set final size
        final = final.resize(newsize=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))
        
        # Export
        log.info(f"Exporting video ({final.duration:.1f}s) to {output_path.name}...")
        
        final.write_videofile(
            str(output_path),
            fps=config.VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger=None,  # Suppress moviepy's verbose logging
        )
        
        # Cleanup
        final.close()
        for clip in scene_clips:
            clip.close()
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        log.info(f"Video exported: {output_path.name} ({file_size_mb:.1f}MB, {final.duration:.1f}s)")
        
        return str(output_path)
        
    except Exception as e:
        log.error(f"Failed to export video: {e}")
        # Cleanup on failure
        for clip in scene_clips:
            try:
                clip.close()
            except Exception:
                pass
        return None
