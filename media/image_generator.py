"""
Image Generator v2 — creates AI-generated visuals for each video scene
using HF Inference API (FLUX.1-dev / SDXL / FLUX.1-schnell).
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


def _call_hf_image(prompt: str, model: str) -> Optional[bytes]:
    """Call HF Inference API for image generation. Returns raw image bytes."""
    headers = {"Authorization": f"Bearer {config.HF_API_KEY}"}
    url = f"{config.HF_API_BASE}/{model}"
    
    # Enhance prompt for better quality using config-based style suffix
    enhanced_prompt = f"{prompt}. {config.IMAGE_STYLE_SUFFIX}"
    
    payload = {
        "inputs": enhanced_prompt,
        "parameters": {
            "width": GEN_WIDTH,
            "height": GEN_HEIGHT,
            "negative_prompt": config.IMAGE_NEGATIVE_PROMPT,
        },
    }
    
    for attempt in range(config.HF_MAX_RETRIES):
        try:
            resp = requests.post(
                url, headers=headers, json=payload,
                timeout=config.HF_API_TIMEOUT * 2  # Image gen can take longer
            )
            
            if resp.status_code == 503:
                wait_time = 30
                try:
                    wait_time = resp.json().get("estimated_time", 30)
                except Exception:
                    pass
                log.warning(f"Image model {model} loading, waiting {wait_time:.0f}s...")
                time.sleep(min(wait_time, 120))
                continue
            
            if resp.status_code == 500:
                log.warning(f"Image gen server error (attempt {attempt + 1})")
                time.sleep(5)
                continue
            
            resp.raise_for_status()
            
            content_type = resp.headers.get("content-type", "")
            if "image" in content_type or len(resp.content) > 5000:
                return resp.content
            
            log.warning(f"Image gen returned non-image content: {content_type}")
            return None
            
        except requests.exceptions.Timeout:
            log.warning(f"Image gen timeout (attempt {attempt + 1})")
            continue
        except Exception as e:
            log.warning(f"Image gen error with {model}: {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            continue
    
    return None


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
        
        # Dark gradient-like background
        img = Image.new("RGB", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), (15, 15, 25))
        draw = ImageDraw.Draw(img)
        
        # Add subtle gradient effect
        for y in range(config.VIDEO_HEIGHT):
            r = int(15 + (25 * y / config.VIDEO_HEIGHT))
            g = int(15 + (15 * y / config.VIDEO_HEIGHT))
            b = int(25 + (35 * y / config.VIDEO_HEIGHT))
            draw.line([(0, y), (config.VIDEO_WIDTH, y)], fill=(r, g, b))
        
        # Add text if provided
        if text:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except (OSError, IOError):
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
                except (OSError, IOError):
                    font = ImageFont.load_default()
            
            # Word wrap
            words = text.split()
            lines = []
            current_line = ""
            for word in words:
                test = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test, font=font)
                if bbox[2] < config.VIDEO_WIDTH - 100:
                    current_line = test
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            y_start = config.VIDEO_HEIGHT // 2 - (len(lines) * 45) // 2
            for i, line in enumerate(lines[:5]):
                bbox = draw.textbbox((0, 0), line, font=font)
                x = (config.VIDEO_WIDTH - bbox[2]) // 2
                draw.text((x, y_start + i * 45), line, fill=(200, 200, 220), font=font)
        
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
    
    # Try primary model
    image_bytes = _call_hf_image(prompt, config.IMAGE_MODEL)
    
    # Try fallback 1
    if not image_bytes:
        log.warning(f"Primary image model ({config.IMAGE_MODEL}) failed, trying fallback...")
        image_bytes = _call_hf_image(prompt, config.IMAGE_FALLBACK)
    
    # Try fallback 2
    if not image_bytes:
        log.warning(f"Fallback image model ({config.IMAGE_FALLBACK}) also failed, trying fallback 2...")
        image_bytes = _call_hf_image(prompt, config.IMAGE_FALLBACK_2)
    
    if image_bytes:
        if _save_and_resize_image(image_bytes, output_path):
            log.info(f"Image generated: {output_path.name}")
            return str(output_path)
    
    # Use fallback solid image
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
