from utils.hf_client import generate_audio
import config
import logging
import sys
import os

# Create logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("test_tts")

print(f"Testing TTS Generation...")
print(f"Model: {config.TTS_MODEL}")
print(f"Fallback: {config.TTS_FALLBACK}")

try:
    print("\nAttempting audio generation...")
    text = "This is a test of the emergency broadcast system."
    audio_bytes = generate_audio(text)
    
    if audio_bytes and len(audio_bytes) > 1000:
        print(f"\n✅ Success! Generated {len(audio_bytes)} bytes of audio.")
        with open("test_output.wav", "wb") as f:
            f.write(audio_bytes)
        print("Saved to test_output.wav")
    else:
        print("\n❌ Failed: No audio generated.")
except Exception as e:
    print(f"\n❌ Exception: {e}")
