
import sys
import os
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from video_creation.media import tts_engine
from utils.logger import log

def test_groq_tts():
    print("Testing Groq TTS Integration...")
    
    output_path = Path("tools/output/test_groq.wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    text = "Hello, this is a test of the Groq text to speech engine. It should be fast and high quality."
    
    print(f"Generating TTS for: '{text}'")
    
    # Test strict Groq generation (bypassing fallback logic in generate_tts for specific test)
    # But let's test the main function to ensure priority is correct
    
    result = tts_engine.generate_tts(text, output_path)
    
    if result:
        print(f"✅ TTS Generated: {result['audio_path']}")
        print(f"   Duration: {result['duration_seconds']:.2f}s")
        
        # Verify it's not empty
        if result['duration_seconds'] < 0.5:
            print("❌ Audio seems too short!")
        else:
            print("✅ Duration looks valid.")
            
    else:
        print("❌ TTS Generation Failed")

if __name__ == "__main__":
    test_groq_tts()
