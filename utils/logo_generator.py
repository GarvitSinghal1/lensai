
from PIL import Image, ImageDraw, ImageFont
import os

def create_logo(output_path="media/logo.png"):
    # Create high-res transparent image
    W, H = 500, 500
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw Red Box for "LENS"
    draw.rectangle([50, 150, 450, 350], fill="#cc0000")
    
    # Draw Text
    try:
        # Try to find a bold font
        font = ImageFont.truetype("Arial", 120)
    except:
        font = ImageFont.load_default()
        
    # "LENS" in white inside box
    draw.text((250, 250), "LENS", fill="white", font=font, anchor="mm")
    
    # "AI" in black below or next? Let's do a "LIVE" badge style
    # Actually, let's make it look like "BBC" or "CNN" style
    # Red square with "LIVE"
    
    img = Image.new("RGBA", (300, 150), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    
    # Red background
    draw.rounded_rectangle([0, 0, 300, 150], radius=20, fill="#cc0000")
    
    # TEXT
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
    except:
        font = ImageFont.load_default()
        
    draw.text((150, 75), "LENS AI", fill="white", font=font, anchor="mm")
    
    img.save(output_path)
    print(f"Logo saved to {output_path}")

if __name__ == "__main__":
    os.makedirs("media", exist_ok=True)
    create_logo()
