import base64
from typing import Dict
from agents.master_agent import MasterAgent
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChunkDistributor:
    def __init__(self):
        self.current_chunk_id = 0
        self.master_agent = MasterAgent()
    
    async def process_chunk(self, chunk) -> Dict:
        """
        Process incoming chunk through the master agent
        """
        try:
            logger.info(f"\n=== Distributor Processing Chunk {chunk.chunk_id} ===")
            
            # Verify chunk sequence
            if chunk.chunk_id != self.current_chunk_id + 1:
                logger.warning(f"Warning: Received chunk {chunk.chunk_id}, expected {self.current_chunk_id + 1}")
            
            self.current_chunk_id = chunk.chunk_id
            
            # Decode base64 data
            logger.info("Decoding data...")
            video_bytes = base64.b64decode(chunk.video_data)
            audio_bytes = base64.b64decode(chunk.audio_data)
            
            # Process with master agent
            logger.info("Sending to master agent...")
            results = await self.master_agent.process_chunk(
                chunk_id=chunk.chunk_id,
                video_data=video_bytes,
                audio_data=audio_bytes
            )
            
            logger.info("=== Distributor Processing Complete ===\n")
            return results
            
        except Exception as e:
            logger.error(f"ERROR in Distributor: {str(e)}")
            raise e