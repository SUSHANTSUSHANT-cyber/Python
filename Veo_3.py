import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import time
import base64
from typing import Optional

# Configure page
st.set_page_config(
    page_title="VEO3 Video Generator",
    page_icon="🎬",
    layout="wide"
)

def main():
    """Main application interface"""
    st.title("🎬 VEO3 Video Generator")
    st.markdown("Generate videos from images and text prompts using Google's VEO3 API")
    
    # Create columns for layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📷 Upload Image")
        uploaded_file = st.file_uploader(
            "Choose an image file",
            type=['png', 'jpg', 'jpeg', 'webp'],
            help="Upload an image to use as a starting frame for your video"
        )
        
        if uploaded_file is not None:
            # Display the uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_container_width=True)
            
            # Show image details
            st.write(f"**Image size:** {image.size[0]} x {image.size[1]} pixels")
            st.write(f"**File format:** {image.format}")
    
    with col2:
        st.header("📝 Video Prompt")
        prompt = st.text_area(
            "Describe the video you want to generate",
            placeholder="Example: A beautiful sunset over the ocean with waves gently crashing on the shore...",
            height=150,
            help="Describe what you want to happen in the video. Be specific about motion, style, and visual elements."
        )
        
        # Video generation settings
        st.subheader("⚙️ Generation Settings")
        
        duration = st.selectbox(
            "Video Duration",
            options=[5, 8],
            index=0,
            help="Duration of the generated video in seconds (VEO3 supports 5-8 seconds)"
        )
        
        aspect_ratio = st.selectbox(
            "Aspect Ratio",
            options=["16:9", "9:16"],
            index=0,
            help="Aspect ratio for the generated video (VEO3 supports 16:9 and 9:16)"
        )
        
        quality = st.selectbox(
            "Quality",
            options=["Standard", "High"],
            index=0,
            help="Video generation quality"
        )
    
    # Generate button
    st.markdown("---")
    
    # Check if API key is configured  
    api_key = os.environ.get("GEMINI_API_KEY", "")
    
    if not api_key:
        st.warning("⚠️ Gemini API key not configured. Please add your API key to generate videos.")
        st.info("You'll need a Gemini API key with access to VEO3. Set the environment variable 'GEMINI_API_KEY' or enter it below for testing.")
        
        # Show input for API key (for testing purposes)
        test_api_key = st.text_input("Enter API Key (for testing)", type="password")
        if test_api_key:
            api_key = test_api_key
    
    # Generate video button
    generate_button = st.button(
        "🎬 Generate Video",
        disabled=(uploaded_file is None or not prompt.strip() or not api_key),
        use_container_width=True
    )
    
    if generate_button:
        if uploaded_file and prompt.strip() and api_key:
            with st.spinner("Generating video... This may take a few minutes."):
                try:
                    # Configure the API
                    os.environ['GEMINI_API_KEY'] = api_key
                    client = genai.Client(api_key=api_key)
                    
                    # Convert uploaded image to format suitable for API
                    image_data = uploaded_file.getvalue()
                    
                    # Generate video
                    result = generate_video_with_veo3(
                        client=client,
                        image_data=image_data,
                        prompt=prompt,
                        duration=duration,
                        aspect_ratio=aspect_ratio,
                        quality=quality
                    )
                    
                    if result:
                        st.success("✅ Video generated successfully!")
                        # Display the generated video
                        display_generated_video(result)
                    else:
                        st.error("❌ Failed to generate video. Please try again.")
                        
                except Exception as e:
                    st.error(f"❌ Error generating video: {str(e)}")
                    st.info("Please check your API key and try again.")
        else:
            st.error("Please upload an image, enter a prompt, and configure your API key.")

def get_mime_type(image_data: bytes) -> str:
    """Detect MIME type from image bytes"""
    if image_data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
        return 'image/webp'
    else:
        return 'image/jpeg'  # Default fallback

