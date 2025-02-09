import requests
import base64
from PIL import Image
import io
import time

def test_image_send():
    # 1. Load and prepare image
    try:
        # Load image
        image_path = "test.jpg"  # Put a test image in your directory
        with open(image_path, 'rb') as img_file:
            image_bytes = img_file.read()
            
        print(f"Original image size: {len(image_bytes)} bytes")
        
        # Convert to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        print(f"Base64 image size: {len(base64_image)} characters")
        
        # Create dummy audio
        dummy_audio = bytes([0] * 1000)
        base64_audio = base64.b64encode(dummy_audio).decode('utf-8')
        
        # 2. Prepare payload
        payload = {
            "timestamp": time.time(),
            "video_data": base64_image,
            "audio_data": base64_audio,
            "chunk_id": 1
        }
        
        # 3. Send to API
        print("\nSending to API...")
        response = requests.post(
            "http://localhost:8000/receive_chunk/",
            json=payload
        )
        
        # 4. Check response
        print(f"\nResponse status code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("\nAPI Response:")
            print(f"Status: {result.get('status')}")
            print(f"Chunk ID: {result.get('chunk_id')}")
            
            # 5. Verify image data in response
            analysis = result.get('current_analysis', {})
            if 'image_data' in analysis:
                print("\nVerifying returned image...")
                returned_image = base64.b64decode(analysis['image_data'])
                img = Image.open(io.BytesIO(returned_image))
                print(f"Successfully decoded returned image: {img.size}")
                
                # Save returned image for verification
                img.save('returned_image.jpg')
                print("Saved returned image as 'returned_image.jpg'")
            else:
                print("No image data in response!")
                
            # Print other analysis results
            print("\nAnalysis Results:")
            print(f"Humans Detected: {analysis.get('humans_detected')}")
            print(f"Safety Status: {analysis.get('safety_status')}")
            print(f"Sector: {analysis.get('sector')}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_image_send()