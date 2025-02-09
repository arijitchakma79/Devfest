from dataclasses import dataclass
from typing import Dict, List, Optional
import time
import logging
from agents.vision_agent import VisionAgent
from agents.audio_agent import AudioAgent

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SituationalAwareness:
    humans_detected: int
    danger_level: str  # "low", "medium", "high"
    confidence: float
    scene_description: str
    audio_transcription: str
    key_observations: List[str]
    timestamp: float

class MasterAgent:
    def __init__(self):
        self.vision_agent = VisionAgent()
        self.audio_agent = AudioAgent()
        self.situation_history: List[SituationalAwareness] = []
        
    async def process_chunk(self, chunk_id: int, video_data: bytes, audio_data: bytes) -> Dict:
        """
        Process a chunk of video and audio data and return unified analysis.
        """
        try:
            print(f"\n=== Master Agent Processing Chunk {chunk_id} ===")
            chunk_start_time = time.time()

            # Process video and audio in parallel
            vision_results = await self.vision_agent.process_chunk(video_data)
            audio_results = await self.audio_agent.process_chunk(audio_data)

            # Analyze combined results
            situation = self._analyze_situation(vision_results, audio_results)
            
            # Store in history
            self.situation_history.append(situation)
            if len(self.situation_history) > 100:  # Keep last 100 situations
                self.situation_history.pop(0)

            processing_time = time.time() - chunk_start_time
            
            return {
                "chunk_id": chunk_id,
                "timestamp": situation.timestamp,
                "processing_time": processing_time,
                "analysis": {
                    "humans_detected": situation.humans_detected,
                    "danger_level": situation.danger_level,
                    "confidence": situation.confidence,
                    "scene_description": situation.scene_description,
                    "audio_transcription": situation.audio_transcription,
                    "key_observations": situation.key_observations
                },
                "vision_stats": vision_results.get("stats", {}),
                "audio_stats": audio_results.get("stats", {}),
            }

        except Exception as e:
            logger.error(f"Error in Master Agent processing chunk {chunk_id}: {str(e)}")
            return {
                "chunk_id": chunk_id,
                "timestamp": time.time(),
                "error": str(e)
            }

    def _analyze_situation(self, vision_results: Dict, audio_results: Dict) -> SituationalAwareness:
        """
        Combine vision and audio results to create overall situational awareness.
        """
        # Extract information from vision results
        humans_detected = vision_results.get("total_human_count", 0)
        vision_confidence = vision_results.get("confidence_level", "medium")
        
        # Extract information from audio results
        danger_detected = audio_results.get("danger_detected", False)
        audio_confidence = audio_results.get("confidence", 0.5)
        
        # Combine confidences
        overall_confidence = (self._confidence_to_float(vision_confidence) + audio_confidence) / 2
        
        # Determine danger level
        danger_level = self._assess_danger_level(
            vision_results, 
            audio_results,
            humans_detected
        )
        
        # Compile key observations
        key_observations = []
        
        # Add vision observations
        if "key_details" in vision_results:
            key_observations.extend(vision_results["key_details"])
            
        # Add audio observations
        if audio_results.get("risk_analysis"):
            key_observations.append(f"Audio Analysis: {audio_results['risk_analysis']}")
            
        return SituationalAwareness(
            humans_detected=humans_detected,
            danger_level=danger_level,
            confidence=overall_confidence,
            scene_description=vision_results.get("description", "No visual description available"),
            audio_transcription=audio_results.get("transcription", "No audio transcription available"),
            key_observations=key_observations,
            timestamp=time.time()
        )

    def _confidence_to_float(self, confidence_level: str) -> float:
        """Convert string confidence level to float."""
        confidence_map = {
            "low": 0.3,
            "medium": 0.6,
            "high": 0.9
        }
        return confidence_map.get(confidence_level.lower(), 0.5)

    def _assess_danger_level(self, vision_results: Dict, audio_results: Dict, humans_detected: int) -> str:
        """
        Assess overall danger level based on all inputs.
        Returns: "low", "medium", or "high"
        """
        danger_score = 0
        
        # Audio danger contribution
        if audio_results.get("danger_detected"):
            danger_score += 2
            
        # Vision danger assessment
        if "key_details" in vision_results:
            danger_keywords = ["injured", "trapped", "risk", "hazard", "danger", "emergency"]
            for detail in vision_results["key_details"]:
                if any(keyword in detail.lower() for keyword in danger_keywords):
                    danger_score += 1
                    
        # Human presence factor
        if humans_detected > 0:
            danger_score += 1
            
        # Determine level
        if danger_score >= 3:
            return "high"
        elif danger_score >= 1:
            return "medium"
        return "low"

    def get_historical_analysis(self) -> Dict:
        """
        Analyze historical data to identify patterns or trends.
        """
        if not self.situation_history:
            return {"message": "No historical data available"}
            
        total_humans = 0
        danger_levels = {"low": 0, "medium": 0, "high": 0}
        
        for situation in self.situation_history:
            total_humans += situation.humans_detected
            danger_levels[situation.danger_level] += 1
            
        avg_humans = total_humans / len(self.situation_history)
        
        return {
            "average_humans_per_frame": avg_humans,
            "danger_level_distribution": danger_levels,
            "total_situations_analyzed": len(self.situation_history)
        }

    def get_latest_situation(self) -> Optional[SituationalAwareness]:
        """Return the most recent situation analysis."""
        return self.situation_history[-1] if self.situation_history else None