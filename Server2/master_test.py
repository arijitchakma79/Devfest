import asyncio
from agents.master_agent import MasterAgent
import os
import json
import time

async def test_master():
    print("Starting Master Agent Test")
    
    # Initialize master agent
    agent = MasterAgent()
    
    # Test directory paths
    test_dir = "test_data"
    video_dir = os.path.join(test_dir, "video")
    audio_dir = os.path.join(test_dir, "audio")
    
    # Create directories if they don't exist
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    
    # Get test files
    video_files = [f for f in os.listdir(video_dir) if f.endswith(('.jpg', '.png'))]
    audio_files = [f for f in os.listdir(audio_dir) if f.endswith('.wav')]
    
    if not video_files or not audio_files:
        print(f"Please add test files to:\n{video_dir} (images)\n{audio_dir} (audio)")
        return
    
    print(f"\nFound {len(video_files)} video files and {len(audio_files)} audio files")
    
    # Process chunks
    for i in range(min(len(video_files), len(audio_files))):
        print(f"\nProcessing Chunk {i+1}")
        
        # Read files
        with open(os.path.join(video_dir, video_files[i]), 'rb') as f:
            video_data = f.read()
        with open(os.path.join(audio_dir, audio_files[i]), 'rb') as f:
            audio_data = f.read()
            
        # Process through master agent
        try:
            results = await agent.process_chunk(i+1, video_data, audio_data)
            
            # Print results
            print("\nResults:")
            print(json.dumps(results, indent=2))
            
            # Get historical analysis after each chunk
            if i > 0:  # Only after first chunk
                history = agent.get_historical_analysis()
                print("\nHistorical Analysis:")
                print(json.dumps(history, indent=2))
            
            # Small delay between chunks
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error processing chunk {i+1}: {str(e)}")
    
    # Final historical analysis
    print("\nFinal Historical Analysis:")
    print(json.dumps(agent.get_historical_analysis(), indent=2))

if __name__ == "__main__":
    asyncio.run(test_master())