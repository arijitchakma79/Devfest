from dataclasses import dataclass
from typing import Dict, List, Optional, Deque
import time
import logging
from collections import deque
from agents.vision_agent import VisionAgent
from agents.audio_agent import AudioAgent

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

class StreamAnalysis:
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.recent_situations: Deque[SituationalAwareness] = deque(maxlen=window_size)
        self.total_humans_trend: List[int] = []
        self.danger_level_history: List[str] = []
        self.last_updated = time.time()

    def add_situation(self, situation: SituationalAwareness):
        self.recent_situations.append(situation)
        self.total_humans_trend.append(situation.humans_detected)
        self.danger_level_history.append(situation.danger_level)
        self.last_updated = time.time()
        
        # Keep trends within a reasonable size
        if len(self.total_humans_trend) > 100:
            self.total_humans_trend.pop(0)
        if len(self.danger_level_history) > 100:
            self.danger_level_history.pop(0)

    def get_current_trends(self) -> Dict:
        if not self.recent_situations:
            return {"message": "No data available"}

        # Analyze recent human count trend
        recent_human_counts = [s.humans_detected for s in self.recent_situations]
        human_count_trend = "stable"
        if len(recent_human_counts) > 1:
            if recent_human_counts[-1] > recent_human_counts[0]:
                human_count_trend = "increasing"
            elif recent_human_counts[-1] < recent_human_counts[0]:
                human_count_trend = "decreasing"

        # Analyze danger level trend
        current_danger = self.danger_level_history[-1]
        danger_trend = "stable"
        if len(self.danger_level_history) > 1:
            danger_levels = {"low": 0, "medium": 1, "high": 2}
            prev_level = danger_levels[self.danger_level_history[-2]]
            curr_level = danger_levels[current_danger]
            if curr_level > prev_level:
                danger_trend = "escalating"
            elif curr_level < prev_level:
                danger_trend = "deescalating"

        return {
            "current_situation": {
                "humans_present": self.recent_situations[-1].humans_detected,
                "danger_level": current_danger,
                "latest_observations": self.recent_situations[-1].key_observations
            },
            "trends": {
                "human_count_trend": human_count_trend,
                "danger_trend": danger_trend,
                "time_window": f"Last {len(self.recent_situations)} seconds"
            }
        }

class MasterAgent:
    def __init__(self, history_window: int = 10):
        self.vision_agent = VisionAgent()
        self.audio_agent = AudioAgent()
        self.stream_analysis = StreamAnalysis(window_size=history_window)
        self.last_chunk_id = 0
        self.last_chunk_time = time.time()
        
    async def process_chunk(self, chunk_id: int, video_data: bytes, audio_data: bytes) -> Dict:
        """Process a chunk and maintain stream awareness"""
        try:
            print(f"\n=== Master Agent Processing Chunk {chunk_id} ===")
            chunk_start_time = time.time()

            # Check chunk sequence and timing
            time_since_last = chunk_start_time - self.last_chunk_time
            if chunk_id != self.last_chunk_id + 1:
                logger.warning(f"Chunk sequence break: Expected {self.last_chunk_id + 1}, got {chunk_id}")
            if time_since_last > 2.0:  # Warning if more than 2 seconds between chunks
                logger.warning(f"Large time gap between chunks: {time_since_last:.2f} seconds")

            # Process video and audio
            vision_results = await self.vision_agent.process_chunk(video_data)
            audio_results = await self.audio_agent.process_chunk(audio_data)

            # Create situation awareness
            situation = self._analyze_situation(chunk_id, vision_results, audio_results)
            
            # Update stream analysis
            self.stream_analysis.add_situation(situation)
            
            # Update chunk tracking
            self.last_chunk_id = chunk_id
            self.last_chunk_time = time.time()

            # Get current trends
            trends = self.stream_analysis.get_current_trends()

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
                    "key_observations": situation.key_observations
                },
                "stream_trends": trends,
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

    def _analyze_situation(self, chunk_id: int, vision_results: Dict, audio_results: Dict) -> SituationalAwareness:
        """Analyze current situation considering stream history"""
        # Extract information
        humans_detected = vision_results.get("total_human_count", 0)
        vision_confidence = vision_results.get("confidence_level", "medium")
        danger_detected = audio_results.get("danger_detected", False)
        audio_confidence = audio_results.get("confidence", 0.5)
        
        # Combine confidences
        overall_confidence = (self._confidence_to_float(vision_confidence) + audio_confidence) / 2
        
        # Assess danger considering history
        danger_level = self._assess_danger_level(
            vision_results, 
            audio_results,
            humans_detected
        )
        
        # Compile observations
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
        """Assess danger level considering stream history"""
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
        
        # Consider trend if we have history
        if self.stream_analysis.danger_level_history:
            if all(level == "high" for level in self.stream_analysis.danger_level_history[-3:]):
                danger_score += 1
            
        # Determine level
        if danger_score >= 3:
            return "high"
        elif danger_score >= 1:
            return "medium"
        return "low"

    def get_stream_status(self) -> Dict:
        """Get current stream status and trends"""
        return {
            "last_chunk_id": self.last_chunk_id,
            "time_since_last_chunk": time.time() - self.last_chunk_time,
            "stream_health": "healthy" if time.time() - self.last_chunk_time < 2.0 else "delayed",
            "trends": self.stream_analysis.get_current_trends()
        }