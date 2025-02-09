import streamlit as st
import requests
import base64
from PIL import Image
import io
import time

# API Configuration
API_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="Search & Rescue Dashboard",
    page_icon="🚨",
    layout="wide"
)

def get_latest_data():
    try:
        response = requests.get(f"{API_URL}/stream_status/")
        st.write("Raw API Response:", response.json())  # Debug: Show raw response
        return response.json()
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def display_image(image_data):
    try:
        st.write("Attempting to display image...")  # Debug message
        st.write("Image data type:", type(image_data))  # Debug: Show data type
        
        # Try to decode and display image
        image_bytes = base64.b64decode(image_data)
        st.write("Decoded image size:", len(image_bytes))  # Debug: Show size
        
        image = Image.open(io.BytesIO(image_bytes))
        st.write("Image size:", image.size)  # Debug: Show image dimensions
        
        st.image(image, caption="Latest Detection")
        st.success("Image displayed successfully!")  # Debug: Success message
    except Exception as e:
        st.error(f"Image Display Error: {str(e)}")

def main():
    st.title("🚨 Search & Rescue Operations Dashboard")
    
    # Debug section
    st.subheader("Debug Information")
    if st.button("Fetch Latest Data"):
        data = get_latest_data()
        if data:
            st.json(data)  # Show full JSON response
            
            # Check for image data
            current_analysis = data.get('current_analysis', {})
            image_data = current_analysis.get('image_data')
            
            if image_data:
                st.write("Found image data! Attempting to display...")
                display_image(image_data)
            else:
                st.warning("No image data found in response")
    
    # Main dashboard content
    left_col, right_col = st.columns([1, 2])
    
    with left_col:
        st.subheader("📊 Stats Overview")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🔍 Active Searches", "10")
            st.metric("👥 People Detected", "0")
        with col2:
            st.metric("⚠️ Danger Zones", "0")
            st.metric("🌍 Search Area", "2.5 km²")

    with right_col:
        st.subheader("📸 Live Detection Feed")
        data = get_latest_data()
        if data:
            current_analysis = data.get('current_analysis', {})
            if 'image_data' in current_analysis:
                display_image(current_analysis['image_data'])
            
        # Status information
        st.subheader("Status")
        if data:
            st.write("Last Update:", time.strftime('%Y-%m-%d %H:%M:%S'))
            st.write("Humans Detected:", current_analysis.get('humans_detected', 0))
            st.write("Safety Status:", current_analysis.get('safety_status', 'Unknown'))

if __name__ == "__main__":
    main()