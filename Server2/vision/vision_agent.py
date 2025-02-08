from PIL import Image
import base64
import os
from groq import Groq
from io import BytesIO
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import logging
from functools import lru_cache

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

class VisionAgent:
    def __init__(self, window_size=512, stride=384, max_workers=4, cache_size=128):
        load_dotenv()
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.window_size = window_size
        self.stride = stride
        self.max_workers = max_workers
        self.MAX_BASE64_SIZE = 4 * 1024 * 1024
        self.prompt = """As a search-and-rescue specialist, analyze this image segment.
        First state the number of people visible, then describe their conditions and positions.
        Include any immediate risks or hazards.
        Format: [Number]: [Brief description of people and risks]
        Example: "2: Two rescuers on damaged roof, one with safety equipment. Risk of structural collapse."
        """

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
        """Convert image to base64 with adaptive compression."""
        if image.mode == 'RGBA':
            image = image.convert('RGB')

        # Get initial image size
        test_buffer = BytesIO()
        image.save(test_buffer, format='JPEG', quality=95)
        initial_size = len(test_buffer.getvalue())

        # Use cached quality setting
        quality = self._get_optimal_quality(initial_size)
        
        buffered = BytesIO()
        image.save(buffered, format='JPEG', quality=quality)
        
        if len(buffered.getvalue()) > self.MAX_BASE64_SIZE:
            raise ValueError(f"Image too large even after compression")
            
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def _parse_analysis(self, analysis: str) -> Tuple[int, str]:
        """Parse the analysis response to extract count and details."""
        try:
            parts = analysis.split(':', 1)
            if len(parts) == 2:
                count = int(parts[0].strip())
                details = parts[1].strip()
                return count, details
            return 0, analysis
        except (ValueError, IndexError):
            return 0, analysis

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
            human_count, details = self._parse_analysis(analysis)
            
            return AnalysisResult(
                coordinates=segment.coordinates,
                analysis=analysis,
                human_count=human_count,
                details=details
            )
        except Exception as e:
            logger.error(f"Error analyzing segment {segment.segment_number}: {str(e)}")
            return AnalysisResult(
                coordinates=segment.coordinates,
                analysis=f"Error: {str(e)}",
                human_count=0,
                details=""
            )

    def _generate_segments(self, img: Image.Image) -> List[ImageSegment]:
        """Generate overlapping image segments."""
        width, height = img.size
        segments = []
        segment_count = 0

        for y in range(0, height - self.stride//2, self.stride):
            for x in range(0, width - self.stride//2, self.stride):
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

    def process_image(self, image_path: str) -> Dict:
        """Process image with parallel segment analysis."""
        try:
            # Validate and load image
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
                
            img = Image.open(image_path)
            
            # Check file size
            file_size = os.path.getsize(image_path)
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
            "confidence_level": "high"
        }

        # Track unique detections to avoid duplicates
        unique_detections = set()
        detection_counts = {}

        for result in results:
            if result.human_count > 0:
                # Create a normalized version of the details for deduplication
                normalized_details = ' '.join(result.details.lower().split())
                
                if normalized_details not in unique_detections:
                    unique_detections.add(normalized_details)
                    final_report['key_details'].append(f"{result.human_count}: {result.details}")
                    
                    # Track detection frequencies
                    for i in range(result.human_count):
                        coord_key = (
                            result.coordinates[0] // self.stride,
                            result.coordinates[1] // self.stride
                        )
                        detection_counts[coord_key] = detection_counts.get(coord_key, 0) + 1

            final_report['segments'].append({
                "coordinates": result.coordinates,
                "analysis": result.analysis
            })

        # Estimate total count considering overlaps
        if detection_counts:
            # Use the mode of detection counts as the likely true count
            most_common_count = max(detection_counts.values())
            final_report['total_human_count'] = most_common_count
            
            # Adjust confidence level based on detection consistency
            variance = len(set(detection_counts.values()))
            if variance > 2:
                final_report['confidence_level'] = "medium"
            elif variance > 4:
                final_report['confidence_level'] = "low"

        final_report['description'] = self._generate_summary(final_report)
        return final_report

    def _generate_summary(self, report: Dict) -> str:
        """Generate a detailed analysis summary."""
        summary = "Search and Rescue Analysis Summary\n"
        summary += "================================\n"
        summary += f"Estimated human presence: {report['total_human_count']} people\n"
        summary += f"Confidence level: {report['confidence_level']}\n\n"
        
        if report['key_details']:
            summary += "Key observations:\n"
            for detail in report['key_details']:
                summary += f"• {detail}\n"
        else:
            summary += "No human presence detected in analyzed segments.\n"
            
        if report['confidence_level'] != "high":
            summary += "\nNote: Some uncertainty in detection due to environmental factors or partial visibility.\n"
            
        return summary


if __name__ == "__main__":
    # Example usage
    agent = VisionAgent(max_workers=4)  # Adjust workers based on CPU cores
    result = agent.process_image("test.jpg")
    print(result['description'])
    
    # Print detailed segment analysis if verbose output is needed
    if result['segments']:
        print("\nDetailed segment analysis:")
        for seg in result['segments'][:3]:
            if not seg['analysis'].startswith("Error"):
                print(f"\nArea {seg['coordinates']}:")
                print(seg['analysis'])