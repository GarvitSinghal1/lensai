
import os
import requests
import random
from pathlib import Path
from typing import Optional
import config
from utils.logger import log

class PexelsClient:
    def __init__(self):
        self.api_key = config.PEXELS_API_KEY
        self.base_url = "https://api.pexels.com/videos"
        self.search_url = f"{self.base_url}/search"
        
    def search_video(self, query: str, orientation: str = "portrait", size: str = "medium", duration_min: int = 3) -> Optional[Path]:
        """
        Search for a stock video on Pexels and download it.
        
        Args:
            query: Search term (e.g. "traffic", "money")
            orientation: 'portrait', 'landscape', or 'square'
            size: 'large', 'medium', or 'small'
            duration_min: Minimum duration in seconds to accept
            
        Returns:
            Path to downloaded video file, or None if failed.
        """
        if not self.api_key:
            log.warning("PEXELS_API_KEY not found. Returning mock video for testing.")
            return self._get_mock_video()
            
        headers = {
            "Authorization": self.api_key
        }
        
        params = {
            "query": query,
            "per_page": 5,
            "orientation": orientation,
            "size": size
        }
        
        try:
            log.info(f"Searching Pexels for: '{query}' ({orientation})")
            response = requests.get(self.search_url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                log.error(f"Pexels API Error: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            videos = data.get("videos", [])
            
            if not videos:
                log.warning(f"No videos found for query: '{query}'")
                return None
                
            # Filter and select best video
            selected_video = None
            for video in videos:
                if video["duration"] >= duration_min:
                    selected_video = video
                    break
            
            if not selected_video:
                # Fallback to first if none meet duration (unlikely)
                selected_video = videos[0]
                
            # Get video file URL (prefer HD)
            video_files = selected_video.get("video_files", [])
            # Sort by width/quality. For portrait 9:16, we want ~1080x1920
            # Pexels usually gives 'link' in video_files.
            
            download_url = None
            # Heuristic: pick the file closest to target resolution
            # For now, just pick the first HD one
            for vf in video_files:
                if vf.get("quality") == "hd" and (orientation == "landscape" or vf.get("height", 0) > vf.get("width", 0)):
                    download_url = vf.get("link")
                    break
            
            if not download_url and video_files:
                download_url = video_files[0].get("link")
                
            if download_url:
                return self._download_video(download_url, f"pexels_{selected_video['id']}")
                
        except Exception as e:
            log.error(f"Pexels Search Failed: {e}")
            
        return None

    def _download_video(self, url: str, file_prefix: str) -> Optional[Path]:
        """Download video content to temp dir."""
        try:
            filename = f"{file_prefix}.mp4"
            output_path = config.TEMP_DIR / filename
            
            if output_path.exists():
                return output_path
                
            log.info(f"Downloading stock video: {url}")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
            return output_path
            
        except Exception as e:
            log.error(f"Failed to download video: {e}")
            return None

    def _get_mock_video(self) -> Path:
        """Create or return a dummy stock video for testing without API key."""
        mock_path = config.TEMP_DIR / "mock_stock.mp4"
        if not mock_path.exists():
            # Create a simple green screen video using moviepy
            try:
                from moviepy import ColorClip, TextClip, CompositeVideoClip
                
                # Green background
                bg = ColorClip(size=(1080, 1920), color=(0, 100, 0), duration=5)
                
                # Text
                txt = TextClip(text="STOCK VIDEO\nPLACEHOLDER", font="Arial-Bold", font_size=100, color='white', text_align='center')
                txt = txt.with_position('center').with_duration(5)
                
                final = CompositeVideoClip([bg, txt])
                final.write_videofile(str(mock_path), fps=24, codec='libx264', verbose=False, logger=None)
                log.info(f"Created mock stock video: {mock_path}")
                
            except Exception as e:
                log.error(f"Failed to create mock video: {e}")
                # Create empty file as last resort to prevent crash
                mock_path.touch()
                
        return mock_path

# Global instance
client = PexelsClient()
search_stock_video = client.search_video
