import streamlit as st
import requests
from PIL import Image
import time
import os

# API Configuration
API_URL = "http://localhost:8000"  # Adjust if your API is hosted elsewhere

# Page configuration
st.set_page_config(
    page_title="Search & Rescue Dashboard",
    page_icon="🚨",
    layout="wide"
)

def get_latest_data():
    """
    Fetch the latest analysis data from the API's /stream_status/ endpoint.
    """
    try:
        response = requests.get(f"{API_URL}/stream_status/")
        data = response.json()
        st.write("Raw API Response:", data)  # Debug output
        return data
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def display_local_image(image_path: str):
    """
    Loads and displays an image from the given local file path.
    """
    try:
        # Check if file exists
        if not os.path.exists(image_path):
            st.error(f"Image file not found: {image_path}")
            return
        
        # Open and display the image
        image = Image.open(image_path)
        st.image(image, caption="Latest Detection", use_column_width=True)
    except Exception as e:
        st.error(f"Error loading image from {image_path}: {str(e)}")

def main():
    st.title("🚨 Search & Rescue Operations Dashboard")
    st.subheader("Latest Drone Feed and Analysis")

    # Get the latest data from the API
    data = get_latest_data()
    if data is None or "stream_status" not in data:
        st.info("No analysis data available yet.")
        return

    current_analysis = data.get("stream_status", {}).get("current_analysis", {})
    
    # Display the image from the latest chunk
    if current_analysis.get("image_path"):
        st.markdown("#### Latest Image")
        display_local_image(current_analysis["image_path"])
    else:
        st.warning("No image available for the latest analysis.")

    # Display human-readable analysis details
    st.markdown("#### Analysis Details")
    st.write(f"**Humans Detected:** {current_analysis.get('humans_detected', 'N/A')}")
    st.write(f"**Danger Level:** {current_analysis.get('danger_level', 'N/A')}")
    st.write(f"**Safety Status:** {current_analysis.get('safety_status', 'N/A')}")
    st.write(f"**Scene Description:** {current_analysis.get('scene_description', 'N/A')}")
    st.write(f"**Audio Transcription:** {current_analysis.get('audio_transcription', 'N/A')}")
    key_obs = current_analysis.get('key_observations', [])
    if key_obs:
        st.write("**Key Observations:**")
        for obs in key_obs:
            st.write(f"- {obs}")
    st.write(f"**Sector:** {current_analysis.get('sector', 'N/A')}")
    st.write(f"**AI Analysis:** {current_analysis.get('ai_situation_analysis', 'N/A')}")
    
    st.markdown("---")
    st.subheader("System Status")
    st.write("Last update:", time.strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    main()
