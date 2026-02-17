
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
import config
from video_creation.media.tts_engine import generate_tts

def main():
    log.info("Testing TTS Speed (1.5x)...")
    
    text = "This is a test of the new speed functionality. The voice should be faster now."
    out_path = Path("video_creation/media/test_speed.wav")
    audio_path = generate_tts(text, str(out_path))
    
    if audio_path and os.path.exists(audio_path):
        size = os.path.getsize(audio_path)
        log.info(f"Saved TTS to {audio_path} ({size} bytes)")
    else:
        log.error("TTS generation failed")

if __name__ == "__main__":
    main()
