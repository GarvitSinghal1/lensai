
import sys
import os
import shutil
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from video_creation.video import composer
from video_creation.media import tts_engine

def test_multilingual_anchor():
    print("Testing Multilingual + Anchor Flow...")
    
    # Setup temp dir
    temp_dir = Path("tools/media")
    temp_dir.mkdir(exist_ok=True)
    
    # Create dummy assets
    dummy_audio = temp_dir / "test_audio.wav"
    if not dummy_audio.exists():
        # Create silent audio clip to bypass TTS API limits
        import numpy as np
        from moviepy import AudioClip
        # Make frame must accept t (time array) if it's an AudioClip? 
        # Actually MoviePy 2 AudioClip takes make_frame(t) where t is float or array?
        # Safe bet: return array matching t shape
        def make_frame(t):
            # t is a numpy array of times
            return np.zeros((len(t), 2))
            
        audio = AudioClip(make_frame, duration=3, fps=44100)
        audio.write_audiofile(str(dummy_audio), fps=44100)
        print(f"✅ Created dummy audio: {dummy_audio}")
        
    dummy_image = temp_dir / "test_image.png"
    if not dummy_image.exists():
        # Blue square
        from PIL import Image
        img = Image.new('RGB', (1080, 1920), color = (73, 109, 137))
        img.save(dummy_image)
        
    dummy_anchor_video = temp_dir / "anchor_video.mp4"
    if not dummy_anchor_video.exists():
        # Create a simple video clip as "anchor"
        from moviepy import ColorClip
        clip = ColorClip(size=(1080, 1920), color=(0, 255, 0), duration=3)
        clip.write_videofile(str(dummy_anchor_video), fps=24)

    # 1. Define Scenes (English)
    scenes_en = [
        # Scene 1: Anchor (Video)
        {
            "text": "This is the anchor introducing the news.",
            "audio_path": str(dummy_audio),
            "video_path": str(dummy_anchor_video), # Explicit video
            "duration": 3,
            "is_anchor": True,
            "lang": "en"
        },
        # Scene 2: B-Roll (Image)
        {
            "text": "This is some b-roll footage.",
            "audio_path": str(dummy_audio),
            "image_path": str(dummy_image),
            "duration": 3,
            "lang": "en"
        }
    ]
    
    # 2. Compose English
    print("\n--- Composing English Video ---")
    output_en = "tools/output/test_anchor_en.mp4"
    Path("tools/output").mkdir(exist_ok=True)
    
    res = composer.compose_video(scenes_en, output_en)
    if res:
        print(f"✅ English Video: {res}")
    else:
        print("❌ English Composition Failed")

    # 3. Define Scenes (Hindi)
    # Hindi usually reuses visuals. 
    # For Anchor, we'd ideally have a Hindi lip-sync video.
    # But for this test, let's reuse the same video to ensure composer handles it.
    
    scenes_hi = [
        {
            "text": "यह समाचार एंकर है।", # Hindi text
            "audio_path": str(dummy_audio), # Reuse audio for test
            "video_path": str(dummy_anchor_video),
            "duration": 3,
            "is_anchor": True,
            "lang": "hi"
        },
        {
            "text": "यह बी-रोल फुटेज है।",
            "audio_path": str(dummy_audio),
            "image_path": str(dummy_image),
            "duration": 3,
            "lang": "hi"
        }
    ]
    
    print("\n--- Composing Hindi Video ---")
    output_hi = "tools/output/test_anchor_hi.mp4"
    res_hi = composer.compose_video(scenes_hi, output_hi)
    if res_hi:
        print(f"✅ Hindi Video: {res_hi}")
    else:
        print("❌ Hindi Composition Failed")

if __name__ == "__main__":
    test_multilingual_anchor()
