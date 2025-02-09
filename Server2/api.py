from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import time
from distributor.chunk_distributor import ChunkDistributor
import base64
import json
import logging

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
    """Root endpoint"""
    return {
        "message": "Search and Rescue Analysis API",
        "version": "1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.post("/receive_chunk/")
async def receive_chunk(chunk: ChunkData):
    """Process incoming data chunk"""
    try:
        logger.info(f"Received chunk {chunk.chunk_id}")
        
        # Process through distributor
        results = await distributor.process_chunk(chunk)
        
        # Log summary of results
        logger.info(f"Processed chunk {chunk.chunk_id}: " 
                   f"{results.get('current_analysis', {}).get('humans_detected', 0)} humans detected")
        
        return {
            "status": "success",
            "chunk_id": chunk.chunk_id,
            "timestamp": time.time(),
            "results": results,
            "current_analysis": {
                "image_data": chunk.video_data,  # Original image
                "humans_detected": results.get("current_analysis", {}).get("humans_detected", 0),
                "safety_status": results.get("current_analysis", {}).get("safety_status", "UNKNOWN"),
                "danger_level": results.get("current_analysis", {}).get("danger_level", "low"),
                "sector": results.get("current_analysis", {}).get("sector", "A1"),
                "confidence": results.get("current_analysis", {}).get("confidence", 0.0),
                "key_observations": results.get("current_analysis", {}).get("key_observations", []),
                "ai_analysis": results.get("current_analysis", {}).get("ai_situation_analysis", "")
            }
        }
    except Exception as e:
        logger.error(f"Error processing chunk: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing chunk: {str(e)}")

@app.get("/stream_status/")
async def get_stream_status():
    """Get current stream status and analysis"""
    try:
        status = distributor.master_agent.get_stream_status()
        logger.info("Stream status requested")
        
        return {
            "status": "success",
            "timestamp": time.time(),
            "stream_status": status,
            "current_analysis": {
                "humans_detected": status.get("trends", {})
                    .get("current_situation", {})
                    .get("humans_present", 0),
                "danger_level": status.get("trends", {})
                    .get("current_situation", {})
                    .get("danger_level", "low"),
                "observations": status.get("trends", {})
                    .get("current_situation", {})
                    .get("latest_observations", [])
            }
        }
    except Exception as e:
        logger.error(f"Error getting stream status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stream status: {str(e)}")

@app.get("/current_trends/")
async def get_current_trends():
    """Get current situation trends"""
    try:
        trends = distributor.master_agent.stream_analysis.get_current_trends()
        logger.info("Trends requested")
        
        return {
            "status": "success",
            "timestamp": time.time(),
            "trends": trends
        }
    except Exception as e:
        logger.error(f"Error getting trends: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting trends: {str(e)}")

@app.get("/latest_images/{count}")
async def get_latest_images(count: int = 3):
    """Get latest processed images"""
    try:
        if count < 1:
            raise HTTPException(status_code=400, detail="Count must be positive")
            
        # Get last N images from master agent's history
        latest = []
        situations = distributor.master_agent.stream_analysis.recent_situations
        
        for situation in list(situations)[-count:]:
            latest.append({
                "timestamp": situation.timestamp,
                "image_data": situation.image_data,
                "humans_detected": situation.humans_detected,
                "safety_status": situation.safety_status,
                "sector": situation.sector
            })
        
        return {
            "status": "success",
            "count": len(latest),
            "images": latest
        }
    except Exception as e:
        logger.error(f"Error getting latest images: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting images: {str(e)}")

@app.get("/system_stats")
async def get_system_stats():
    """Get system statistics"""
    try:
        return {
            "status": "success",
            "timestamp": time.time(),
            "stats": {
                "vision": distributor.master_agent.vision_agent.get_stats(),
                "audio": distributor.master_agent.audio_agent.get_stats(),
                "stream": distributor.master_agent.get_stream_status()
            }
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@app.get("/debug_info")
async def get_debug_info():
    """Get debug information (for development)"""
    if app.debug:
        return {
            "distributor_status": {
                "current_chunk_id": distributor.current_chunk_id,
                "master_agent": {
                    "last_chunk_id": distributor.master_agent.last_chunk_id,
                    "last_chunk_time": distributor.master_agent.last_chunk_time
                }
            }
        }
    return {"message": "Debug endpoint disabled in production"}