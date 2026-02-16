"""
Video Composer v2 — assembles final 9:16 short-form videos using MoviePy v2.
Features: Ken Burns effect, word-by-word captions, crossfade transitions.
Compatible with MoviePy >= 2.0
"""

import os
import math
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config
from utils.logger import log

# MoviePy v2 imports
from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, TextClip, ColorClip, VideoClip
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


SYSTEM_FONT = _find_system_font()


# ─── Ken Burns Effect ────────────────────────────────────

def apply_ken_burns(image_path: str, duration: float, zoom_start: float = 1.0,
                     zoom_end: float = None) -> VideoClip:
    """
    Create a video clip from a still image with Ken Burns zoom effect.
    The image slowly zooms from zoom_start to zoom_end over the duration.
    """
    zoom_end = zoom_end or config.ZOOM_FACTOR

    # Load image at higher resolution for zoom headroom
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Ensure image is large enough for zooming
    target_w = int(config.VIDEO_WIDTH * zoom_end * 1.1)
    target_h = int(config.VIDEO_HEIGHT * zoom_end * 1.1)

    if img.width < target_w or img.height < target_h:
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    img_array = np.array(img)
    h, w = img_array.shape[:2]

    def make_frame(t):
        """Generate a frame at time t with zoom applied."""
        progress = t / max(duration, 0.01)
        progress = min(progress, 1.0)
        current_zoom = zoom_start + (zoom_end - zoom_start) * progress

        # Calculate crop region (zoom into center)
        crop_w = int(config.VIDEO_WIDTH / current_zoom)
        crop_h = int(config.VIDEO_HEIGHT / current_zoom)

        # Center crop with slight drift for more dynamic feel
        drift_x = int(20 * math.sin(progress * math.pi))
        cx = w // 2 + drift_x
        cy = h // 2

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

    return clip


# ─── Caption Generation (PIL-based for reliability) ──────

def _render_caption_frame(text: str, highlight_word_idx: int,
                           words: list, video_size: tuple) -> np.ndarray:
    """Render a caption frame using PIL (more reliable than TextClip)."""
    w, h = video_size
    # Create transparent-ish overlay
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(SYSTEM_FONT, config.CAPTION_FONT_SIZE)
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

    return np.array(img.convert("RGB"))


def create_caption_clips(narration: str, duration: float,
                          video_size: tuple = None) -> list:
    """
    Create word-by-word highlighted caption clips using PIL rendering.
    Shows groups of 4 words at a time with the current word highlighted.
    """
    if not narration.strip():
        return []

    video_size = video_size or (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
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
                    group_words, video_size
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
        ).with_duration(duration)

        # Add audio
        if audio_path and os.path.exists(audio_path):
            try:
                audio = AudioFileClip(audio_path)
                # Match audio duration to video
                if abs(audio.duration - duration) > 0.5:
                    duration = audio.duration
                    scene_clip = scene_clip.with_duration(duration)
                scene_clip = scene_clip.with_audio(audio)
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
            final = concatenate_videoclips(
                scene_clips,
                method="compose",
                padding=-config.CROSSFADE_DURATION
            )
        else:
            final = concatenate_videoclips(scene_clips, method="compose")

        # Resize to target
        final = final.resized(new_size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))

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
