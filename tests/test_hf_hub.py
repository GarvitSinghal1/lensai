
import sys
import os
from huggingface_hub import InferenceClient

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config

def test_hub_client():
    print("Testing huggingface_hub.InferenceClient...")
    
    # Get token
    token = os.getenv("HF_TOKEN") or (config.HF_TOKENS[0] if config.HF_TOKENS else None)
    
    if not token:
        print("❌ No token found")
        return

    print(f"Using token: {token[:5]}...")
    
    # helper to dry run
    client = InferenceClient(token=token)
    
    model = config.IMAGE_MODEL # runwayml/stable-diffusion-v1-5
    prompt = "A futuristic city"
    
    print(f"Testing Model: {model}")
    
    try:
        # text_to_image returns PIL Image
        image = client.text_to_image(prompt, model=model)
        output_path = "tools/test_hub_gen.png"
        image.save(output_path)
        print(f"✅ Success! Saved to {output_path}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    test_hub_client()
