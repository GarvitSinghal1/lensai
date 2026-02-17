
import requests
import re
import subprocess
from pathlib import Path
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config

URL = "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Impact_Moderato.ogg"
OUTPUT_WAV = config.SFX_DIR / "news_background_pro.wav"
TEMP_OGG = config.SFX_DIR / "temp_bgm.ogg"

def main():
    search_query = "Kevin MacLeod Impact Moderato"
    print(f"Searching Commons API for '{search_query}'...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    
    # 1. Search for file title
    api_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": search_query,
        "srnamespace": "6", # File namespace
        "format": "json"
    }
    
    try:
        r = requests.get(api_url, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()
        
        results = data.get("query", {}).get("search", [])
        if not results:
            print("No audio files found.")
            return

        # Pick first result
        file_title = results[0]["title"]
        print(f"Found file: {file_title}")
        
        # 2. Get download URL
        params_info = {
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json"
        }
        
        r_info = requests.get(api_url, params=params_info, headers=headers)
        data_info = r_info.json()
        
        pages = data_info.get("query", {}).get("pages", {})
        download_url = ""
        for page_id, page in pages.items():
            imageinfo = page.get("imageinfo", [])
            if imageinfo:
                download_url = imageinfo[0]["url"]
                break
        
        if not download_url:
            print("Could not retrieve download URL.")
            return

        print(f"Download URL: {download_url}")
        
        # 3. Download using CURL (more robust against 403)
        print("Downloading via curl...")
        cmd_curl = [
            "curl", "-L", "-A", headers["User-Agent"],
            "-o", str(TEMP_OGG), download_url
        ]
        subprocess.run(cmd_curl, check=True)
        
        if TEMP_OGG.exists() and TEMP_OGG.stat().st_size > 0:
             print(f"Downloaded to {TEMP_OGG}")
        else:
             print("Download failed.")
             return
        
        # 4. Convert
        print("Converting to WAV...")
        cmd = [
            "ffmpeg", "-y", "-i", str(TEMP_OGG),
            "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(OUTPUT_WAV)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if OUTPUT_WAV.exists():
            print(f"Success! BGM saved to {OUTPUT_WAV}")
            TEMP_OGG.unlink()
        else:
            print("Conversion failed.")

    except Exception as e:
        print(f"Error fetching BGM: {e}")

if __name__ == "__main__":
    config.SFX_DIR.mkdir(parents=True, exist_ok=True)
    main()
