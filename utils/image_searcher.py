
import requests
import re
import random
from pathlib import Path
from typing import Optional, List
from utils.logger import log

def search_google_images(query: str, output_path: Path) -> Optional[str]:
    """
    Search for an image of a specific person/entity using DuckDuckGo (HTML scraping).
    Fallback to a simple scraping method if possible.
    
    Args:
        query: Search query (e.g., "Bill Gates photo")
        output_path: Path to save the image
        
    Returns:
        Path to saved image string, or None if failed.
    """
    try:
        log.info(f"🔍 Searching web for image: '{query}'...")
        
        # DuckDuckGo HTML scraping (No API key needed, but fragile)
        # Headers to look like a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        
        # 1. Get DDG search page
        # vqd is needed for API, but let's try the 'lite' version or regex from main page
        # Actually, standard DDG search: https://duckduckgo.com/?q=...&t=h_&iax=images&ia=images
        # It loads via JS.
        # Minimal HTML version: https://duckduckgo.com/html/?q=...
        
        search_url = "https://duckduckgo.com/html/"
        params = {"q": query, "iax": "images", "ia": "images"}
        
        resp = requests.post(search_url, data=params, headers=headers, timeout=10) # DDG HTML uses POST sometimes? Or GET.
        # Try GET first
        resp = requests.get(search_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        
        # 2. Extract Image URLs
        # Look for 'content': 'https://...' inside class 'tile--img__img'
        # Or look for src="..." in img tags.
        # DDG HTML returns results like: <a class="tile--img__a" href="..."> <img class="tile--img__img" src="...">
        # The src in tile--img__img is usually a thumbnail (proxy).
        # Should rely on thumbnail? Yes, for video it's often okay (if 480p+).
        # But better to get full image if possible.
        # In /html/ mode, it links to result.
        
        # Regex to find image URLs
        # Looking for src="https://external-content.duckduckgo.com/iu/?u=..."
        # or direct URLs.
        
        urls = re.findall(r'src="(https?://[^"]+)"', resp.text)
        
        # Filter for likely image results (DDG proxies)
        image_urls = [u for u in urls if ".jpg" in u or ".png" in u or "external-content" in u]
        
        # Prioritize non-favicon/non-tiny images
        filtered_urls = []
        for u in image_urls:
            if "favicon" in u or "icon" in u: continue
            # Unescape generic HTML entities if needed
            u = u.replace("&amp;", "&")
            filtered_urls.append(u)
            
        if not filtered_urls:
            log.warning("No images found in search results.")
            return None
            
        # Try downloading first few
        for i, url in enumerate(filtered_urls[:5]):
            try:
                log.info(f"Downloading search result {i+1}: {url[:60]}...")
                img_resp = requests.get(url, headers=headers, timeout=5)
                img_resp.raise_for_status()
                
                # Check size
                if len(img_resp.content) < 10000: # Skip < 10KB images ( likely icons)
                     continue
                     
                # Save
                from video_creation.media.image_generator import _save_and_resize_image
                if _save_and_resize_image(img_resp.content, output_path):
                    return str(output_path)
                    
            except Exception as e:
                log.warning(f"Failed to download search result {i}: {e}")
                continue
                
        return None

    except Exception as e:
        log.error(f"Image search failed: {e}")
        return None
