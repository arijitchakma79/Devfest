import base64
import time
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
from distributor.chunk_distributor import ChunkDistributor

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChunkData(BaseModel):
    timestamp: float
    video_data: str  # base64 encoded video frame
    audio_data: str  # base64 encoded audio segment
    chunk_id: int

app = FastAPI()
distributor = ChunkDistributor()

@app.get("/")
async def root():
    """Root endpoint for the Search & Rescue Analysis API."""
    return {
        "message": "Search and Rescue Analysis API",
        "version": "1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.post("/receive_chunk/")
async def receive_chunk(chunk: ChunkData):
    """
    Endpoint to process an incoming chunk.
    The API expects the video and audio data as base64-encoded strings.
    """
    try:
        logger.info(f"Received chunk {chunk.chunk_id}")
        
        # Convert the base64 strings to bytes
        video_bytes = base64.b64decode(chunk.video_data)
        audio_bytes = base64.b64decode(chunk.audio_data)
        
        # Process the chunk using the distributor (which delegates to MasterAgent)
        results = await distributor.process_chunk(chunk.chunk_id, video_bytes, audio_bytes)
        
        logger.info(f"Processed chunk {chunk.chunk_id}: " 
                    f"{results.get('current_analysis', {}).get('humans_detected', 0)} humans detected")
        
        return {
            "status": "success",
            "chunk_id": chunk.chunk_id,
            "timestamp": time.time(),
            "results": results,
            "current_analysis": {
                "image_path": results.get("current_analysis", {}).get("image_path", ""),
                "humans_detected": results.get("current_analysis", {}).get("humans_detected", 0),
                "safety_status": results.get("current_analysis", {}).get("safety_status", "UNKNOWN"),
                "danger_level": results.get("current_analysis", {}).get("danger_level", "low"),
                "sector": results.get("current_analysis", {}).get("sector", "A1"),
                "confidence": results.get("current_analysis", {}).get("confidence", 0.0),
                "key_observations": results.get("current_analysis", {}).get("key_observations", []),
                "ai_analysis": results.get("current_analysis", {}).get("ai_situation_analysis", ""),
                "scene_description": results.get("current_analysis", {}).get("scene_description", ""),
                "audio_transcription": results.get("current_analysis", {}).get("audio_transcription", "")
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing chunk: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing chunk: {str(e)}")

@app.get("/stream_status/")
async def get_stream_status():
    """
    Endpoint to retrieve the latest analysis.
    This returns the latest processed chunk's situational awareness, including the local image file path.
    """
    try:
        # Retrieve the latest analysis from the MasterAgent
        status = distributor.master_agent.get_latest_analysis()
        logger.info("Stream status requested")
        
        return {
            "status": "success",
            "timestamp": time.time(),
            "stream_status": status,
            "current_analysis": {
                "image_path": status.get("current_analysis", {}).get("image_path", ""),
                "humans_detected": status.get("current_analysis", {}).get("humans_detected", 0),
                "safety_status": status.get("current_analysis", {}).get("safety_status", "UNKNOWN"),
                "danger_level": status.get("current_analysis", {}).get("danger_level", "low"),
                "sector": status.get("current_analysis", {}).get("sector", "A1"),
                "confidence": status.get("current_analysis", {}).get("confidence", 0.0),
                "key_observations": status.get("current_analysis", {}).get("key_observations", []),
                "ai_analysis": status.get("current_analysis", {}).get("ai_situation_analysis", ""),
                "scene_description": status.get("current_analysis", {}).get("scene_description", ""),
                "audio_transcription": status.get("current_analysis", {}).get("audio_transcription", "")
            }
        }
    except Exception as e:
        logger.error(f"Error getting stream status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stream status: {str(e)}")

@app.get("/system_stats")
async def get_system_stats():
    """
    Endpoint to return processing statistics from the vision and audio agents.
    """
    try:
        return {
            "status": "success",
            "timestamp": time.time(),
            "stats": {
                "vision": distributor.master_agent.vision_agent.get_stats(),
                "audio": distributor.master_agent.audio_agent.get_stats(),
            }
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
