from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from distributor.chunk_distributor import ChunkDistributor

class ChunkData(BaseModel):
    timestamp: float  # Unix timestamp
    video_data: str  # base64 encoded video frame
    audio_data: str  # base64 encoded audio segment
    chunk_id: int    # sequential identifier for the chunk

# Initialize FastAPI and chunk distributor
app = FastAPI()
distributor = ChunkDistributor()

@app.post("/receive_chunk/")
async def receive_chunk(chunk: ChunkData):
    try:
        # Pass the chunk to distributor
        video_data, audio_data = distributor.process_chunk(chunk)
        
        return {
            "status": "success",
            "chunk_id": chunk.chunk_id,
            "video_size": len(video_data),
            "audio_size": len(audio_data)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing chunk: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}