import base64
from typing import Tuple

class ChunkDistributor:
    def __init__(self):
        self.current_chunk_id = 0
        
    async def process_chunk(self, chunk) -> Tuple[dict, bytes]:
        """
        Process incoming chunk and separate into video and audio components
        Returns tuple of (vision_results, audio_bytes)
        """
        try:
            print("\n=== Distributor Processing Start ===")
            print(f"Received chunk ID: {chunk.chunk_id}")
            
            # Verify chunk sequence
            if chunk.chunk_id != self.current_chunk_id + 1:
                print(f"Warning: Received chunk {chunk.chunk_id}, expected {self.current_chunk_id + 1}")
            
            self.current_chunk_id = chunk.chunk_id
            
            # Decode base64 data
            print("Decoding video data...")
            video_bytes = base64.b64decode(chunk.video_data)
            print(f"Video size: {len(video_bytes)} bytes")
            
            print("Decoding audio data...")
            audio_bytes = base64.b64decode(chunk.audio_data)
            print(f"Audio size: {len(audio_bytes)} bytes")
            
            # Process with vision agent
            print("Sending to vision agent...")
            vision_results = await self.vision_agent.process_chunk(video_bytes)
            print("Vision processing complete")
            
            print("=== Distributor Processing Complete ===\n")
            return vision_results, audio_bytes
            
        except Exception as e:
            print(f"ERROR in Distributor: {str(e)}")
            raise e
            
    # Placeholder methods for sending to agents
    def send_to_vision_agent(self, video_bytes: bytes):
        """Send video data to vision agent"""
        pass
        
    def send_to_audio_agent(self, audio_bytes: bytes):
        """Send audio data to audio agent"""
        pass