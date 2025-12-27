import sys
import os
import glob
import re
import json
import shutil
import contextlib
import time
import gc
import mimetypes
import google.generativeai as genai
import yt_dlp

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
def configure_gemini():
    # STRICT SECURITY: Only use Environment Variable
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ CRITICAL ERROR: GEMINI_API_KEY not found in environment variables.", file=sys.stderr)
        print("   Please add it to your Render Dashboard under 'Environment'.", file=sys.stderr)
        sys.exit(1)
        
    genai.configure(api_key=api_key)

# ---------------------------------------------------------
# RENDER SPECIFIC: Cookie Handling
# ---------------------------------------------------------
def get_cookie_file():
    """
    Render stores secrets in /etc/secrets/ which is Read-Only.
    yt-dlp often needs to write to the cookie file or gets permission denied.
    We copy the secret cookie to /tmp (which is writable) to fix this.
    """
    secret_cookie = "/etc/secrets/youtube.com_cookies.txt"
    local_cookie = "/tmp/youtube_cookies.txt"

    # 1. Production: Copy from Secret -> Tmp
    if os.path.exists(secret_cookie):
        try:
            shutil.copy(secret_cookie, local_cookie)
            print(f"🍪 Cookies loaded from Render secrets.", file=sys.stderr)
            return local_cookie
        except Exception as e:
            print(f"⚠️ Cookie copy failed: {e}", file=sys.stderr)
            return secret_cookie # Fallback to read-only path

    # 2. Local Testing: Look in current folder
    if os.path.exists("youtube.com_cookies.txt"):
        return "youtube.com_cookies.txt"

    return None

# ---------------------------------------------------------
# UTILITY: Clean VTT
# ---------------------------------------------------------
def clean_vtt_text(vtt_content):
    lines = vtt_content.splitlines()
    clean_lines = []
    seen = set()
    for line in lines:
        if "WEBVTT" in line or "-->" in line or line.strip().isdigit() or not line.strip():
            continue
        line = re.sub(r'<[^>]+>', '', line).strip()
        if line and line not in seen:
            seen.add(line)
            clean_lines.append(line)
    return " ".join(clean_lines)

# ---------------------------------------------------------
# STRATEGY 1: Smart Subtitles (Fast)
# ---------------------------------------------------------
def get_transcript_from_subs(url):
    temp_dir = "/tmp/subs" if os.name != 'nt' else "temp_subs"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    # Cleanup
    for f in glob.glob(os.path.join(temp_dir, "*.vtt")):
        try: os.remove(f)
        except: pass

    cookie_file = get_cookie_file()
    
    # 1. Fetch Metadata to choose language
    target_lang = 'en.*' 
    try:
        opts_meta = {'skip_download': True, 'quiet': True, 'no_warnings': True, 'cookiefile': cookie_file}
        with yt_dlp.YoutubeDL(opts_meta) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get('id')
            title = info.get('title', 'No Title')
            desc = info.get('description', '')
            
            # Logic to pick best subtitle
            subs = list(info.get('subtitles', {}).keys())
            auto = list(info.get('automatic_captions', {}).keys())
            all_langs = set(subs + auto)
            
            if any(l.startswith('en') for l in all_langs):
                target_lang = 'en.*'
            elif any(l.startswith('hi') for l in all_langs):
                target_lang = 'hi.*'
            elif auto:
                target_lang = auto[0]
            else:
                return None, None, None # No subs available
                
    except Exception as e:
        print(f"⚠️ Metadata Error: {e}", file=sys.stderr)
        return None, None, None

    # 2. Download Specific Language
    opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [target_lang],
        'subtitlesformat': 'vtt',
        'outtmpl': os.path.join(temp_dir, '%(id)s'), 
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_file
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        files = glob.glob(os.path.join(temp_dir, f"{video_id}*.vtt"))
        if files:
            with open(files[0], 'r', encoding='utf-8') as f:
                clean = clean_vtt_text(f.read())
            try: shutil.rmtree(temp_dir)
            except: pass
            return clean, title, desc
            
    except Exception as e:
        print(f"⚠️ Subtitle Download Error: {e}", file=sys.stderr)
    
    return None, None, None

# ---------------------------------------------------------
# STRATEGY 2: Audio Download (Slow Fallback)
# ---------------------------------------------------------
def download_audio(url):
    temp_dir = "/tmp" if os.name != 'nt' else os.getcwd()
    audio_template = os.path.join(temp_dir, "audio_%(id)s.%(ext)s")
    cookie_file = get_cookie_file()

    opts = {
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
        "format": "worst/bestaudio", # Save space
        "outtmpl": audio_template,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")
            title = info.get("title", "No Title")
            desc = info.get("description", "")
            ext = info.get("ext")
        
        gc.collect() # Force memory cleanup
        
        final_path = os.path.join(temp_dir, f"audio_{video_id}.{ext}")
        
        # Double check file existence (names can vary)
        if not os.path.exists(final_path):
            for f in os.listdir(temp_dir):
                if f.startswith(f"audio_{video_id}"):
                    final_path = os.path.join(temp_dir, f)
                    break
        
        if os.path.exists(final_path):
            return final_path, title, desc
            
    except Exception as e:
        print(f"❌ Audio Download Error: {e}", file=sys.stderr)
        
    return None, None, None

def explain_with_gemini(transcript, title="", description=""):
    model = genai.GenerativeModel("gemini-2.5-flash") # Or 1.5-pro
    safe_transcript = transcript[:30000] # Token safety
    
    prompt = f"""
    You are a product-quality note designer.
    Turn this video transcript into **beautiful, human-friendly notes**.
    
    Tone: Calm, helpful, easy to scan.
    Formatting: 
    - Use **bold** for key ideas.
    - No Markdown headers (##).
    - No code blocks.
    
    Title: {title}
    Description: {description[:500]}
    
    Transcript: 
    {safe_transcript}
    
    OUTPUT FORMAT:
    ## Summary
    (Concise summary)
    
    ## Key Points
    - (Bulleted list)
    """
    
    response = model.generate_content(prompt)
    return response.text

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Error: No URL provided", file=sys.stderr)
        return

    url = sys.argv[1]
    configure_gemini()

    # 1. Try Subtitles
    print("🚀 Strategy 1: Subtitles...", file=sys.stderr)
    transcript, title, desc = get_transcript_from_subs(url)
    method = "subtitles_clean"

    # 2. Try Audio if Subtitles fail
    if not transcript:
        print("⚠️ Subtitles failed. Strategy 2: Audio Download...", file=sys.stderr)
        audio_path, title, desc = download_audio(url)
        
        if audio_path:
            try:
                transcript = transcribe_with_gemini(audio_path)
                method = "audio_slow"
            except Exception as e:
                print(f"❌ Transcription failed: {e}", file=sys.stderr)
            finally:
                if os.path.exists(audio_path):
                    os.remove(audio_path)

    # 3. Generate Summary
    if transcript:
        print("✅ Transcript acquired. Generating summary...", file=sys.stderr)
        try:
            summary = explain_with_gemini(transcript, title, desc)
            # Remove line separators that break JSON
            summary = summary.replace("\u2028", "").replace("\u2029", "")
            
            print(json.dumps({
                "summary": summary,
                "title": title,
                "method": method
            }))
        except Exception as e:
            print(f"Gemini API Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("❌ FATAL: Could not get transcript from Subtitles or Audio.", file=sys.stderr)
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
