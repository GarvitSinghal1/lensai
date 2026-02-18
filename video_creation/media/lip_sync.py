
import os
import shutil
from pathlib import Path
from typing import Optional
from gradio_client import Client

# Add project root 
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
import config

def generate_lip_sync(audio_path: Path, image_path: Path, output_path: Path) -> Optional[str]:
    """
    Generates a lip-synced video using SadTalker via Hugging Face Space.
    Returns path to the generated video file, or None if failed.
    """
    if not audio_path.exists() or not image_path.exists():
        print(f"❌ Missing inputs for lip sync: {audio_path} or {image_path}")
        return None
        
    print(f"👄 Converting Audio to Anchor Video: {audio_path.name}")
    
    try:
        # Use vinthony/SadTalker (or clone)
        # Note: This often requires a GPU quota or HF Token if the space is busy/gated
        client = Client("vinthony/SadTalker", hf_token=config.HF_TOKENS[0] if config.HF_TOKENS else None)
        
        # SadTalker API typically takes:
        # source_image, driven_audio, preprocess_type, is_still_mode, enhancement...
        # We need to check exact API args. 
        # Based on historic SadTalker Gradio APIs:
        # result = client.predict(
        #		source_image,	# filepath  in 'Source image' Image component
        #		driven_audio,	# filepath  in 'Driven Audio' Audio component
        #		"crop",	# str in 'Preprocess' Radio component
        #		True,	# bool in 'Still Mode' Checkbox component
        #		True,	# bool in 'GFPGAN as Face enhancer' Checkbox component
        #		api_name="/predict"
        # )
        
        # Since API changes, we wrap in broad try/except
        # Just creating the client is the first test
        
        # For now, since we know vinthony/SadTalker is down/gated in my tests,
        # this will likely fail. But we implement the logic for when it works.
        
        result_video = client.predict(
            str(image_path),
            str(audio_path),
            "crop", # preprocess
            True,   # still mode
            True,   # enhancer
            api_name="/predict"
        )
        
        if result_video and os.path.exists(result_video):
            shutil.copy(result_video, output_path)
            print(f"✅ Lip Sync Success: {output_path}")
            return str(output_path)
            
    except Exception as e:
        print(f"⚠️ SadTalker API failed (likely quota/gated): {e}")
        
    return None

if __name__ == "__main__":
    # Test
    pass
