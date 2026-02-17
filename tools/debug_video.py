
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log

# Mock config
import config
config.SFX_DIR = Path("../media/sfx")
config.SFX_DIR.mkdir(parents=True, exist_ok=True)

# Ensure dummy SFX exist if not already generated
def ensure_sfx():
    if not (config.SFX_DIR / "whoosh.wav").exists():
        import utils.sfx_generator
        utils.sfx_generator.main()

ensure_sfx()

from video_creation.video.composer import compose_video

def main():
    log.info("Starting debug_video.py for Effects & Pacing...")

    # Define test scenes
    scenes = [
        {
            "scene_number": 1,
            "scene_type": "hook",
            "narration": "This is a test of the fast pacing system. Whoosh!",
            "image_path": "debug_scene1.png", 
            "audio_path": "test_output.wav", # Using existing dummy audio
            "estimated_duration": 3.0,
            "visual_effect": "shake",
            "audio_effect": "whoosh"
        },
        {
            "scene_number": 2,
            "scene_type": "facts",
            "narration": "Here is a second rapid clip with a boom effect.",
            "image_path": "debug_scene2.png",
            "audio_path": "test_output.wav",
            "estimated_duration": 3.0,
            "visual_effect": "zoom_fast",
            "audio_effect": "boom"
        },
        {
            "scene_number": 3,
            "scene_type": "kicker",
            "narration": "And a final flash to end the video.",
            "image_path": "debug_fallback.png",
            "audio_path": "test_output.wav",
            "estimated_duration": 3.0,
            "visual_effect": "flash",
            "audio_effect": "ding"
        }
    ]

    # Ensure dummy images and audio exist
    if not os.path.exists("debug_scene1.png"):
        from PIL import Image
        Image.new('RGB', (1080, 1920), color = 'red').save('debug_scene1.png')
    if not os.path.exists("debug_scene2.png"):
        from PIL import Image
        Image.new('RGB', (1080, 1920), color = 'blue').save('debug_scene2.png')
    if not os.path.exists("debug_fallback.png"):
        from PIL import Image
        Image.new('RGB', (1080, 1920), color = 'green').save('debug_fallback.png')
    
    # Create dummy audio if missing
    if not os.path.exists("test_output.wav"):
        # We need a valid wav file for moviepy
        import wave, struct, math
        with wave.open("test_output.wav", 'w') as obj:
            obj.setnchannels(1)
            obj.setsampwidth(2)
            obj.setframerate(44100)
            for i in range(44100 * 3): # 3 seconds
                val = math.sin(2 * math.pi * 440 * i / 44100)
                obj.writeframesraw(struct.pack('<h', int(val * 32767 * 0.5)))

    output_file = "debug_effects_output.mp4"
    result = compose_video(scenes, output_file)

    if result:
        log.info(f"SUCCESS: Video generated at {result}")
    else:
        log.error("FAILURE: composition returned None")

if __name__ == "__main__":
    main()
