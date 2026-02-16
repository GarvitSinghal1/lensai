"""
Image Generator v2 — creates AI-generated visuals for each video scene
using HF Inference API. Fallback chain: FLUX.2-dev → FLUX.1-dev → SDXL.
Enhanced with cinematic style guidelines and negative prompt support.
"""

import io
import time
import requests
from pathlib import Path
from typing import Optional
from PIL import Image

import config
from utils.logger import log

# 9:16 aspect ratio dimensions for generation
# Generate smaller, then upscale in video composer for performance
GEN_WIDTH = 576
GEN_HEIGHT = 1024





def _save_and_resize_image(image_bytes: bytes, output_path: Path) -> bool:
    """Save image bytes and resize to target dimensions."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary (RGBA → RGB)
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (0, 0, 0))
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        
        # Resize to target video dimensions
        img = img.resize(
            (config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
            Image.Resampling.LANCZOS
        )
        
        img.save(output_path, "PNG", quality=95)
        return True
        
    except Exception as e:
        log.error(f"Failed to process image: {e}")
        return False


def _generate_solid_fallback(output_path: Path, text: str = "") -> bool:
    """Generate a solid-color fallback image with text overlay."""
    try:
        from PIL import ImageDraw, ImageFont
        
        # Brighter blue/purple gradient background
        img = Image.new("RGB", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), (20, 20, 40))
        draw = ImageDraw.Draw(img)
        
        # Add gradient effect (Dark Blue -> Lighter Blue/Purple)
        for y in range(config.VIDEO_HEIGHT):
            r = int(20 + (40 * y / config.VIDEO_HEIGHT))
            g = int(20 + (20 * y / config.VIDEO_HEIGHT))
            b = int(60 + (80 * y / config.VIDEO_HEIGHT))
            draw.line([(0, y), (config.VIDEO_WIDTH, y)], fill=(r, g, b))
        
        # Add explicit "IMAGE GENERATION FAILED" warning
        draw.text((50, 50), "AI IMAGE GEN FAILED", fill=(255, 100, 100))
        
        # Add text if provided
        if text:
            font = None
            # Try common Mac/Linux fonts
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
            ]
            
            for path in font_paths:
                try:
                    font = ImageFont.truetype(path, 40)
                    break
                except (OSError, IOError):
                    continue
            
            if not font:
                font = ImageFont.load_default()
            
            # Word wrap
            words = text.split()
            lines = []
            current_line = ""
            for word in words:
                test = f"{current_line} {word}".strip()
                # Check width (handling default font lacking getbbox in older Pillow)
                try:
                    bbox = draw.textbbox((0, 0), test, font=font)
                    width = bbox[2]
                except AttributeError:
                    width = len(test) * 10 # Rough estimate for default font
                    
                if width < config.VIDEO_WIDTH - 60:
                    current_line = test
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            # Draw lines centered
            line_height = 50
            total_height = len(lines) * line_height
            y_start = (config.VIDEO_HEIGHT - total_height) // 2
            
            for i, line in enumerate(lines[:10]): # Limit lines
                try:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2]
                except AttributeError:
                    text_width = len(line) * 10
                    
                x = (config.VIDEO_WIDTH - text_width) // 2
                draw.text((x, y_start + i * line_height), line, fill=(255, 255, 255), font=font)
        
        img.save(output_path, "PNG")
        return True
        
    except Exception as e:
        log.error(f"Failed to create fallback image: {e}")
        return False


def generate_image(prompt: str, output_path: Path) -> Optional[str]:
    """
    Generate an AI image from a text prompt.
    
    Returns the output path string on success, None on failure.
    """
    if not prompt.strip():
        log.warning("Empty prompt provided to image generator")
        return None
    
    log.info(f"Generating image: \"{prompt[:70]}...\"")
    output_path = Path(output_path).with_suffix('.png')
    
    # Use centralized HF client (handles Replicate Flux 2, Flux 1, SDXL fallbacks)
    from utils import hf_client
    image_bytes = hf_client.generate_image(prompt)
    
    if image_bytes:
        if _save_and_resize_image(image_bytes, output_path):
            log.info(f"Image generated: {output_path.name}")
            return str(output_path)
    
    # Use fallback solid image if all API methods fail
    log.warning("All image models failed, using fallback image")
    if _generate_solid_fallback(output_path, prompt[:100]):
        return str(output_path)
    
    return None


def generate_images_for_scenes(scenes: list[dict], temp_dir: Path) -> list[dict]:
    """
    Generate images for all scenes in a script.
    
    Adds 'image_path' to each scene dict.
    Returns the updated scenes list.
    """
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    for i, scene in enumerate(scenes):
        image_prompt = scene.get("image_prompt", "")
        if not image_prompt:
            image_prompt = f"Cinematic news visual: {scene.get('narration', 'Breaking news')[:100]}"
        
        image_file = temp_dir / f"scene_{i:02d}.png"
        result = generate_image(image_prompt, image_file)
        
        if result:
            scene["image_path"] = result
        else:
            # Generate fallback
            fallback = temp_dir / f"scene_{i:02d}_fallback.png"
            if _generate_solid_fallback(fallback, scene.get("narration", "")[:80]):
                scene["image_path"] = str(fallback)
            else:
                scene["image_path"] = None
        
        # Delay between image gen calls
        if i < len(scenes) - 1:
            time.sleep(2)
    
    generated = sum(1 for s in scenes if s.get("image_path"))
    log.info(f"Image generation complete: {generated}/{len(scenes)} scenes")
    return scenes
