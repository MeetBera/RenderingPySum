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
    audio_path_template = os.path.join(temp_dir, "audio_%(id)s.%(ext)s")

    # COOKIE SETUP
    secret_cookie_path = "/etc/secrets/youtube.com_cookies.txt"
    temp_cookie_path = os.path.join(temp_dir, "youtube_cookies.txt")
    final_cookie_path = None
    
    if os.path.exists(secret_cookie_path):
        try:
            shutil.copy(secret_cookie_path, temp_cookie_path)
            final_cookie_path = temp_cookie_path
            print(f"✅ Cookies copied to writable temp: {final_cookie_path}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Could not copy cookies: {e}", file=sys.stderr)
            final_cookie_path = secret_cookie_path
    else:
        if os.path.exists("youtube.com_cookies.txt"):
            final_cookie_path = "youtube.com_cookies.txt"

    # NO FFMPEG ANYMORE
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "cookiefile": final_cookie_path,
        "format": "bestaudio/best",       # yt-dlp will download native audio (webm/m4a)
        "outtmpl": audio_path_template,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info.get("id")
                title = info.get("title", "No Title")
                description = info.get("description", "")


        # Aggressive memory cleanup
        del info
        gc.collect()

        # NEW FINAL PATH LOGIC (detect webm/m4a/mp3)
        downloaded_file = None
        for ext in ("webm", "m4a", "mp3"):
            candidate = os.path.join(temp_dir, f"audio_{video_id}.{ext}")
            if os.path.exists(candidate):
                downloaded_file = candidate
                break

        if downloaded_file:
            return downloaded_file, title, description

        return None, None, None

    except Exception as e:
        print(f"❌ Audio download failed: {e}", file=sys.stderr)
        return None, None, None
        


def transcribe_with_gemini(audio_path):
    print(f"Uploading file {audio_path} to Gemini...")

    # 1. Robust MIME detection (Fixes the "Internal Server Error" / 500 issue)
    mime, _ = mimetypes.guess_type(audio_path)
    if not mime:
        ext = audio_path.split(".")[-1].lower()
        if ext == "webm":
            mime = "audio/webm"
        elif ext == "m4a":
            mime = "audio/mp4"
        elif ext == "mp3":
            mime = "audio/mp3"
        else:
            mime = "audio/mp3" # Safe fallback

    print(f"Detected MIME type: {mime}")

    # 2. Upload file
    audio_file = genai.upload_file(audio_path, mime_type=mime)

    # 3. Wait for processing
    while audio_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(1)
        audio_file = genai.get_file(audio_file.name)

    if audio_file.state.name == "FAILED":
        print(f"\n❌ Gemini failed to process file. State: {audio_file.state.name}")
        raise ValueError("Audio processing failed by Gemini")

    print("\nGenerating transcript...")
    
    # ✅ REVERTED TO YOUR MODEL (You were right!)
    model = genai.GenerativeModel("gemini-2.5-flash") 

    try:
        response = model.generate_content([
            audio_file,
            "Transcribe this audio accurately in English. Ignore background noise."
        ])
        
        if not response.text:
            raise ValueError("Gemini returned an empty response.")
            
        return response.text

    except Exception as e:
        print(f"Transcription Error: {e}")
        raise e


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
    try:
        genai.delete_file(audio_file.name)
    except Exception:
        pass
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
            if path and os.path.exists(path):
                os.remove(path)

        except Exception as e:
            print(f"AI Error: {e}")
    else:
        print("Download failed.")
