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
        
        # Validate image dimensions (avoid tracking pixels or icons)
        if img.width < 300 or img.height < 300:
            log.warning(f"Image too small ({img.width}x{img.height}), skipping.")
            return False

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
        
        # Resize to target video dimensions (Aspect Fill)
        target_ratio = config.VIDEO_WIDTH / config.VIDEO_HEIGHT
        img_ratio = img.width / img.height
        
        if img_ratio > target_ratio:
            # Image is wider than target
            new_height = config.VIDEO_HEIGHT
            new_width = int(new_height * img_ratio)
        else:
            # Image is taller than target
            new_width = config.VIDEO_WIDTH
            new_height = int(new_width / img_ratio)
            
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center crop to fit exactly
        left = (new_width - config.VIDEO_WIDTH) // 2
        top = (new_height - config.VIDEO_HEIGHT) // 2
        right = left + config.VIDEO_WIDTH
        bottom = top + config.VIDEO_HEIGHT
        
        img = img.crop((left, top, right, bottom))
        
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
        # Brighter background (Deep Blue/Purple but visible)
        # Using a much brighter gradient (Cyan -> Magenta -> Yellow) to be unmistakably NOT black
        img = Image.new("RGB", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # Add gradient effect (Cyan -> Magenta)
        for y in range(config.VIDEO_HEIGHT):
            # Vivid gradient: Cyan (0, 255, 255) to Magenta (255, 0, 255)
            r = int(255 * (y / config.VIDEO_HEIGHT))
            g = int(255 * ((config.VIDEO_HEIGHT - y) / config.VIDEO_HEIGHT))
            b = 255
            draw.line([(0, y), (config.VIDEO_WIDTH, y)], fill=(r, g, b))
        
        # Add explicit "IMAGE GENERATION FAILED" warning
        # Draw a box for text backdrop
        draw.rectangle([50, config.VIDEO_HEIGHT//2 - 100, config.VIDEO_WIDTH-50, config.VIDEO_HEIGHT//2 + 100], fill=(0,0,0,128))
        draw.text((100, config.VIDEO_HEIGHT//2), "AI IMAGE GEN FAILED", fill=(255, 255, 255))
        
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
        
    # Privacy / Search Strategy:
    # 1. Detect Specific People (Entities) -> Trigger Search
    # 2. Generic concepts -> Use AI
    
    should_search = False
    search_query = prompt
    
    import re
    # Check for specific patterns that indicate a person of interest
    # We use the same regex patterns but trigger SEARCH instead of genericizing
    entity_patterns = [
        r"(?i)\b(Joe )?Biden\b",
        r"(?i)\b(Donald )?Trump\b", 
        r"(?i)\b(Barack )?Obama\b",
        r"(?i)\b(Elon )?Musk\b",
        r"(?i)\b(Bill )?Gates\b",
        r"(?i)\b(Mark )?Zuckerberg\b",
        r"(?i)\b(Jeff )?Bezos\b",
        r"(?i)\b(Narendra )?Modi\b",
        r"(?i)\b(Vladimir )?Putin\b",
        r"(?i)\b(Volodymyr )?Zelenskyy?\b",
        r"(?i)\b(Rishi )?Sunak\b", 
        r"(?i)\b(Emmanuel )?Macron\b",
        r"(?i)\b(Justin )?Trudeau\b"
    ]
    
    for pattern in entity_patterns:
        if re.search(pattern, prompt):
            should_search = True
            log.info(f"Detected named entity matching '{pattern}'. Switching to Web Search.")
            break
            
    if should_search:
        try:
            from utils.image_searcher import search_google_images
            # Clean up prompt for search (remove artistic style keywords if present?)
            # Actually, "A photo of Bill Gates jumping" is a good search query.
            # Maybe strip "cinematic lighting" etc if they were added (they aren't here yet, added inside hf_client).
            
            search_path = search_google_images(prompt, output_path)
            if search_path:
                return search_path
            else:
                log.warning("Web search failed. Falling back to AI (with sanitization?) or failing?")
                # User said: "just don't use specific persons in the image generation"
                # So if search fails, we should probably genericize like before to be safe?
                # "You can use the AI to create a scared person... but not Bill Gates"
                # So let's sanitize IF search fails.
                pass 
        except Exception as e:
            log.error(f"Search module error: {e}")

    # Fallback to AI (or primary AI if no entity)
    # If we tried search and failed, sanitize strictly before AI
    if should_search:
        log.info("Search failed/skipped. Sanitizing prompt for AI fallback...")
        replacements = {
            r"(?i)\b(Joe )?Biden\b": "a politician",
            r"(?i)\b(Donald )?Trump\b": "a politician", 
            r"(?i)\b(Barack )?Obama\b": "a politician",
            r"(?i)\b(Elon )?Musk\b": "a tech CEO",
            r"(?i)\b(Bill )?Gates\b": "a tech CEO",
            r"(?i)\b(Mark )?Zuckerberg\b": "a tech CEO",
            r"(?i)\b(Jeff )?Bezos\b": "a tech CEO", 
            r"(?i)\b(Narendra )?Modi\b": "a politician",
            r"(?i)\b(Vladimir )?Putin\b": "a politician",
            r"(?i)\b(Volodymyr )?Zelenskyy?\b": "a politician",
            r"(?i)\b(Rishi )?Sunak\b": "a politician",
            r"(?i)\b(Emmanuel )?Macron\b": "a politician",
            r"(?i)\b(Justin )?Trudeau\b": "a politician"
        }
        for pattern, replacement in replacements.items():
            prompt = re.sub(pattern, replacement, prompt)
            
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


def _download_and_process_image(url: str, output_path: Path) -> bool:
    """Download image from URL and resize/crop to target dimensions."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        return _save_and_resize_image(resp.content, output_path)
    except Exception as e:
        log.warning(f"Failed to download image {url}: {e}")
        return False

def generate_images_for_scenes(scenes: list[dict], temp_dir: Path, article_images: list[str] = None) -> list[dict]:
    """
    Assign images to scenes using scraped article images.
    """
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    if not article_images:
        article_images = []
        
    img_idx = 0
    
    for i, scene in enumerate(scenes):
        output_path = temp_dir / f"scene_{i:02d}.png"
        success = False
        
        # Try to use a scraped image
        # Try to use a scraped image (Linear assignment, no reuse)
        if article_images and img_idx < len(article_images):
            # Pick next available image
            img_url = article_images[img_idx]
            img_idx += 1
            
            log.info(f"Downloading scraped image {img_idx}/{len(article_images)} for scene {i+1}: {img_url[:60]}...")
            if _download_and_process_image(img_url, output_path):
                scene["image_path"] = str(output_path)
                success = True
            else:
                log.warning(f"Image download failed for {img_url[:40]}.")
                # If download failed, we consumed the URL. Should we try next?
                # For simplicity, if this one failed, we fall through to AI gen for this scene.
                # Or we could loop to find next valid one?
                # Let's keep it simple: failed download = fall to AI for this scene.
        
        # If scraped image unavailable (exhausted or failed), try AI generation
        if not success and scene.get("image_prompt"):
            prompt = scene["image_prompt"]
            log.info(f"Generating AI image for scene {i+1} (Reason: Scraped exhausted/failed)...")
            ai_image_path = generate_image(prompt, output_path)
            if ai_image_path:
                scene["image_path"] = ai_image_path
                success = True
        # If no image found or download failed, use fallback
        if not success:
            log.warning(f"No valid image found for scene {i+1}, using fallback.")
            fallback = temp_dir / f"scene_{i:02d}_fallback.png"
            if _generate_solid_fallback(fallback, scene.get("narration", "")[:80]):
                scene["image_path"] = str(fallback)
            else:
                scene["image_path"] = None
                
    generated = sum(1 for s in scenes if s.get("image_path"))
    log.info(f"Visuals assigned: {generated}/{len(scenes)} scenes")
    return scenes
