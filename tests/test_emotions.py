
import sys
import os
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from video_creation.media import tts_engine
from utils.logger import log

def test_emotional_tts():
    print("Testing Emotional TTS & Voice Varieties...")
    
    output_dir = Path("tools/output/emotions")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Test cases
    tags = ["<laugh>", "<chuckle>", "<sigh>"]
    # Test valid Groq voices
    voices = ["autumn", "diana", "daniel"] 
    
    base_text = "This is a test of the emotional capabilities."
    
    for voice in voices:
        # Update config temporarily
        original_voice = config.GROQ_TTS_VOICE
        config.GROQ_TTS_VOICE = voice
        
        print(f"\n--- Testing Voice: {voice} ---")
        
        # 1. Normal
        text_normal = f"Hello, I am {voice}. {base_text}"
        out_normal = output_dir / f"{voice}_normal.wav"
        print(f"Generating: {text_normal}")
        if tts_engine.generate_tts(text_normal, out_normal):
            print(f"✅ Generated {out_normal}")
            
        # 2. Emotional
        for tag in tags:
            text_emotion = f"I can't believe it {tag}. {base_text}"
            out_emotion = output_dir / f"{voice}_{tag.strip('<>')}.wav"
            print(f"Generating: {text_emotion}")
            if tts_engine.generate_tts(text_emotion, out_emotion):
                 print(f"✅ Generated {out_emotion}")
            else:
                 print(f"❌ Failed to generate {text_emotion}")

        # Restore
        config.GROQ_TTS_VOICE = original_voice

if __name__ == "__main__":
    test_emotional_tts()
