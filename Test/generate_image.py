from PIL import Image, ImageDraw, ImageFont
import numpy as np

def generate_test_image():
    # Create a new image with a white background
    img = Image.new('RGB', (640, 480), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw some shapes
    draw.rectangle([100, 100, 200, 300], fill='blue', outline='black')  # "person"
    draw.ellipse([150, 50, 200, 100], fill='pink', outline='black')    # "head"
    
    # Add text
    draw.text((250, 200), "Test Image", fill='black')
    draw.text((250, 220), "Person Detection", fill='black')
    
    # Save the image
    img.save('test.jpg', quality=95)
    print("Generated test image: test.jpg")

if __name__ == "__main__":
    generate_test_image()