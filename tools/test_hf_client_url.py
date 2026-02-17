
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from utils import hf_client

def test_url_construction():
    print("Testing HF Client URL Construction for Tencent Hunyuan...")
    
    # Force config model (in case user changes it later)
    config.IMAGE_MODEL = "tencent/HunyuanImage-3.0"
    
    with patch("requests.post") as mock_post:
        # Mock successful response so code doesn't retry
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake_image_bytes"
        mock_post.return_value = mock_resp
        
        # Call generate_image
        hf_client.generate_image("A futuristic city")
        
        # Verify URL
        found = False
        for call in mock_post.call_args_list:
            url = call[0][0]
            print(f"Called URL: {url}")
            if "router.huggingface.co/replicate/v1/models/tencent/HunyuanImage-3.0" in url:
                found = True
                break
        
        if found:
            print("SUCCESS: Correctly routed to Replicate endpoint for Hunyuan.")
        else:
            print("FAILURE: Did not route to expected URL.")
            print(f"Expected: .../replicate/v1/models/tencent/HunyuanImage-3.0/predictions")

if __name__ == "__main__":
    test_url_construction()
