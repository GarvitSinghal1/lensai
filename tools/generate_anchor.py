
import sys
import os
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils import hf_client
import config

def generate_anchor():
    print("Generating AI News Anchor Avatar...")
    
    # Prompt for a professional anchor
    # Front-facing is crucial for Wav2Lip/LivePortrait
    prompt = (
        "Professional news anchor, diverse background, friendly but authoritative, "
        "sitting at a modern news desk, facing camera directly, looking at viewer, "
        "television studio lighting, 8k, photorealistic, high detail, sharp focus, "
        "neutral expression, mouth closed"
    )
    
    output_path = config.MEDIA_DIR / "anchor.png"
    config.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Prompt: {prompt}")
    print(f"Model: {config.IMAGE_MODEL}")
    
    try:
        # Use existing generation logic
        # We need raw bytes
        # We can use hf_client.generate_image which handles key rotation
        
        img_bytes = hf_client.generate_image(prompt)
        
        if img_bytes:
            with open(output_path, "wb") as f:
                f.write(img_bytes)
            print(f"✅ Anchor generated: {output_path}")
        else:
            print("❌ Failed to generate anchor image.")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    generate_anchor()
