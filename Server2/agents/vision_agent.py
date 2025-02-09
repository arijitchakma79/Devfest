from PIL import Image
import base64
import os
from groq import Groq
from io import BytesIO
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Union
import logging
from functools import lru_cache
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ProcessingStats:
    total_frames_processed: int = 0
    total_humans_detected: int = 0
    last_processed_timestamp: float = 0
    processing_times: List[float] = None

    def __post_init__(self):
        if self.processing_times is None:
            self.processing_times = []

    def update(self, humans_detected: int, processing_time: float):
        self.total_frames_processed += 1
        self.total_humans_detected += humans_detected
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
class ImageSegment:
    coordinates: Tuple[int, int, int, int]
    image: Image.Image
    segment_number: int

@dataclass
class AnalysisResult:
    coordinates: Tuple[int, int, int, int]
    analysis: str
    human_count: int
    details: str
    confidence: float = 1.0
    safety_status: str = "SAFE"  # Added for frontend
    image_data: Optional[str] = None  # Added for frontend

class VisionAgent:
    def __init__(self, window_size=512, stride=384, max_workers=4, cache_size=128):
        load_dotenv()
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.window_size = window_size
        self.stride = stride
        self.max_workers = max_workers
        self.MAX_BASE64_SIZE = 4 * 1024 * 1024
        self.stats = ProcessingStats()  # Add this line
        self.confidence_threshold = 0.5  # Add this line
        self.min_segment_size = 256     # Add this line
        self.prompt = """As a search-and-rescue specialist, analyze this image segment.
        First state the number of people visible, then describe their conditions and positions.
        Include any immediate risks or hazards.
        Format: [Number]: [Brief description of people and risks]
        Example: "2: Two rescuers on damaged roof, one with safety equipment. Risk of structural collapse."
        Also assess if the detected humans are in a SAFE or UNSAFE situation.
        """

    def _get_confidence_level(self, confidence: float) -> str:
        """Convert confidence score to level."""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        return "low"

    @lru_cache(maxsize=128)
    def _get_optimal_quality(self, image_size: int) -> int:
        """Determine optimal JPEG quality based on image size."""
        if image_size < self.MAX_BASE64_SIZE:
            return 95
        elif image_size < self.MAX_BASE64_SIZE * 2:
            return 85
        elif image_size < self.MAX_BASE64_SIZE * 4:
            return 75
        else:
            return 65

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert image to base64 with size limitations."""
        if image.mode == 'RGBA':
            image = image.convert('RGB')

        # Resize if image is too large
        max_size = (800, 800)  # Maximum dimensions
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.LANCZOS)

        # Compress image
        buffered = BytesIO()
        image.save(buffered, format='JPEG', quality=85)
        
        return base64.b64encode(buffered.getvalue()).decode('utf-8')


    def _parse_analysis(self, analysis: str) -> Tuple[int, str, float]:
        """Parse the analysis response to extract count, details, and estimate confidence."""
        try:
            parts = analysis.split(':', 1)
            if len(parts) == 2:
                count = int(parts[0].strip())
                details = parts[1].strip()
                
                # Estimate confidence based on language used
                confidence = 1.0
                if any(word in details.lower() for word in ['maybe', 'possibly', 'unclear', 'might']):
                    confidence *= 0.7
                if any(word in details.lower() for word in ['difficult to see', 'partially visible']):
                    confidence *= 0.8
                    
                return count, details, confidence
            return 0, analysis, 0.5
        except (ValueError, IndexError):
            return 0, analysis, 0.5

    async def process_chunk(self, video_bytes: bytes) -> Dict:
        """Process incoming video chunk."""
        start_time = time.time()
        try:
            print("\n=== Vision Agent Processing Start ===")
            
            # Convert video frame bytes to PIL Image and resize
            image = Image.open(BytesIO(video_bytes))
            if image.size[0] > 800 or image.size[1] > 800:
                image.thumbnail((800, 800), Image.LANCZOS)
            
            # Convert back to base64 for storage
            compressed_image = self._image_to_base64(image)
            
            # Process the image
            result = await self.process_image(image)
            
            # Add the compressed image to result
            result['image_data'] = compressed_image
            
            # Update stats
            processing_time = time.time() - start_time
            self.stats.update(result.get('total_human_count', 0), processing_time)
            
            return result
            
        except Exception as e:
            print(f"ERROR in Vision Agent: {str(e)}")
            return {
                "error": str(e),
                "total_human_count": 0,
                "key_details": [],
                "segments": [],
                "image_data": None
            }

    def _analyze_segment(self, segment: ImageSegment) -> AnalysisResult:
        """Analyze a single image segment."""
        try:
            base64_image = self._image_to_base64(segment.image)
            segment_prompt = f"Segment {segment.segment_number}: {self.prompt}"
            
            response = self.client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": segment_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            analysis = response.choices[0].message.content
            human_count, details, confidence = self._parse_analysis(analysis)
            
            # Determine safety status based on analysis
            safety_status = "UNSAFE" if any(keyword in analysis.lower() 
                for keyword in ["risk", "hazard", "danger", "unsafe", "injured", "trapped"]) else "SAFE"
            
            return AnalysisResult(
                coordinates=segment.coordinates,
                analysis=analysis,
                human_count=human_count,
                details=details,
                confidence=confidence,
                safety_status=safety_status,
                image_data=base64_image
            )
        except Exception as e:
            logger.error(f"Error analyzing segment {segment.segment_number}: {str(e)}")
            return AnalysisResult(
                coordinates=segment.coordinates,
                analysis=f"Error: {str(e)}",
                human_count=0,
                details="",
                confidence=0.0,
                safety_status="UNKNOWN",
                image_data=None
            )


    def _generate_segments(self, img: Image.Image) -> List[ImageSegment]:
        """Generate overlapping image segments."""
        width, height = img.size
        segments = []
        segment_count = 0

        for y in range(0, height - self.stride//2, self.stride):
            for x in range(0, width - self.stride//2, self.stride):
                # Skip segments smaller than minimum size
                if (min(x + self.window_size, width) - x < self.min_segment_size or
                    min(y + self.window_size, height) - y < self.min_segment_size):
                    continue
                    
                segment_count += 1
                box = (
                    x,
                    y,
                    min(x + self.window_size, width),
                    min(y + self.window_size, height)
                )
                segment = img.crop(box)
                segments.append(ImageSegment(box, segment, segment_count))

        return segments

    async def process_image(self, image_input: Union[str, Image.Image, bytes]) -> Dict:
        """Process image with parallel segment analysis."""
        try:
            # Handle different input types
            if isinstance(image_input, str):
                if not os.path.exists(image_input):
                    raise FileNotFoundError(f"Image file not found: {image_input}")
                img = Image.open(image_input)
            elif isinstance(image_input, bytes):
                img = Image.open(BytesIO(image_input))
            elif isinstance(image_input, Image.Image):
                img = image_input
            else:
                raise ValueError("Unsupported image input type")
            
            # Check file size
            if isinstance(image_input, str):
                file_size = os.path.getsize(image_input)
                if file_size > 20 * 1024 * 1024:
                    raise ValueError(f"Image too large ({file_size} bytes). Must be under 20MB.")

            # Generate segments
            segments = self._generate_segments(img)
            logger.info(f"Processing {len(segments)} segments with {self.max_workers} workers")

            # Process segments in parallel
            results = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_segment = {
                    executor.submit(self._analyze_segment, segment): segment
                    for segment in segments
                }
                
                for future in as_completed(future_to_segment):
                    result = future.result()
                    if not result.analysis.startswith("Error"):
                        results.append(result)

            return self._aggregate_results(results)

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {
                "error": str(e),
                "total_human_count": 0,
                "key_details": [],
                "segments": []
            }

    def _aggregate_results(self, results: List[AnalysisResult]) -> Dict:
        """Aggregate and deduplicate analysis results."""
        final_report = {
            "total_human_count": 0,
            "key_details": [],
            "segments": [],
            "confidence_level": "high",
            "safety_statuses": [],
            "image_data": None,  # Will be added by process_chunk
            "stats": {
                "total_frames_processed": self.stats.total_frames_processed,
                "avg_processing_time": self.stats.get_average_processing_time(),
                "total_humans_detected": self.stats.total_humans_detected
            }
        }

        # Get the maximum confidence result for the total count
        max_confidence_result = max(results, key=lambda x: x.confidence) if results else None
        if max_confidence_result:
            final_report['total_human_count'] = max_confidence_result.human_count
            final_report['key_details'].append(
                f"{max_confidence_result.human_count}: {max_confidence_result.details}"
            )
            final_report['safety_statuses'].append(max_confidence_result.safety_status)

        # Add all segments for completeness
        for result in results:
            final_report['segments'].append({
                "coordinates": result.coordinates,
                "analysis": result.analysis,
                "confidence": result.confidence,
                "safety_status": result.safety_status
            })

        return final_report

    def _generate_summary(self, report: Dict) -> str:
        """Generate a detailed analysis summary."""
        summary = "Search and Rescue Analysis Summary\n"
        summary += "================================\n"
        summary += f"Estimated human presence: {report['total_human_count']} people\n"
        summary += f"Confidence level: {report['confidence_level']}\n"
        summary += f"Processing time: {report['stats']['avg_processing_time']:.2f}s\n\n"
        
        if report['key_details']:
            summary += "Key observations:\n"
            for detail in report['key_details']:
                summary += f"• {detail}\n"
        else:
            summary += "No human presence detected in analyzed segments.\n"
            
        if report['confidence_level'] != "high":
            summary += "\nNote: Some uncertainty in detection due to environmental factors or partial visibility.\n"
            
        return summary

    def get_stats(self) -> Dict:
        """Return current processing statistics."""
        return {
            "total_frames_processed": self.stats.total_frames_processed,
            "total_humans_detected": self.stats.total_humans_detected,
            "average_processing_time": self.stats.get_average_processing_time(),
            "last_processed": self.stats.last_processed_timestamp
        }