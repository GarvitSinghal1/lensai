
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from video_creation.media import image_generator
from utils import hf_client
import config

def test_search_logic():
    print("Testing Search vs AI Logic...")
    
    # 1. Test Entity Detection -> Search
    print("\nCase 1: Entity 'Bill Gates' -> Expect Search")
    with patch("utils.image_searcher.search_google_images") as mock_search, \
         patch("utils.hf_client.generate_image") as mock_ai:
        
        mock_search.return_value = "found_image.png"
        
        res = image_generator.generate_image("A photo of Bill Gates", "out.png")
        
        if mock_search.called:
            print("  ✅ Triggered Search")
            if not mock_ai.called:
                print("  ✅ Did NOT trigger AI (Correct)")
            else:
                print("  ❌ Triggered AI (Incorrect)")
        else:
            print("  ❌ Did NOT trigger Search")

    # 2. Test Generic -> AI
    print("\nCase 2: Generic 'A scared person' -> Expect AI")
    with patch("utils.image_searcher.search_google_images") as mock_search, \
         patch("utils.hf_client.generate_image") as mock_ai:
        
        mock_ai.return_value = b"bytes"
        
        res = image_generator.generate_image("A scared person", "out.png")
        
        if not mock_search.called:
            print("  ✅ Did NOT trigger Search")
            if mock_ai.called:
                print("  ✅ Triggered AI (Correct)")
        else:
            print("  ❌ Triggered Search (Incorrect)")

    # 3. Test Search Failure -> Fallback Sanitized AI
    print("\nCase 3: Entity 'Elon Musk' -> Search Fail -> Expect Sanitized AI")
    with patch("utils.image_searcher.search_google_images") as mock_search, \
         patch("utils.hf_client.generate_image") as mock_ai:
        
        mock_search.return_value = None # Search fails
        mock_ai.return_value = b"bytes"
        
        res = image_generator.generate_image("Elon Musk on Mars", "out.png")
        
        if mock_search.called:
            print("  ✅ Triggered Search (and failed)")
            if mock_ai.called:
                called_prompt = mock_ai.call_args[0][0]
                print(f"  AI Prompt: '{called_prompt}'")
                if "Elon Musk" not in called_prompt and "tech CEO" in called_prompt:
                     print("  ✅ Fallback to Sanitized AI (Correct)")
                else:
                     print("  ❌ Fallback Prompt NOT Sanitized!")
            else:
                print("  ❌ Did NOT trigger AI Fallback")
        else:
            print("  ❌ Did NOT trigger Search")

if __name__ == "__main__":
    test_search_logic()
