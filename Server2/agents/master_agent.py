import os
import time
import base64
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from agents.vision_agent import VisionAgent
from agents.audio_agent import AudioAgent
from groq import Client
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SituationalAwareness:
    chunk_id: int
    humans_detected: int
    danger_level: str  # "low", "medium", "high"
    confidence: float
    scene_description: str
    audio_transcription: str
    key_observations: List[str]
    timestamp: float
    sector: str  # For frontend
    safety_status: str  # For frontend
    image_path: str  # Local file path for the saved image

class MasterAgent:
    def __init__(self):
        load_dotenv()
        self.vision_agent = VisionAgent()
        self.audio_agent = AudioAgent()
        self.last_chunk_id = 0
        self.last_chunk_time = time.time()
        self.latest_situation: Optional[SituationalAwareness] = None  # Store latest situation
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        self.client = Client(api_key=groq_api_key)
        self.sectors = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        self.current_sector_index = 0

    def _get_next_sector(self) -> str:
        sector = self.sectors[self.current_sector_index]
        self.current_sector_index = (self.current_sector_index + 1) % len(self.sectors)
        return sector

    def save_image_locally(self, video_data: bytes, chunk_id: int) -> str:
        """
        Save the raw video frame (assumed to be an image) to a local file.
        Returns the file path.
        """
        directory = "images"
        os.makedirs(directory, exist_ok=True)
        filename = os.path.join(directory, f"chunk_{chunk_id}.jpg")
        try:
            # Convert the raw bytes to an image using PIL.
            from PIL import Image
            import io
            image = Image.open(io.BytesIO(video_data))
            image.save(filename, format="JPEG")
            logger.info(f"Image for chunk {chunk_id} saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving image for chunk {chunk_id}: {str(e)}")
            raise e
        return filename

    async def _get_situation_analysis(self, vision_results: Dict, audio_results: Dict, chunk_id: int) -> str:
        """Use AI to analyze the overall situation for the current chunk."""
        try:
            prompt = f"""As an AI Search and Rescue Analyst, analyze this real-time data from our drone surveillance system (Chunk {chunk_id}).

Visual Analysis Data:
- Humans Detected: {vision_results.get('total_human_count', 0)}
- Scene Description: {vision_results.get('description', 'No description available')}
- Key Visual Details: {', '.join(vision_results.get('key_details', []))}

Audio Analysis Data:
- Transcription: {audio_results.get('transcription', 'No audio available')}
- Danger Detected: {audio_results.get('danger_detected', False)}
- Risk Analysis: {audio_results.get('risk_analysis', 'No analysis available')}

Based on this data:
1. Provide a clear, human-readable situational analysis.
2. Identify any immediate risks.
3. Suggest actionable steps for rescue teams.
"""
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in AI situation analysis: {str(e)}")
            return "Error generating situation analysis"

    async def process_chunk(self, chunk_id: int, video_data: bytes, audio_data: bytes) -> Dict:
        """Process a chunk and store the latest situation analysis without trend tracking."""
        try:
            logger.info(f"\n=== Master Agent Processing Chunk {chunk_id} ===")
            chunk_start_time = time.time()

            # Check chunk sequence and timing
            time_since_last = chunk_start_time - self.last_chunk_time
            if chunk_id != self.last_chunk_id + 1:
                logger.warning(f"Chunk sequence break: Expected {self.last_chunk_id + 1}, got {chunk_id}")
            if time_since_last > 2.0:
                logger.warning(f"Large time gap between chunks: {time_since_last:.2f} seconds")

            # Process video and audio data with the respective agents
            vision_results = await self.vision_agent.process_chunk(video_data)
            audio_results = await self.audio_agent.process_chunk(audio_data)

            # Get current sector information
            current_sector = self._get_next_sector()

            # Save the video frame as an image locally
            image_path = self.save_image_locally(video_data, chunk_id)

            # Analyze the situation for the current chunk
            situation = self._analyze_situation(
                chunk_id=chunk_id,
                vision_results=vision_results,
                audio_results=audio_results,
                sector=current_sector,
                image_path=image_path  # Use the local file path
            )

            # Get additional AI analysis for a human-readable summary
            ai_analysis = await self._get_situation_analysis(vision_results, audio_results, chunk_id)

            # Update tracking and store the latest situation
            self.last_chunk_id = chunk_id
            self.last_chunk_time = time.time()
            self.latest_situation = situation

            processing_time = time.time() - chunk_start_time

            return {
                "chunk_id": chunk_id,
                "timestamp": situation.timestamp,
                "processing_time": processing_time,
                "current_analysis": {
                    "humans_detected": situation.humans_detected,
                    "danger_level": situation.danger_level,
                    "confidence": situation.confidence,
                    "scene_description": situation.scene_description,
                    "audio_transcription": situation.audio_transcription,
                    "key_observations": situation.key_observations,
                    "ai_situation_analysis": ai_analysis,
                    "sector": situation.sector,
                    "safety_status": situation.safety_status,
                    "image_path": situation.image_path
                },
                "vision_stats": vision_results.get("stats", {}),
                "audio_stats": audio_results.get("stats", {})
            }

        except Exception as e:
            logger.error(f"Error in Master Agent processing chunk {chunk_id}: {str(e)}")
            return {
                "chunk_id": chunk_id,
                "timestamp": time.time(),
                "error": str(e)
            }

    def _analyze_situation(self, chunk_id: int, vision_results: Dict, audio_results: Dict, sector: str, image_path: str) -> SituationalAwareness:
        """Combine vision and audio results to create a situational awareness report for the current chunk."""
        humans_detected = vision_results.get("total_human_count", 0)
        vision_confidence = self._confidence_to_float(vision_results.get("confidence_level", "medium"))
        audio_confidence = audio_results.get("confidence", 0.5)
        overall_confidence = (vision_confidence + audio_confidence) / 2

        danger_level = self._assess_danger_level(vision_results, audio_results, humans_detected)
        safety_status = "SAFE" if danger_level == "low" else "UNSAFE"

        key_observations = []
        if "key_details" in vision_results:
            key_observations.extend(vision_results["key_details"])
        if audio_results.get("risk_analysis"):
            key_observations.append(f"Audio Analysis: {audio_results['risk_analysis']}")

        return SituationalAwareness(
            chunk_id=chunk_id,
            humans_detected=humans_detected,
            danger_level=danger_level,
            confidence=overall_confidence,
            scene_description=vision_results.get("description", "No visual description available"),
            audio_transcription=audio_results.get("transcription", "No audio transcription available"),
            key_observations=key_observations,
            timestamp=time.time(),
            sector=sector,
            safety_status=safety_status,
            image_path=image_path
        )

    def _confidence_to_float(self, confidence_level: str) -> float:
        """Convert a string-based confidence level to a numerical value."""
        confidence_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
        return confidence_map.get(confidence_level.lower(), 0.5)

    def _assess_danger_level(self, vision_results: Dict, audio_results: Dict, humans_detected: int) -> str:
        """Compute a danger level based on the analysis results."""
        danger_score = 0
        if audio_results.get("danger_detected"):
            danger_score += 2
        if "key_details" in vision_results:
            danger_keywords = ["injured", "trapped", "risk", "hazard", "danger", "emergency"]
            for detail in vision_results["key_details"]:
                if any(keyword in detail.lower() for keyword in danger_keywords):
                    danger_score += 1
        if danger_score >= 3:
            return "high"
        elif danger_score >= 1:
            return "medium"
        return "low"

    def get_latest_analysis(self) -> Dict:
        """Return the latest processed situation analysis."""
        if self.latest_situation:
            return {
                "chunk_id": self.latest_situation.chunk_id,
                "timestamp": self.latest_situation.timestamp,
                "current_analysis": {
                    "humans_detected": self.latest_situation.humans_detected,
                    "danger_level": self.latest_situation.danger_level,
                    "confidence": self.latest_situation.confidence,
                    "scene_description": self.latest_situation.scene_description,
                    "audio_transcription": self.latest_situation.audio_transcription,
                    "key_observations": self.latest_situation.key_observations,
                    "sector": self.latest_situation.sector,
                    "safety_status": self.latest_situation.safety_status,
                    "image_path": self.latest_situation.image_path
                }
            }
        return {"message": "No analysis available"}
