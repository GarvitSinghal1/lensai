
import sys
import os
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from utils.stock_footage import search_stock_video
from utils.logger import log

def test_stock_integration():
    print("Testing Stock Video Integration...")
    
    # Check if API Key is present
    if config.PEXELS_API_KEY:
        print(f"PEXELS_API_KEY found: {config.PEXELS_API_KEY[:4]}...")
    else:
        print("⚠️ No PEXELS_API_KEY found. Expecting mock video.")
    
    # Test Query
    query = "traffic"
    print(f"\nSearching for: '{query}' (portrait)...")
    
    video_path = search_stock_video(query, orientation="portrait")
    
    if video_path:
        print(f"✅ Video found at: {video_path}")
        print(f"   Size: {os.path.getsize(video_path) / 1024:.1f} KB")
        
        # Verify it's a valid file
        if video_path.name == "mock_stock.mp4":
            print("   (Note: This is the MOCK video)")
        else:
            print("   (Note: This looks like a REAL download)")
    else:
        print("❌ Failed to get video.")

if __name__ == "__main__":
    test_stock_integration()
