
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from video_creation.media import image_generator
from utils.logger import log

def test_priority():
    print("Testing Image Priority Logic...")
    
    # Mock data
    scenes = [
        {"narration": "Scene 1", "image_prompt": "Prompt 1"},
        {"narration": "Scene 2", "image_prompt": "Prompt 2"},
        {"narration": "Scene 3", "image_prompt": "Prompt 3"},
        {"narration": "Scene 4", "image_prompt": "Prompt 4"},
    ]
    
    article_images = ["http://img1.jpg", "http://img2.jpg"]
    temp_dir = Path("test_temp")
    
    # Mock dependencies
    with patch("video_creation.media.image_generator._download_and_process_image") as mock_dl, \
         patch("video_creation.media.image_generator.generate_image") as mock_gen, \
         patch("video_creation.media.image_generator._generate_solid_fallback") as mock_fallback, \
         patch("pathlib.Path.mkdir"):
             
        # Setup mocks
        mock_dl.side_effect = lambda url, path: True # Always succeed download
        mock_gen.side_effect = lambda prompt, path: str(path) # Always succeed gen
        
        # Run function
        print(f"Input: {len(scenes)} scenes, {len(article_images)} scraped images")
        result = image_generator.generate_images_for_scenes(scenes, temp_dir, article_images)
        
        # Verify
        print("\nResults:")
        for i, scene in enumerate(result):
            print(f"Scene {i+1} image: {scene.get('image_path')}")
            
        # Assertions
        # Scene 1 & 2 should use scraped images
        # Scene 3 & 4 should use AI generation
        
        assert mock_dl.call_count == 2, f"Expected 2 downloads, got {mock_dl.call_count}"
        assert mock_gen.call_count == 2, f"Expected 2 AI generations, got {mock_gen.call_count}"
        
        # Verify call args
        args_dl = mock_dl.call_args_list
        print(f"\nDownload calls: {[a[0][0] for a in args_dl]}")
        if args_dl[0][0][0] == "http://img1.jpg" and args_dl[1][0][0] == "http://img2.jpg":
            print("SUCCESS: Used images in order.")
        else:
            print("FAILURE: Did not use images in correct order.")

        print("\nLogic Verification Complete.")

if __name__ == "__main__":
    test_priority()
