
import os
import sys
from pathlib import Path
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Ensure project root is in path
sys.path.append(os.getcwd())

import config
from media import tts_engine

def test_tts():
    print(f"Testing TTS Model: {config.TTS_MODEL}")
    text = "This is a test of the Kokoro Text to Speech engine via Replicate provider."
    output_path = Path("media/test_tts.wav")
    
    # Clean previous test
    if output_path.exists():
        output_path.unlink()
        
    result = tts_engine.generate_tts(text, output_path)
    
    if result:
        print(f"✅ Success! Audio saved to {result['audio_path']}")
        print(f"Duration: {result['duration_seconds']:.2f}s")
    else:
        print("❌ TTS Generation Failed")

if __name__ == "__main__":
    test_tts()
