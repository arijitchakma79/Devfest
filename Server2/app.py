import streamlit as st
import os
import re
import json
from PIL import Image
import base64
from io import BytesIO
import time

# Configuration
IMAGE_DIR = "images"  # Directory where MasterAgent saves annotated images
METADATA_DIR = "metadata"  # Directory where MasterAgent saves metadata JSONs
THUMBNAIL_SIZE = (400, 300)

# Page configuration
st.set_page_config(
    page_title="Danger Detector",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for layout and styling
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1rem;
        padding-right: 1rem;
        padding-left: 1rem;
        max-width: 100%;
    }
    
    .css-1d391kg {
        padding-top: 1rem;
    }
    
    .stat-card {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        margin-bottom: 1rem;
    }
    
    .priority-item {
        background: white;
        padding: 0.8rem;
        border-radius: 0.5rem;
        margin-bottom: 0.8rem;
        border: 1px solid #f0f0f0;
    }
    
    .priority-high { border-left: 4px solid #ff4b4b; }
    .priority-medium { border-left: 4px solid #ffa600; }
    .priority-low { border-left: 4px solid #00cc96; }

    .img-container {
        position: relative;
        margin-bottom: 1rem;
    }

    .img-overlay {
        position: absolute;
        top: 10px;
        left: 10px;
        background: rgba(0, 0, 0, 0.7);
        color: white;
        padding: 5px 10px;
        border-radius: 4px;
        font-size: 0.9em;
    }

    .safety-badge {
        position: absolute;
        top: 10px;
        right: 10px;
        padding: 5px 10px;
        border-radius: 4px;
        font-size: 0.9em;
        font-weight: bold;
    }

    .safe {
        background: rgba(0, 204, 150, 0.9);
        color: white;
    }

    .unsafe {
        background: rgba(255, 75, 75, 0.9);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def load_metadata() -> dict:
    """Load all metadata JSON files from the METADATA_DIR."""
    metadata = {}
    if os.path.exists(METADATA_DIR):
        for f in os.listdir(METADATA_DIR):
            if f.lower().endswith('.json'):
                try:
                    path = os.path.join(METADATA_DIR, f)
                    with open(path, "r") as mf:
                        data = json.load(mf)
                        chunk_id = str(data.get("chunk_id", ""))
                        metadata[chunk_id] = data
                except Exception as e:
                    st.error(f"Error loading metadata file {f}: {e}")
    return metadata

def load_images_with_metadata() -> list:
    """Load images and merge with metadata from MasterAgent output."""
    images = []
    meta = load_metadata()
    
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR, exist_ok=True)
        return images

    for f in sorted(os.listdir(IMAGE_DIR)):
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            try:
                img_path = os.path.join(IMAGE_DIR, f)
                image = Image.open(img_path).convert("RGB")
                w, h = image.size

                # Create thumbnail for display
                image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                buffered = BytesIO()
                image.save(buffered, format="WEBP", quality=85)
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                # Extract chunk id from filename
                match = re.match(r'chunk(\d+)_', f)
                chunk_id = match.group(1) if match else None

                # Get corresponding metadata
                if chunk_id and chunk_id in meta:
                    metadata = meta[chunk_id]
                else:
                    metadata = {
                        "chunk_id": chunk_id or "N/A",
                        "human_count": 0,
                        "safety_status": "UNKNOWN",
                        "description": "No description available",
                        "timestamp": "N/A",
                        "ai_analysis": "",
                        "key_observations": []
                    }

                images.append({
                    "src": f"data:image/webp;base64,{img_str}",
                    "path": img_path,
                    "width": w,
                    "height": h,
                    **metadata
                })
            except Exception as e:
                st.error(f"Error loading {f}: {e}")
    
    return images

def compute_stats(images):
    """Compute dashboard statistics from images data."""
    return {
        "Active Searches": {"value": len(images), "icon": "🔍"},
        "People Detected": {
            "value": sum(img.get("human_count", 0) for img in images),
            "icon": "👥"
        },
        "Danger Zones": {
            "value": sum(1 for img in images if img.get("safety_status") == "UNSAFE"),
            "icon": "⚠️"
        },
        "Search Area": {"value": "2.5 km²", "icon": "📍"}  # This could be computed based on metadata
    }

# Load images and metadata
with st.spinner("Loading images and metadata..."):
    start_time = time.time()
    images = load_images_with_metadata()
    load_duration = time.time() - start_time

# Sidebar content
with st.sidebar:
    with st.expander("ℹ️ About", expanded=True):
        st.write("""
        This application detects humans in images using YOLO model. Features:
        - Real-time object detection
        - Priority classification
        - Rescue operation monitoring
        """)
    
    st.markdown("### 🚨 Rescue Operations Dashboard")
    
    # Stats Overview
    st.markdown("### 📊 Stats Overview")
    stats = compute_stats(images)
    
    for label, data in stats.items():
        st.markdown(f"""
        <div class="stat-card">
            <div style="color: #666;">{data['icon']} {label}</div>
            <div style="font-size: 1.5rem; font-weight: bold;">{data['value']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Priority Queue based on actual data
    st.markdown("### 🚨 Priority Queue")
    sorted_images = sorted(
        images,
        key=lambda x: (
            x.get("safety_status") == "UNSAFE",
            x.get("human_count", 0)
        ),
        reverse=True
    )

    for img in sorted_images[:5]:  # Show top 5 priority items
        priority = "high" if img.get("safety_status") == "UNSAFE" else \
                  "medium" if img.get("human_count", 0) > 1 else "low"
        
        st.markdown(f"""
        <div class="priority-item priority-{priority}">
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <span class="status-indicator status-{priority}"></span>
                    Chunk {img.get('chunk_id', 'N/A')}
                </div>
                <div style="color: #666;">{img.get('timestamp', 'N/A')}</div>
            </div>
            <div style="color: #666; margin-top: 0.5rem;">
                {img.get('human_count', 0)} humans · {priority.capitalize()} priority
            </div>
        </div>
        """, unsafe_allow_html=True)

# Main content area
st.markdown("## Detected Images")

# Display images in a grid layout
cols = st.columns(3)
for idx, img in enumerate(images):
    with cols[idx % 3]:
        st.markdown(f"""
        <div class="img-container">
            <img src="{img['src']}" style="width: 100%; border-radius: 8px;">
            <div class="img-overlay">
                {img.get('human_count', 0)} Human{'s' if img.get('human_count', 0) != 1 else ''} Detected
            </div>
            <div class="safety-badge {'safe' if img.get('safety_status') == 'SAFE' else 'unsafe'}">
                {img.get('safety_status', 'UNKNOWN')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("Details"):
            st.write(f"**Description:** {img.get('description', 'No description available')}")
            if img.get('key_observations'):
                st.write("**Key Observations:**")
                for obs in img.get('key_observations', []):
                    st.write(f"- {obs}")
            if img.get('ai_analysis'):
                st.write("**AI Analysis:**")
                st.write(img['ai_analysis'])

st.caption(f"Loaded {len(images)} images in {load_duration:.2f}s")