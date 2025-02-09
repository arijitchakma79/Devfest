import asyncio
import aiohttp
import base64
import os
import time
from typing import Dict
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StreamTester:
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.chunk_id = 0
        
    def prepare_chunk(self, video_path: str, audio_path: str) -> Dict:
        """Prepare a chunk from video and audio files"""
        try:
            # Read files
            with open(video_path, 'rb') as f:
                video_data = f.read()
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
                
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
        """Send a chunk to the server"""
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
        """Get current stream status"""
        try:
            async with session.get(f"{self.server_url}/stream_status/") as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Error getting stream status: {e}")
            raise

    async def get_current_trends(self, session: aiohttp.ClientSession) -> Dict:
        """Get current trends"""
        try:
            async with session.get(f"{self.server_url}/current_trends/") as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Error getting trends: {e}")
            raise

async def run_stream_test():
    """Run a complete streaming test"""
    tester = StreamTester()
    
    # Test directories
    test_dir = "test_data"
    video_dir = os.path.join(test_dir, "video")
    audio_dir = os.path.join(test_dir, "audio")
    
    # Create directories if they don't exist
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    
    # Get list of test files
    video_files = sorted([f for f in os.listdir(video_dir) if f.endswith(('.jpg', '.png'))])
    audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith('.wav')])
    
    if not video_files or not audio_files:
        logger.error(f"Please add test files to:\n{video_dir} (images)\n{audio_dir} (audio)")
        return
    
    logger.info(f"Found {len(video_files)} video files and {len(audio_files)} audio files")
    
    async with aiohttp.ClientSession() as session:
        # Send chunks with 1-second intervals
        for i in range(min(len(video_files), len(audio_files))):
            try:
                # Prepare chunk
                video_path = os.path.join(video_dir, video_files[i])
                audio_path = os.path.join(audio_dir, audio_files[i])
                chunk = tester.prepare_chunk(video_path, audio_path)
                
                # Send chunk
                logger.info(f"\nSending chunk {i+1}")
                results = await tester.send_chunk(session, chunk)
                logger.info(f"Chunk {i+1} Results:")
                logger.info(json.dumps(results, indent=2))
                
                # Get status and trends every 3 chunks
                if (i + 1) % 3 == 0:
                    status = await tester.get_stream_status(session)
                    trends = await tester.get_current_trends(session)
                    
                    logger.info("\nStream Status:")
                    logger.info(json.dumps(status, indent=2))
                    logger.info("\nCurrent Trends:")
                    logger.info(json.dumps(trends, indent=2))
                
                # Wait 1 second between chunks
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in test loop: {e}")
                continue

async def main():
    """Main test function"""
    try:
        logger.info("Starting Stream Test")
        await run_stream_test()
        logger.info("Stream Test Complete")
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())