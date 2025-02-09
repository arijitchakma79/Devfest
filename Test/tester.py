import asyncio
import aiohttp
import base64
import os
import time
from typing import Dict
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StreamTester:
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.chunk_id = 0
        
    def prepare_chunk(self, video_path: str) -> Dict:
        """Prepare a chunk from video file with dummy audio."""
        try:
            # Read video file
            with open(video_path, 'rb') as f:
                video_data = f.read()
                
            # Create dummy audio data (1KB of silence)
            audio_data = bytes([0] * 1024)
                
            self.chunk_id += 1
            
            return {
                "timestamp": time.time(),
                "video_data": base64.b64encode(video_data).decode('utf-8'),
                "audio_data": base64.b64encode(audio_data).decode('utf-8'),
                "chunk_id": self.chunk_id
            }
        except Exception as e:
            logger.error(f"Error preparing chunk: {e}")
            raise

    async def send_chunk(self, session: aiohttp.ClientSession, chunk: Dict) -> Dict:
        """Send a chunk to the server."""
        try:
            async with session.post(
                f"{self.server_url}/receive_chunk/",
                json=chunk
            ) as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Error sending chunk: {e}")
            raise

    async def get_stream_status(self, session: aiohttp.ClientSession) -> Dict:
        """Get the current stream status (latest analysis)."""
        try:
            async with session.get(f"{self.server_url}/stream_status/") as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Error getting stream status: {e}")
            raise

async def run_stream_test():
    """Run a complete streaming test."""
    tester = StreamTester()
    
    # Test directory
    test_dir = Path("test_data/video")
    
    # Get list of test files
    image_files = sorted([f for f in test_dir.glob("*.jpg")])
    
    if not image_files:
        logger.error(f"No jpg files found in {test_dir}")
        return
    
    logger.info(f"Found {len(image_files)} image files to process")
    
    async with aiohttp.ClientSession() as session:
        for i, image_path in enumerate(image_files):
            try:
                # Prepare chunk
                logger.info(f"\nProcessing image {i+1}/{len(image_files)}: {image_path.name}")
                chunk = tester.prepare_chunk(str(image_path))
                
                # Send chunk
                results = await tester.send_chunk(session, chunk)
                logger.info(f"Results for {image_path.name}:")
                logger.info(json.dumps(results, indent=2))
                
                # Get stream status every 3 images
                if (i + 1) % 3 == 0:
                    status = await tester.get_stream_status(session)
                    logger.info("\nStream Status:")
                    logger.info(json.dumps(status, indent=2))
                
                # Wait a short time between chunks to avoid overwhelming the server
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing {image_path.name}: {e}")
                continue

async def main():
    """Main test function."""
    try:
        logger.info("Starting Stream Test")
        await run_stream_test()
        logger.info("Stream Test Complete")
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())