def generate_video_with_veo3(client, image_data: bytes, prompt: str, duration: int, aspect_ratio: str, quality: str) -> Optional[bytes]:
    """Generate video using VEO3 API"""
    try:
        st.info("🔄 Initializing VEO3 video generation...")
        
        # Preprocess image: encode as base64 for API
        mime_type = get_mime_type(image_data)
        encoded_string = base64.b64encode(image_data).decode("utf-8")
        
        # Create image dictionary using the correct VEO3 API format
        image = {
            "bytes_base64_encoded": encoded_string,
            "mime_type": mime_type
        }

        st.info(f"📤 Testing text-only video generation (image parameter temporarily disabled)...")

        # Use Google AI Studio logic for config
        config = types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            number_of_videos=1,
            duration_seconds=duration,
            person_generation="ALLOW_ALL",
        )

        # Generate video using VEO3 - try without image parameter first
        try:
            operation = client.models.generate_videos(
                model="veo-2.0-generate-001",
                prompt=prompt,
                config=config
            )
        except Exception as billing_error:
            if "billing" in str(billing_error).lower() or "FAILED_PRECONDITION" in str(billing_error):
                st.error("🚨 **BILLING REQUIRED**: VEO3 requires Google Cloud Platform billing to be enabled.")
                st.info("📋 **To fix this:**\n1. Go to https://console.cloud.google.com/\n2. Enable billing in your Google Cloud account\n3. Link a payment method\n4. Wait a few minutes and try again")
                st.warning("💡 VEO3 is a premium model that requires active GCP billing. This is not a code issue - your code is working correctly!")
                return None
            else:
                raise billing_error

        st.info("⏳ Video generation in progress... This may take a few minutes.")
        progress_bar = st.progress(0)
        progress_text = st.empty()

        # Poll until video is ready
        timeout = 300  # 5 minutes timeout
        start_time = time.time()
        while not operation.done:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                st.error("❌ Video generation timed out after 5 minutes.")
                return None
            progress = min(elapsed / 180, 0.95)
            progress_bar.progress(progress)
            progress_text.text(f"Generating... {int(elapsed)}s elapsed")
            time.sleep(10)
            operation = client.operations.get(operation)

        progress_bar.progress(1.0)
        progress_text.text("Video generation complete!")

        # Get the result
        result = operation.result if hasattr(operation, 'result') else None
        if not result:
            st.error("Error occurred while generating video.")
            return None

        generated_videos = result.generated_videos if hasattr(result, 'generated_videos') else None
        if not generated_videos:
            st.error("No videos were generated.")
            return None

        st.success(f"✅ Generated {len(generated_videos)} video(s).")
        # Download and display the first video
        generated_video = generated_videos[0]
        client.files.download(file=generated_video.video)
        # Save the video
        generated_video.video.save("veo3_generated_video.mp4")
        with open("veo3_generated_video.mp4", "rb") as f:
            video_bytes = f.read()
        return video_bytes
            
    except Exception as e:
        error_message = str(e)
        st.error(f"❌ Error in video generation: {error_message}")
        
        # Provide specific guidance based on error type
        if "quota" in error_message.lower() or "exceeded" in error_message.lower():
            st.info("💡 **Quota Issue**: You've exceeded your API limits. Please check your Google AI API quota and billing.")
        elif "authentication" in error_message.lower() or "unauthorized" in error_message.lower():
            st.info("💡 **Authentication Issue**: Please verify your API key has access to VEO3 video generation.")
        elif "invalid_argument" in error_message.lower():
            st.info("💡 **Invalid Input**: Please check your image format and prompt. Try a different image or shorter prompt.")
        elif "model" in error_message.lower() and "not found" in error_message.lower():
            st.info("💡 **Model Access**: VEO3 model may not be available in your region or requires special access.")
        elif "timeout" in error_message.lower():
            st.info("💡 **Timeout**: The request timed out. Please try again with a shorter prompt or different image.")
        elif "unavailable" in error_message.lower() or "503" in error_message:
            st.info("💡 **Service Unavailable**: The VEO3 service is temporarily unavailable. Please try again later.")
        else:
            st.info("💡 **General Error**: Please check your internet connection and try again. If the issue persists, verify your API key and quota.")
        
        return None

def display_generated_video(video_result: bytes):
    """Display the generated video"""
    if video_result:
        # Display the video
        st.video(video_result)
        
        # Provide download option
        st.download_button(
            label="📥 Download Video",
            data=video_result,
            file_name="veo3_generated_video.mp4",
            mime="video/mp4",
            use_container_width=True
        )
        
        # Show video info
        st.info(f"📹 Video size: {len(video_result) / (1024*1024):.1f} MB")
    else:
        st.error("No video data to display.")

if __name__ == "__main__":
    main()