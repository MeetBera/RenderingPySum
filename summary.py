import sys
import os
import time
import shutil  # Add this import at the top
import google.generativeai as genai
import yt_dlp

# Configure Gemini
def configure_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)


def download_audio(url):
    # Render/Linux uses /tmp.
    temp_dir = "/tmp"
    audio_path_template = os.path.join(temp_dir, "audio_%(id)s.%(ext)s")

    # 1. DEFINE SOURCE AND DESTINATION FOR COOKIES
    # The read-only secret file provided by Render
    secret_cookie_path = "/etc/secrets/youtube.com_cookies.txt"
    # A writable location in temp
    temp_cookie_path = os.path.join(temp_dir, "youtube_cookies.txt")

    # 2. COPY THE COOKIE FILE TO TEMP (To avoid Read-Only errors)
    final_cookie_path = None
    
    if os.path.exists(secret_cookie_path):
        try:
            # Copy secret file to /tmp so yt-dlp can write/lock if it needs to
            shutil.copy(secret_cookie_path, temp_cookie_path)
            final_cookie_path = temp_cookie_path
            print(f"✅ Cookies copied to writable temp: {final_cookie_path}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Could not copy cookies: {e}", file=sys.stderr)
            # Fallback to secret path (might fail if yt-dlp tries to write)
            final_cookie_path = secret_cookie_path
    else:
        # Fallback for local testing
        if os.path.exists("youtube.com_cookies.txt"):
            final_cookie_path = "youtube.com_cookies.txt"
        else:
            print(f"❌ COOKIE FILE NOT FOUND AT: {secret_cookie_path}", file=sys.stderr)

    ydl_opts = {
        "quiet": True, 
        "no_warnings": True,
        "cookiefile": final_cookie_path, # Use the writable temp path
        "format": "bestaudio/best",
        "outtmpl": audio_path_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128", 
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id')
            final_path = os.path.join(temp_dir, f"audio_{video_id}.mp3")
            
            if os.path.exists(final_path):
                # Return the 3 values expected
                return final_path, info.get('title', 'No Title'), info.get('description', '')
            
            return None, None, None

    except Exception as e:
        print(f"❌ Audio download failed: {e}", file=sys.stderr)
        return None, None, None

def transcribe_with_gemini(audio_path):
    print("Uploading file to Gemini...")
    # 1. Upload the file using the File API (Better for large files)
    audio_file = genai.upload_file(audio_path, mime_type="audio/mp3")
    
    # 2. Wait for processing (File API is async for processing)
    while audio_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        audio_file = genai.get_file(audio_file.name)

    if audio_file.state.name == "FAILED":
        raise ValueError("Audio processing failed by Gemini")

    print("\nGenerating transcript...")
    # 3. Use the correct model name
    model = genai.GenerativeModel("gemini-1.5-flash") 
    
    response = model.generate_content([
        audio_file,
        "Transcribe this audio accurately in English. Ignore background noise."
    ])
    
    # Cleanup: Delete file from Gemini cloud storage to save quota
    # (Optional but recommended)
    # genai.delete_file(audio_file.name) 
    
    return response.text

def explain_with_gemini(transcript, title="", description=""):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
    You are an intelligent API. Explain the given YouTube transcript in clear, factual English.
    
    Title: {title}
    Description Snippet: {description[:500]}
    
    Transcript: 
    {transcript}
    
    OUTPUT FORMAT:
    ## Summary
    (A concise summary)
    
    ## Key Points
    - (Bullet points)
    """
    response = model.generate_content(prompt)
    return response.text

# --- MAIN EXECUTION BLOCK (Example usage) ---
if __name__ == "__main__":
    # You can test it directly here
    configure_gemini()
    
    # Example URL
    test_url = "YOUR_YOUTUBE_URL_HERE" 
    
    path, vid_title, vid_desc = download_audio(test_url)
    
    if path:
        print(f"Downloaded: {vid_title}")
        try:
            transcription = transcribe_with_gemini(path)
            print("Transcription complete.")
            summary = explain_with_gemini(transcription, vid_title, vid_desc)
            print(summary)
            
            # Cleanup local file
            os.remove(path)
        except Exception as e:
            print(f"AI Error: {e}")
    else:
        print("Download failed.")
