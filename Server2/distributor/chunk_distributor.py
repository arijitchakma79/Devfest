import base64
from typing import Dict
from agents.master_agent import MasterAgent

class ChunkDistributor:
    def __init__(self):
        self.current_chunk_id = 0
        self.master_agent = MasterAgent()
    
    async def process_chunk(self, chunk) -> Dict:
        """
        Process incoming chunk through the master agent
        """
        try:
            print("\n=== Distributor Processing Start ===")
            print(f"Received chunk ID: {chunk.chunk_id}")
            
            # Verify chunk sequence
            if chunk.chunk_id != self.current_chunk_id + 1:
                print(f"Warning: Received chunk {chunk.chunk_id}, expected {self.current_chunk_id + 1}")
            
            self.current_chunk_id = chunk.chunk_id
            
            # Decode base64 data
            print("Decoding data...")
            video_bytes = base64.b64decode(chunk.video_data)
            audio_bytes = base64.b64decode(chunk.audio_data)
            
            # Process with master agent
            print("Sending to master agent...")
            results = await self.master_agent.process_chunk(
                chunk_id=chunk.chunk_id,
                video_data=video_bytes,
                audio_data=audio_bytes
            )
            
            print("=== Distributor Processing Complete ===\n")
            return results
            
        except Exception as e:
            print(f"ERROR in Distributor: {str(e)}")
            raise e