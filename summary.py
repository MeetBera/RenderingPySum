import sys
import os
import glob
import re
import json
import shutil
import google.generativeai as genai
import yt_dlp

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
def configure_gemini():
    """Configures the Gemini API from Environment Variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ CRITICAL ERROR: GEMINI_API_KEY not found.", file=sys.stderr)
        print("   Please add it to your Render Dashboard under 'Environment'.", file=sys.stderr)
        sys.exit(1)
        
    genai.configure(api_key=api_key)

# ---------------------------------------------------------
# RENDER SPECIFIC: Cookie Handling
# ---------------------------------------------------------
def get_cookie_file():
    """
    Handles Render's read-only secret file system.
    Copies the cookie file to a writable /tmp directory if needed.
    """
    secret_cookie = "/etc/secrets/youtube.com_cookies.txt"
    local_cookie = "/tmp/youtube_cookies.txt"

    # 1. Production: Copy from Secret -> Tmp
    if os.path.exists(secret_cookie):
        try:
            shutil.copy(secret_cookie, local_cookie)
            print("🍪 Cookies loaded from Render secrets.", file=sys.stderr)
            return local_cookie
        except Exception as e:
            print(f"⚠️ Cookie copy warning: {e}", file=sys.stderr)
            return secret_cookie # Fallback to read-only path

    # 2. Local Testing: Look in current folder
    if os.path.exists("youtube.com_cookies.txt"):
        print("🍪 Cookies loaded from local file.", file=sys.stderr)
        return "youtube.com_cookies.txt"

    print("⚠️ No cookie file found. Some videos may fail.", file=sys.stderr)
    return None

# ---------------------------------------------------------
# UTILITY: Clean VTT
# ---------------------------------------------------------
def clean_vtt_text(vtt_content):
    """Parses raw VTT content into clean, readable text."""
    lines = vtt_content.splitlines()
    clean_lines = []
    seen = set()
    
    for line in lines:
        # Skip metadata, timestamps, and empty lines
        if "WEBVTT" in line or "-->" in line or line.strip().isdigit() or not line.strip():
            continue
        
        # Remove HTML-like tags (e.g., <c.colorE5E5E5>)
        line = re.sub(r'<[^>]+>', '', line).strip()
        
        # Remove duplicate consecutive lines (common in auto-captions)
        if line and line not in seen:
            seen.add(line)
            clean_lines.append(line)
            
    return " ".join(clean_lines)

# ---------------------------------------------------------
# STRATEGY 1: Smart Subtitles (Optimized)
# ---------------------------------------------------------
def get_transcript_from_subs(url):
    temp_dir = "/tmp/subs" if os.name != 'nt' else "temp_subs"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    cookie_file = get_cookie_file()
    
    # Configuration to prioritize English -> Hindi -> Auto-generated
    opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        # Prioritize manual English, then manual Hindi, then Auto English
        'subtitleslangs': ['en', 'en-US', 'hi', 'en-orig', 'en.*'], 
        'subtitlesformat': 'vtt',
        'outtmpl': os.path.join(temp_dir, '%(id)s'), 
        'quiet': True,
        'no_warnings': True,
    }

    if cookie_file:
        opts['cookiefile'] = cookie_file

    title = "Unknown Title"
    desc = ""
    video_id = ""

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'No Title')
            desc = info.get('description', '')
            video_id = info.get('id')

        # Find the downloaded VTT file
        files = glob.glob(os.path.join(temp_dir, "*.vtt"))
        
        if files:
            # Sort by size (larger usually means more complete subtitles)
            files.sort(key=os.path.getsize, reverse=True)
            with open(files[0], 'r', encoding='utf-8') as f:
                clean_text = clean_vtt_text(f.read())
            
            # Cleanup
            try: shutil.rmtree(temp_dir)
            except: pass
            
            return clean_text, title, desc
            
    except Exception as e:
        print(f"⚠️ Subtitle Download Error: {e}", file=sys.stderr)
    
    # Cleanup on failure
    try: shutil.rmtree(temp_dir)
    except: pass
    
    return None, None, None

# ---------------------------------------------------------
# GEMINI GENERATION
# ---------------------------------------------------------
def explain_with_gemini(transcript, title="", description=""):
    # Updated to a valid, stable model
    model = genai.GenerativeModel("gemini-2.5-flash-lite") 
    
    # 1.5 Flash has a large context window, but we limit to ~100k chars for safety/cost
    safe_transcript = transcript[:100000] 
    
    prompt = f"""
    You are a product-quality note designer.

    Your task:
    Turn this video transcript into **beautiful, human-friendly notes** that feel
    carefully written for real users.

    Tone & Care:
    - Write as if you genuinely care about the reader
    - Make it calm, helpful, and easy to scan
    - Assume the reader may be tired or busy

    Formatting Rules:
    - Use **bold** for important ideas
    - Use *italic* for emphasis or clarification
    - Use short sections with clear spacing
    - Avoid heavy Markdown (no ## headings)
    - Use light symbols (→, •) only if helpful
    - No code blocks

    Content Style:
    - Explain ideas simply, not academically
    - Highlight *why something matters*
    - Reduce clutter and repetition
    - Make it feel like well-crafted product notes.
    
    Title: {title}
    Description Snippet: {description[:500]}
    
    Transcript: 
    {safe_transcript}
    
    OUTPUT FORMAT:
    ## Summary
    (A concise summary of the video content)
    
    ## Key Points
    - (Bulleted list of main takeaways)
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating summary: {str(e)}"

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No URL provided"}), file=sys.stderr)
        return

    url = sys.argv[1]
    configure_gemini()

    print(f"🚀 Processing: {url}", file=sys.stderr)
    
    # 1. Get Transcript
    transcript, title, desc = get_transcript_from_subs(url)
    
    if transcript:
        print("✅ Transcript acquired. Sending to Gemini...", file=sys.stderr)
        
        # 2. Generate Summary
        summary = explain_with_gemini(transcript, title, desc)
        
        # Output JSON for the calling application (Node.js/Python)
        print(json.dumps({
            "summary": summary,
            "title": title,
            "method": "subtitles_clean"
        }))
    else:
        print(json.dumps({
            "error": "Could not retrieve subtitles. Video might lack captions or cookies are invalid."
        }))
        sys.exit(1)

if __name__ == "__main__":
    main()

# import sys
# import os
# import time
# import shutil
# import gc
# import glob
# import re
# import google.generativeai as genai
# import yt_dlp
# import mimetypes
# import json

# # ---------------------------------------------------------
# # GEMINI CONFIG
# # ---------------------------------------------------------
# def configure_gemini():
#     api_key = os.getenv("GEMINI_API_KEY")
#     if api_key:
#         genai.configure(api_key=api_key)

# # ---------------------------------------------------------
# # CLEAN VTT (Token Saver)
# # ---------------------------------------------------------
# def clean_vtt_text(vtt_content):
#     lines = vtt_content.splitlines()
#     clean_lines = []
#     seen = set()

#     for line in lines:
#         if "WEBVTT" in line or "-->" in line or line.strip().isdigit() or not line.strip():
#             continue
#         line = re.sub(r'<[^>]+>', '', line).strip()
#         if line and line not in seen:
#             seen.add(line)
#             clean_lines.append(line)

#     return " ".join(clean_lines)


# # ---------------------------------------------------------
# # FIXED COOKIE HANDLING (mandatory)
# # ---------------------------------------------------------
# def get_cookie_file():
#     secret_cookie = "/etc/secrets/youtube.com_cookies.txt"
#     local_cookie = "/tmp/youtube_cookies.txt"

#     # 1. Try to use the Read-Only secret file
#     if os.path.exists(secret_cookie):
#         try:
#             # Try to copy it to a writable location (Best Case)
#             shutil.copy(secret_cookie, local_cookie)
#             return local_cookie
#         except:
#             # Fallback: Return the read-only path if copy fails
#             # yt-dlp might warn about writing, but Auth should still work
#             return secret_cookie 

#     # 2. Local fallback for testing
#     if os.path.exists("youtube.com_cookies.txt"):
#         return "youtube.com_cookies.txt"

#     return None


# # ---------------------------------------------------------
# # FAST TRACK: Subtitles
# # ---------------------------------------------------------
# def get_transcript_from_subs(url):
#     temp_dir = "/tmp"

#     # Cleanup old VTT files
#     for f in glob.glob(os.path.join(temp_dir, "*.vtt")):
#         try: os.remove(f)
#         except: pass

#     cookie_file = get_cookie_file()

#     opts = {
#         'skip_download': True,
#         'writesubtitles': True,
#         'writeautomaticsub': True,
#         'subtitlesformat': 'vtt',
#         'outtmpl': os.path.join(temp_dir, '%(id)s'),
#         'quiet': True,
#         'no_warnings': True,
#         'cookiefile': cookie_file
#     }

#     try:
#         with yt_dlp.YoutubeDL(opts) as ydl:
#             info = ydl.extract_info(url, download=True)
#             video_id = info.get('id')
#             title = info.get('title', 'No Title')
#             desc = info.get('description', '')

#         vtt_files = glob.glob(os.path.join(temp_dir, f"{video_id}*.vtt"))

#         if vtt_files:
#             sub_path = vtt_files[0]
#             for p in vtt_files:
#                 if ".en" in p:
#                     sub_path = p
#                     break

#             print(f"✅ Found subtitles: {sub_path}", file=sys.stderr)

#             raw = open(sub_path, "r", encoding="utf-8").read()
#             clean = clean_vtt_text(raw)

#             try: os.remove(sub_path)
#             except: pass

#             return clean, title, desc

#     except Exception as e:
#         print(f"⚠️ Subtitle fetch failed: {e}", file=sys.stderr)

#     return None, None, None


# # ---------------------------------------------------------
# # SLOW TRACK: AUDIO DOWNLOAD
# # ---------------------------------------------------------
# def download_audio(url):
#     temp_dir = "/tmp"
#     audio_template = os.path.join(temp_dir, "audio_%(id)s.%(ext)s")

#     cookie_file = get_cookie_file()

#     opts = {
#         "quiet": True,
#         "no_warnings": True,
#         "cookiefile": cookie_file,
#         "format": "worst/bestaudio",
#         "outtmpl": audio_template,
#     }

#     try:
#         with yt_dlp.YoutubeDL(opts) as ydl:
#             info = ydl.extract_info(url, download=True)
#             video_id = info.get("id")
#             title = info.get("title", "No Title")
#             desc = info.get("description", "")
#             ext = info.get("ext")

#         del info
#         gc.collect()

#         final_path = os.path.join(temp_dir, f"audio_{video_id}.{ext}")

#         if not os.path.exists(final_path):
#             for f in os.listdir(temp_dir):
#                 if f.startswith(f"audio_{video_id}"):
#                     final_path = os.path.join(temp_dir, f)
#                     break

#         if os.path.exists(final_path):
#             return final_path, title, desc

#         return None, None, None

#     except Exception as e:
#         print(f"❌ Audio download failed: {e}", file=sys.stderr)
#         return None, None, None


# # ---------------------------------------------------------
# # AI: TRANSCRIBE AUDIO
# # ---------------------------------------------------------
# def transcribe_with_gemini(audio_path):
#     print(f"Uploading: {audio_path}", file=sys.stderr)

#     mime, _ = mimetypes.guess_type(audio_path)
#     if not mime:
#         ext = audio_path.split(".")[-1].lower()
#         mime = {
#             "m4a": "audio/mp4",
#             "webm": "audio/webm",
#             "mp3": "audio/mp3",
#             "opus": "audio/ogg",
#         }.get(ext, "audio/mp3")

#     audio_file = genai.upload_file(audio_path, mime_type=mime)

#     while audio_file.state.name == "PROCESSING":
#         time.sleep(1)
#         audio_file = genai.get_file(audio_file.name)

#     if audio_file.state.name == "FAILED":
#         raise ValueError("Gemini audio processing failed")

#     model = genai.GenerativeModel("gemini-2.5-flash")

#     response = model.generate_content([audio_file, "Transcribe this audio."])

#     try: genai.delete_file(audio_file.name)
#     except: pass

#     return response.text


# # ---------------------------------------------------------
# # AI: SUMMARIZE
# # ---------------------------------------------------------
# def explain_with_gemini(transcript, title="", description=""):
#     model = genai.GenerativeModel("gemini-2.5-flash")

#     safe_text = transcript[:30000]

#     prompt = f"""
# You are an intelligent summarizer. Summarize this YouTube video.

# Title: {title}
# Description: {description[:500]}

# Transcript:
# {safe_text}

# OUTPUT FORMAT:
# ## Summary
# (text)

# ## Key Points
# - point 1
# - point 2
# - point 3
# """

#     response = model.generate_content(prompt)
#     return response.text


# # ---------------------------------------------------------
# # MAIN
# # ---------------------------------------------------------
# def main():
#     if len(sys.argv) < 2:
#         print("Error: No URL provided", file=sys.stderr)
#         return

#     url = sys.argv[1]
#     configure_gemini()

#     print("🚀 Attempting Fast Track (Subtitles)...", file=sys.stderr)
#     transcript, title, desc = get_transcript_from_subs(url)

#     if transcript:
#         print("✅ Subtitles found! Generating summary...", file=sys.stderr)
#         summary = explain_with_gemini(transcript, title, desc)
#         print(json.dumps({
#             "summary": summary,
#             "title": title,
#             "method": "subtitles_clean"
#         }))
#         return

#     print("⚠️ No subtitles found. Falling back to Audio (Slow)...", file=sys.stderr)
#     audio_path, title, desc = download_audio(url)

#     if not audio_path:
#         print("Error: Audio download failed", file=sys.stderr)
#         sys.exit(1)

#     transcript = transcribe_with_gemini(audio_path)
#     summary = explain_with_gemini(transcript, title, desc)

#     if os.path.exists(audio_path):
#         os.remove(audio_path)

#     print(json.dumps({
#         "summary": summary,
#         "title": title,
#         "method": "audio_slow"
#     }))


# if __name__ == "__main__":
#     main()
