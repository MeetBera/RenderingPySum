import sys
import os
import time
import shutil 
import gc  # <--- [FIX 1] Import Garbage Collection
import google.generativeai as genai
import yt_dlp
import mimetypes

# Configure Gemini
def configure_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)

def download_audio(url):
    temp_dir = "/tmp"
    # We remove the specific extension from the template so yt-dlp can use the real one
    audio_path_template = os.path.join(temp_dir, "audio_%(id)s.%(ext)s")

    # COOKIE SETUP
    secret_cookie_path = "/etc/secrets/youtube.com_cookies.txt"
    temp_cookie_path = os.path.join(temp_dir, "youtube_cookies.txt")
    final_cookie_path = None
    
    if os.path.exists(secret_cookie_path):
        try:
            shutil.copy(secret_cookie_path, temp_cookie_path)
            final_cookie_path = temp_cookie_path
        except Exception:
            final_cookie_path = secret_cookie_path
    elif os.path.exists("youtube.com_cookies.txt"):
        final_cookie_path = "youtube.com_cookies.txt"

    ydl_opts = {
        "quiet": True, 
        "no_warnings": True,
        "cookiefile": final_cookie_path,
        
        # KEY CHANGE 1: Request 'worst' quality audio directly.
        # This gets the smallest file possible (fastest download).
        # We REMOVED the 'postprocessors' block so no conversion happens.
        "format": "worst/bestaudio", 
        "outtmpl": audio_path_template,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")
            title = info.get("title", "No Title")
            description = info.get("description", "")
            
            # KEY CHANGE 2: Get the actual extension of the downloaded file
            # yt-dlp tells us exactly what extension it used
            ext = info.get('ext') 

        # Memory Cleanup
        del info
        gc.collect()

        # Construct the path using the extension we just learned
        final_path = os.path.join(temp_dir, f"audio_{video_id}.{ext}")

        if os.path.exists(final_path):
            return final_path, title, description
        
        # Fallback search if the extension logic failed for some reason
        # Look for any file starting with 'audio_VIDEOID'
        potential_files = [f for f in os.listdir(temp_dir) if f.startswith(f"audio_{video_id}")]
        if potential_files:
             return os.path.join(temp_dir, potential_files[0]), title, description

        print(f"❌ Error: File not found at {final_path}", file=sys.stderr)
        return None, None, None

    except Exception as e:
        print(f"❌ Audio download failed: {e}", file=sys.stderr)
        return None, None, None

    except Exception as e:
        print(f"❌ Audio download failed: {e}", file=sys.stderr)
        return None, None, None
    except Exception as e:
        print(f"❌ Audio download failed: {e}", file=sys.stderr)
        return None, None, None

def transcribe_with_gemini(audio_path):
    print(f"Uploading file {audio_path} to Gemini...")

    # 1. Enhanced MIME Detection (Handles raw YouTube formats)
    mime_type, _ = mimetypes.guess_type(audio_path)
    
    if not mime_type:
        ext = audio_path.split('.')[-1].lower()
        if ext == 'm4a':
            mime_type = 'audio/mp4'
        elif ext == 'webm':
            mime_type = 'audio/webm'
        elif ext == 'mp3':
            mime_type = 'audio/mp3'
        elif ext == 'opus' or ext == 'ogg':
            mime_type = 'audio/ogg'
        elif ext == 'wav':
            mime_type = 'audio/wav'
        else:
            mime_type = 'audio/mp3' # Last resort fallback

    print(f"Detected MIME type: {mime_type}")

    # 2. Upload file with correct MIME
    audio_file = genai.upload_file(audio_path, mime_type=mime_type)

    # 3. Wait for processing (Async)
    while audio_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(1)
        audio_file = genai.get_file(audio_file.name)

    if audio_file.state.name == "FAILED":
        print(f"\n❌ Gemini failed to process file. State: {audio_file.state.name}")
        raise ValueError("Audio processing failed by Gemini")

    print("\nGenerating transcript...")
    
    # Using your preferred model (gemini-2.5-flash)
    model = genai.GenerativeModel("gemini-2.5-flash") 

    try:
        response = model.generate_content([
            audio_file,
            "Transcribe this audio accurately in English. Ignore background noise."
        ])
        
        if not response.text:
            raise ValueError("Gemini returned an empty response.")
        
        # CLEANUP: Delete file from Gemini cloud to save quota
        try:
            genai.delete_file(audio_file.name)
            print("✅ Remote file deleted from Gemini")
        except Exception:
            pass

        return response.text

    except Exception as e:
        print(f"Transcription Error: {e}")
        raise e
def explain_with_gemini(transcript, title="", description=""):
    model = genai.GenerativeModel("gemini-2.5-flash")
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
    # [FIXED] Removed incorrect file deletion code here (moved to transcribe function)
    response = model.generate_content(prompt)
    return response.text

# --- MAIN EXECUTION BLOCK (Example usage) ---
if __name__ == "__main__":
    # You can test it directly here
    configure_gemini()
    
    # Example URL (Replace with real URL for testing)
    test_url = "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" 
    
    path, vid_title, vid_desc = download_audio(test_url)
    
    if path:
        print(f"Downloaded: {vid_title}")
        try:
            transcription = transcribe_with_gemini(path)
            print("Transcription complete.")
            summary = explain_with_gemini(transcription, vid_title, vid_desc)
            print(summary)
            
            # Cleanup local file
            if path and os.path.exists(path):
                os.remove(path)
                print("✅ Local file deleted")

        except Exception as e:
            print(f"AI Error: {e}")
    else:
        print("Download failed.")
