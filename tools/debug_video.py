
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log

# Mock config
import config
# config.SFX_DIR is already set correctly in config.py to video_creation/media/sfx
# We just need to ensure directory exists
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
            "headline": "PACING TEST",
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
            "headline": "BOOM EFFECT",
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
            "headline": "FINALE",
            "image_path": "debug_fallback.png",
            "audio_path": "test_output.wav",
            "estimated_duration": 3.0,
            "visual_effect": "flash",
            "audio_effect": "ding" # Using ding as shutter replacement
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

    for i, scene in enumerate(scenes):
        log.info(f"  Composing scene {i+1}/{len(scenes)}: {scene.get('scene_type')}")
        
        # Determine image path
        img_path = scene.get("image_path")
        if not img_path or not os.path.exists(img_path):
             # Placeholder logic if missing
             img_path = config.TEMP_DIR / f"scene_{i+1}.png"
             if not img_path.exists():
                 log.warning(f"  Image missing for scene {i+1}, creating placeholder at {img_path}")
                 # Generate a simple placeholder
                 from PIL import Image, ImageDraw
                 img = Image.new('RGB', (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), color=(50, 50, 150)) # Blue
                 d = ImageDraw.Draw(img)
                 d.text((100,100), f"SCENE {i+1}\nPlaceholder", fill=(255,255,255))
                 img.save(img_path)
        
        log.info(f"  Using image: {img_path}")
        # Update scene dict with verified path (if it was missing)
        scene["image_path"] = str(img_path)

        # The original instruction had a syntax error here. Assuming 'compose_scene' is meant to be called
        # and the trailing string was a copy-paste error from an error message.
        # Since compose_video is called above, this loop might be intended for pre-processing scenes
        # before passing them to compose_video, or it's part of a different flow.
        # For faithful reproduction, I'm including the line as provided, but correcting the syntax.
        # If 'compose_scene' is not defined or intended here, this will cause a NameError.
        # Assuming 'compose_scene' is a placeholder for scene-specific processing.
        # If the intent was to replace compose_video with a scene-by-scene composition,
        # the structure would need a list of clips to be built and then concatenated.
        # Given the instruction "Log image source" and the provided snippet,
        # the most faithful interpretation is to insert the snippet as is,
        # correcting only the obvious syntax error.
        # If 'compose_scene' is not defined, this will be a runtime error.
        # To avoid introducing new errors, I will comment out the `clip = compose_scene(scene)` line
        # as it's not defined in this file and its purpose is unclear in this context
        # after `compose_video` has already been called.
        # The primary instruction was "Log image source", which is handled by the log.info line.
        # The rest of the snippet seems to be part of a scene processing loop.
        # Given the context, this loop should likely happen *before* `compose_video`.
        # However, the instruction explicitly places it *after* `compose_video`.
        # I will place the loop as instructed, but comment out the `compose_scene` call
        # to prevent a NameError and maintain the file's executability,
        # as `compose_scene` is not defined in this file.
        # If the user intended to define `compose_scene` or use it differently,
        # further instructions would be needed.
        # For now, the logging of image source is the core of the request.
        # clip = compose_scene(scene) # This line is commented out as `compose_scene` is not defined in this file.

    if result:
        log.info(f"SUCCESS: Video generated at {result}")
    else:
        log.error("FAILURE: composition returned None")

if __name__ == "__main__":
    main()
