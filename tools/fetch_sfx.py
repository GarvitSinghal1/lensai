
import requests
import os
import subprocess
from pathlib import Path

# Direct URLs found via curl
MAPPING = {
    "whoosh.wav": "https://studionora.ca/Download/s-f-x/MP3/Woosh/Woosh-Deep-01.mp3",
    "ding.wav": "https://studionora.ca/Download/s-f-x/MP3/Alert/Alert-01.mp3",
    "boom.wav": "https://studionora.ca/Download/s-f-x/MP3/SciFi/SciFi-04.mp3", # Assuming 04 is punchy
    "glitch.wav": "https://studionora.ca/Download/s-f-x/MP3/SciFi/SciFi-01.mp3",
    "camera_shutter.wav": "https://studionora.ca/Download/s-f-x/MP3/Input/Input-01.mp3", # Click
    "news_background_pro.wav": "https://studionora.ca/Download/s-f-x/MP3/Music/Music-01.mp3"
}

SFX_DIR = Path("video_creation/media/sfx")
SFX_DIR.mkdir(parents=True, exist_ok=True)

def download_file(url, final_path):
    print(f"Downloading {url} to {final_path}...")
    try:
        r = requests.get(url, allow_redirects=True)
        if r.status_code != 200:
            print(f"  Failed: {r.status_code}")
            return
        
        # Save as temp mp3
        temp_mp3 = final_path.with_suffix(".mp3")
        with open(temp_mp3, "wb") as f:
            f.write(r.content)
            
        # Convert to wav
        cmd = ["ffmpeg", "-y", "-i", str(temp_mp3), str(final_path)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        if final_path.exists():
            print(f"  Success: {final_path} (Size: {final_path.stat().st_size} bytes)")
            # Clean up mp3
            if temp_mp3.exists():
                os.remove(temp_mp3)
        else:
            print("  Conversion failed.")
            
    except Exception as e:
        print(f"  Error: {e}")

def main():
    for name, url in MAPPING.items():
        final_path = SFX_DIR / name
        # Overwrite always to replace trash files
        download_file(url, final_path)

if __name__ == "__main__":
    main()
