import os
import threading
import cv2
import numpy as np
import requests
import base64
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

# Directory to store raw and processed images.
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Global dictionary to queue images by chunk.
# Keys: chunk_id (int)
# Value: list of dictionaries with each image's metadata and raw bytes.
chunk_data = {}

# Global list to store best image info per chunk.
best_images = []

# Lock for synchronizing access to shared structures.
data_lock = threading.Lock()

# Destination URL for the receiving FastAPI server.
# Update <destination-ip> and port as needed.
DESTINATION_URL = "http://0.0.0.0:8000/receive_chunk/"

def process_chunk(chunk_id, images):
    """
    Process all images in a finished chunk:
      - Select the best (least blurry) image based on variance of Laplacian.
      - Save that image as an uncompressed BMP file.
      - Encode the file in base64 (ensuring pure, uncompressed image data).
      - Forward a JSON payload to the destination server.
    """
    print(f"[PROCESS] Processing chunk {chunk_id} with {len(images)} images")
    best_blur = -1.0
    best_image_info = None
    best_img = None

    for idx, img_info in enumerate(images):
        image_bytes = img_info['image_bytes']
        # Decode the raw bytes to an OpenCV image.
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            print(f"[PROCESS] Failed to decode image {idx} in chunk {chunk_id}")
            continue

        # Compute the blurriness metric (variance of Laplacian).
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        print(f"[PROCESS] Chunk {chunk_id}, image {idx}: blur metric = {variance}")

        # Update the best candidate if this image is less blurry.
        if variance > best_blur:
            best_blur = variance
            best_image_info = {
                'chunk_id': chunk_id,
                'chunk_start': img_info['chunk_start'],
                'blur_value': variance,
                'received_time': img_info.get('received_time')
            }
            best_img = img

    if best_image_info is not None and best_img is not None:
        # Save the best image as an uncompressed BMP file.
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"chunk{chunk_id}_best_{now_str}.bmp"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        cv2.imwrite(filepath, best_img)
        best_image_info['image_path'] = filepath

        # Append best image info to global list.
        with data_lock:
            best_images.append(best_image_info)
        print(f"[PROCESS] Best image for chunk {chunk_id}: blur={best_blur}, saved at {filepath}")

        # Read the BMP file and encode it to base64.
        with open(filepath, 'rb') as f:
            image_content = f.read()
        video_data_base64 = base64.b64encode(image_content).decode('utf-8')

        # Prepare the JSON payload matching the receiving server's expected format.
        payload = {
            "timestamp": datetime.now().timestamp(),  # Current timestamp (float)
            "video_data": video_data_base64,            # Base64 encoded uncompressed image
            "audio_data": "",                           # Audio data ignored for now
            "chunk_id": chunk_id
        }

        try:
            # Forward the payload to the receiving FastAPI endpoint.
            r = requests.post(DESTINATION_URL, json=payload, timeout=10)
            if r.status_code == 200:
                print(f"[FORWARD] Successfully forwarded best image for chunk {chunk_id}")
            else:
                print(f"[FORWARD] Failed to forward best image for chunk {chunk_id}: {r.status_code}")
        except Exception as e:
            print(f"[FORWARD] Exception while forwarding best image for chunk {chunk_id}: {e}")
    else:
        print(f"[PROCESS] No valid images processed for chunk {chunk_id}")

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Receives an image along with its chunk metadata.
    - Saves a raw copy of the image.
    - Queues the image under its chunk.
    - When a new chunk is detected, any lower-numbered chunks are considered complete
      and processed in separate threads.
    """
    try:
        # Extract chunk metadata from query parameters.
        chunk_id_str = request.args.get('chunk_id', None)
        chunk_start_str = request.args.get('chunk_start', None)
        if chunk_id_str is None or chunk_start_str is None:
            return "Missing chunk metadata", 400

        try:
            chunk_id = int(chunk_id_str)
            chunk_start = float(chunk_start_str)
        except ValueError:
            return "Invalid chunk metadata", 400

        # Retrieve image data from the request.
        image_data = request.data

        # Save a raw JPEG copy for reference.
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        raw_filename = f"chunk{chunk_id}_{chunk_start}_img_{now_str}.jpg"
        raw_filepath = os.path.join(UPLOAD_FOLDER, raw_filename)
        with open(raw_filepath, 'wb') as f:
            f.write(image_data)

        # Queue the image under its chunk.
        with data_lock:
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = []
            chunk_data[chunk_id].append({
                'chunk_start': chunk_start,
                'image_bytes': image_data,
                'received_time': datetime.now().timestamp()
            })

            # Any chunk with an ID lower than the current one is considered complete.
            completed_chunks = [cid for cid in chunk_data.keys() if cid < chunk_id]
            for cid in completed_chunks:
                images = chunk_data.pop(cid)
                threading.Thread(target=process_chunk, args=(cid, images), daemon=True).start()

        return f"Image received for chunk {chunk_id}", 200

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
