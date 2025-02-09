import base64
import logging
from agents.master_agent import MasterAgent

logger = logging.getLogger(__name__)

class ChunkDistributor:
    def __init__(self):
        self.current_chunk_id = 0
        self.master_agent = MasterAgent()

    async def process_chunk(self, chunk_id: int, video_data: bytes, audio_data: bytes) -> dict:
        """
        Process an incoming chunk by forwarding the chunk_id, video_data, and audio_data
        to the MasterAgent.
        """
        try:
            logger.info(f"\n=== Distributor Processing Chunk {chunk_id} ===")
            
            # Verify chunk sequence
            if chunk_id != self.current_chunk_id + 1:
                logger.warning(f"Warning: Received chunk {chunk_id}, expected {self.current_chunk_id + 1}")
            self.current_chunk_id = chunk_id

            # Process with MasterAgent
            logger.info("Sending to master agent...")
            results = await self.master_agent.process_chunk(
                chunk_id=chunk_id,
                video_data=video_data,
                audio_data=audio_data
            )
            
            logger.info("=== Distributor Processing Complete ===\n")
            return results

        except Exception as e:
            logger.error(f"ERROR in Distributor: {str(e)}")
            raise e
