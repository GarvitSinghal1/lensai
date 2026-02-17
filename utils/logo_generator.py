
from PIL import Image, ImageDraw, ImageFont
import os

def create_logo(output_path="media/logo.png"):
    # Create high-res transparent image
    W, H = 600, 200
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw Red RoundRec for "LENS"
    # Left side red box
    draw.rounded_rectangle([0, 0, 240, 200], radius=40, fill="#cc0000")
    
    # Draw White "LENS" inside red box
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 110)
    except:
        font = ImageFont.load_default()
        
    draw.text((120, 100), "LENS", fill="white", font=font, anchor="mm")
    
    # Draw Black text "AI" next to it
    # We need a font for AI
    try:
        font_ai = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 110) 
    except:
        font_ai = font
        
    # Draw "AI" in white with black outline or just black?
    # Let's do white text with black stroke for visibility on all backgrounds, 
    # OR just a black box?
    # Let's do a black box style for AI, adjoining the red box.
    
    draw.rounded_rectangle([250, 0, 450, 200], radius=40, fill="black")
    draw.text((350, 100), "AI", fill="white", font=font_ai, anchor="mm")

    # Resize to target size for consistency if needed, but high res is good.
    img.save(output_path)
    print(f"Logo saved to {output_path}")

if __name__ == "__main__":
    os.makedirs("media", exist_ok=True)
    create_logo()
