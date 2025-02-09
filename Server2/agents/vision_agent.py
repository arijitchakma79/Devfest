from PIL import Image, ImageDraw
import base64
import os
from groq import Groq
from io import BytesIO
from dotenv import load_dotenv
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List, Union
from functools import lru_cache
import numpy as np
from ultralytics import YOLO  # Ensure ultralytics is installed

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

class VisionAgent:
    def __init__(self, yolo_model_path: str = "yolov8x.pt"):
        load_dotenv()
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.stats = ProcessingStats()
        self.confidence_threshold = 0.5  # Confidence threshold for YOLO detections
        # Load YOLO model for human detection
        self.yolo = YOLO(yolo_model_path)
        # LLM prompt template for analysis
        self.prompt_template = (
            "As a search-and-rescue specialist, analyze the following image detection data:\n\n"
            "Detected {count} human(s) with bounding boxes:\n{boxes}\n\n"
            "Provide a concise situational analysis, noting any immediate risks or hazards. "
            "Conclude with a safety assessment: 'SAFE' or 'UNSAFE'. "
            "Also describe what you are seeing in the image. What are the persons doing etc and everything near the surroundings"
        )

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert image to base64 string with size limitations."""
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        max_size = (800, 800)  # Maximum dimensions
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.LANCZOS)
        buffered = BytesIO()
        image.save(buffered, format='JPEG', quality=85)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def _run_yolo_detection(self, image: Image.Image) -> Tuple[List[Tuple[int, int, int, int, float]], Image.Image]:
        """
        Run YOLO detection on the image.
        Returns a list of bounding boxes for detected humans and an annotated image.
        Each bounding box is a tuple: (x1, y1, x2, y2, confidence).
        """
        # Convert PIL image to numpy array
        img_np = np.array(image)
        # Run YOLO detection
        results = self.yolo(img_np)
        boxes = []
        # Iterate over results (assume one image per inference)
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                conf = box.conf[0].item()
                # YOLO typically uses class 0 for "person"
                if class_id == 0 and conf >= self.confidence_threshold:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    boxes.append((x1, y1, x2, y2, conf))
        
        # Create a copy of the image to annotate
        annotated_image = image.copy()
        draw = ImageDraw.Draw(annotated_image)
        for (x1, y1, x2, y2, conf) in boxes:
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1, y1), f"{conf:.2f}", fill="white")
        return boxes, annotated_image


    async def process_chunk(self, video_bytes: bytes) -> Dict:
        """Process incoming video chunk using YOLO detection and LLM analysis."""
        start_time = time.time()
        try:
            print("\n=== Vision Agent Processing Start ===")
            # Open the video frame as a PIL image
            image = Image.open(BytesIO(video_bytes))
            if image.size[0] > 800 or image.size[1] > 800:
                image.thumbnail((800, 800), Image.LANCZOS)
            
            # Run YOLO detection
            boxes, annotated_image = self._run_yolo_detection(image)
            human_count = len(boxes)
            
            # Convert annotated image to base64 for storage/display
            annotated_image_b64 = self._image_to_base64(annotated_image)
            
            # Prepare detection details for the LLM prompt
            boxes_str = "\n".join(
                [f"Box {i+1}: {x1},{y1},{x2},{y2} (conf: {conf:.2f})" for i, (x1, y1, x2, y2, conf) in enumerate(boxes)]
            )
            prompt = self.prompt_template.format(count=human_count, boxes=boxes_str if boxes_str else "None")
            
            # Call the LLM via Groq
            response = self.client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            analysis = response.choices[0].message.content
            # Determine safety status based on keywords in the analysis
            safety_status = "UNSAFE" if any(keyword in analysis.lower() 
                                             for keyword in ["risk", "hazard", "danger", "injured", "trapped"]) else "SAFE"
            processing_time = time.time() - start_time
            self.stats.update(human_count, processing_time)
            
            return {
                "total_human_count": human_count,
                "detection_boxes": boxes,
                "analysis": analysis,
                "safety_status": safety_status,
                "image_data": annotated_image_b64,
                "stats": {
                    "total_frames_processed": self.stats.total_frames_processed,
                    "avg_processing_time": self.stats.get_average_processing_time(),
                    "total_humans_detected": self.stats.total_humans_detected
                }
            }
            
        except Exception as e:
            print(f"ERROR in Vision Agent: {str(e)}")
            return {
                "error": str(e),
                "total_human_count": 0,
                "analysis": "",
                "safety_status": "UNKNOWN",
                "image_data": None
            }
