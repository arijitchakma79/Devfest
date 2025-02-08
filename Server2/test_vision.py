import asyncio
from agents.vision_agent import VisionAgent
import os

async def test_vision():
    print("Starting Vision Agent Test")
    
    # Initialize vision agent
    agent = VisionAgent()
    
    # Test with a direct image file
    image_path = "./src/test2.jpg"
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found!")
        return
        
    print(f"\nTesting with image: {image_path}")
    
    # Process the image
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
            
        results = await agent.process_chunk(image_bytes)
        
        print("\nResults:")
        print(f"Total humans detected: {results.get('total_human_count', 0)}")
        print("\nKey details:")
        for detail in results.get('key_details', []):
            print(f"- {detail}")
            
        print("\nDescription:")
        print(results.get('description', 'No description available'))
        
    except Exception as e:
        print(f"Error during testing: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_vision())