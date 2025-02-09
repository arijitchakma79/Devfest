from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from distributor.chunk_distributor import ChunkDistributor
import json
from datetime import datetime

class ChunkData(BaseModel):
    timestamp: float
    video_data: str  # base64 encoded video frame
    audio_data: str  # base64 encoded audio segment
    chunk_id: int

app = FastAPI()
distributor = ChunkDistributor()

@app.post("/receive_chunk/")
async def receive_chunk(chunk: ChunkData):
    """Process a single chunk from the stream"""
    try:
        results = await distributor.process_chunk(chunk)
        return {
            "status": "success",
            "chunk_id": chunk.chunk_id,
            "results": results
        }
    except Exception as e:
        print(f"Error in API: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing chunk: {str(e)}")

@app.get("/stream_status/")
async def get_stream_status():
    """Get current stream status and trends"""
    try:
        status = distributor.master_agent.get_stream_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stream status: {str(e)}")

@app.get("/current_trends/")
async def get_current_trends():
    """Get current situation trends"""
    try:
        trends = distributor.master_agent.stream_analysis.get_current_trends()
        return trends
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting trends: {str(e)}")

@app.get("/health")
async def health_check():
    """Check server health and stream status"""
    stream_status = distributor.master_agent.get_stream_status()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "stream_health": stream_status["stream_health"],
        "last_chunk_received": stream_status["last_chunk_id"],
        "time_since_last_chunk": stream_status["time_since_last_chunk"]
    }

@app.get("/")
async def root():
    return {
        "message": "Search and Rescue Analysis Server",
        "version": "1.0",
        "endpoints": {
            "/receive_chunk": "Process single chunk from stream",
            "/stream_status": "Get current stream status",
            "/current_trends": "Get current situation trends",
            "/health": "Server health check"
        }
    }