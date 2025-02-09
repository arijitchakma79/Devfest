import os
import tempfile
from dotenv import load_dotenv
from groq import Client
import base64
from dataclasses import dataclass
from typing import Dict, Optional
import logging
from functools import lru_cache
import time
from io import BytesIO

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ProcessingStats:
    total_audio_processed: int = 0
    total_dangers_detected: int = 0
    last_processed_timestamp: float = 0
    processing_times: list[float] = None

    def __post_init__(self):
        if self.processing_times is None:
            self.processing_times = []

    def update(self, danger_detected: bool, processing_time: float):
        self.total_audio_processed += 1
        if danger_detected:
            self.total_dangers_detected += 1
        self.last_processed_timestamp = time.time()
        self.processing_times.append(processing_time)
        
        # Keep only last 100 processing times
        if len(self.processing_times) > 100:
            self.processing_times.pop(0)

    def get_average_processing_time(self) -> float:
        if not self.processing_times:
            return 0
        return sum(self.processing_times) / len(self.processing_times)

@dataclass
class AudioAnalysisResult:
    transcription: str
    danger_detected: bool
    risk_analysis: str
    confidence: float = 1.0
    processing_time: float = 0.0

class AudioAgent:
    def __init__(self):
        load_dotenv()
        self.client = Client(api_key=os.getenv("GROQ_API_KEY"))
        if not os.getenv("GROQ_API_KEY"):
            raise ValueError("GROQ_API_KEY is not set in environment variables")
            
        self.stats = ProcessingStats()
        self.danger_prompt = """
        Analyze the following text and determine if it signals danger or distress.
        Consider words that may be phonetically similar to distress calls.
        Example: If the text is 'Hello', it may mean 'Help'.
        Respond with 'YES' if there is danger, otherwise respond with 'NO'.
        Provide a brief explanation.
        
        Text to analyze:
        """

    async def process_chunk(self, audio_bytes: bytes) -> Dict:
        """Process incoming audio chunk."""
        start_time = time.time()
        try:
            print("\n=== Audio Agent Processing Start ===")
            print(f"Received audio chunk of size: {len(audio_bytes)} bytes")
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name
            
            try:
                # Process audio file
                result = await self.process_audio(temp_file_path)
                
                # Update stats
                processing_time = time.time() - start_time
                self.stats.update(result.danger_detected, processing_time)
                
                print(f"Processing time: {processing_time:.2f} seconds")
                print("=== Audio Agent Processing Complete ===\n")
                
                return {
                    "transcription": result.transcription,
                    "danger_detected": result.danger_detected,
                    "risk_analysis": result.risk_analysis,
                    "confidence": result.confidence,
                    "processing_time": processing_time,
                    "stats": self.get_stats()
                }
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
        except Exception as e:
            logger.error(f"Error in Audio Agent: {str(e)}")
            return {
                "error": str(e),
                "transcription": "",
                "danger_detected": False,
                "risk_analysis": f"Error occurred: {str(e)}",
                "confidence": 0.0
            }

    async def process_audio(self, audio_file_path: str) -> AudioAnalysisResult:
        """Process audio file and analyze for danger signals."""
        try:
            # Transcribe audio
            with open(audio_file_path, "rb") as audio_file:
                print("Starting transcription...")
                transcription = self.client.audio.transcriptions.create(
                    file=("audio.wav", audio_file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="json",
                    language="en",
                    temperature=0.0
                )
            
            transcribed_text = transcription.text
            print(f"Transcription complete: {transcribed_text}")
            
            # Analyze risk
            danger_detected, risk_analysis, confidence = await self._analyze_risk(transcribed_text)
            
            return AudioAnalysisResult(
                transcription=transcribed_text,
                danger_detected=danger_detected,
                risk_analysis=risk_analysis,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            raise

    async def _analyze_risk(self, transcription_text: str) -> tuple[bool, str, float]:
        """Analyze transcribed text for danger signals."""
        try:
            full_prompt = self.danger_prompt + transcription_text
            
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": full_prompt}]
            )
            
            analysis = response.choices[0].message.content.strip()
            danger_detected = "YES" in analysis.upper()
            
            # Estimate confidence based on language used
            confidence = 1.0
            if any(word in analysis.lower() for word in ['maybe', 'possibly', 'unclear']):
                confidence *= 0.7
            if any(word in analysis.lower() for word in ['difficult to determine', 'uncertain']):
                confidence *= 0.8
            
            return danger_detected, analysis, confidence
            
        except Exception as e:
            logger.error(f"Error in risk analysis: {str(e)}")
            return False, f"Error in risk analysis: {str(e)}", 0.0

    def get_stats(self) -> Dict:
        """Return current processing statistics."""
        return {
            "total_audio_processed": self.stats.total_audio_processed,
            "total_dangers_detected": self.stats.total_dangers_detected,
            "average_processing_time": self.stats.get_average_processing_time(),
            "last_processed": self.stats.last_processed_timestamp
        }