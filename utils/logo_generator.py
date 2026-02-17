
from PIL import Image, ImageDraw, ImageFont
import os

def create_logo(output_path="media/logo.png"):
    # Create high-res transparent image
    W, H = 640, 220
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw Red RoundRec for "LENS"
    # Left side red box - Widen to 260
    draw.rounded_rectangle([10, 10, 270, 210], radius=40, fill="#cc0000")
    
    # Draw White "LENS" inside red box
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 90)
    except:
        font = ImageFont.load_default()
        
    draw.text((140, 110), "LENS", fill="white", font=font, anchor="mm")
    
    # Draw Black text "AI" next to it
    # We need a font for AI
    try:
        font_ai = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 90) 
    except:
        font_ai = font
        
    # Draw "AI" in white with black outline or just black?
    # Let's do a black box style for AI, adjoining the red box.
    
    draw.rounded_rectangle([280, 10, 480, 210], radius=40, fill="black")
    draw.text((380, 110), "AI", fill="white", font=font_ai, anchor="mm")

    # Resize to target size for consistency if needed, but high res is good.
    img.save(output_path)
    print(f"Logo saved to {output_path}")

if __name__ == "__main__":
    os.makedirs("media", exist_ok=True)
    create_logo()
