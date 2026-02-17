
import os
import requests
from pathlib import Path
from utils.logger import log
import config

def generate_news_music(output_path: Path, prompt: str = "", duration: int = 30):
    """
    Download a professional royalty-free 'Breaking News' track.
    Using a known copyright-free asset.
    """
    # Direct link to a high-quality news intro/loop (Royalty Free)
    # Using a reliable PixaBay asset for demo purposes
    # "News Background" style
    TRACK_URL = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=breaking-news-intro-12792.mp3" 
    
    log.info(f"Downloading professional news track from {TRACK_URL}...")
    
    try:
        response = requests.get(TRACK_URL, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)
            log.info(f"Music downloaded to {output_path}")
            return True
        else:
            log.error(f"Download failed: {response.status_code}")
            return False
            
    except Exception as e:
        log.error(f"Music download error: {e}")
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    out_dir = Path("media/sfx")
    out_dir.mkdir(parents=True, exist_ok=True)
    generate_news_music(out_dir / "news_background_pro.wav")
