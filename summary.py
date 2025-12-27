import sys
import os
import glob
import re
import json
import shutil
import contextlib
import google.generativeai as genai
import yt_dlp

# =========================================================
# RENDER CONFIGURATION
# =========================================================

TMP_DIR = "/tmp"
COOKIE_SECRET_PATH = "/etc/secrets/youtube.com_cookies.txt"


def configure_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("❌ GEMINI_API_KEY not set in Render environment.", file=sys.stderr)
        sys.exit(1)

    genai.configure(api_key=api_key)


def get_cookie_file():
    """
    Render only:
    - Secrets are mounted at /etc/secrets
    - Copy to /tmp because /etc is read-only
    """
    if os.path.exists(COOKIE_SECRET_PATH):
        local_cookie = os.path.join(TMP_DIR, "youtube_cookies.txt")
        try:
            shutil.copy(COOKIE_SECRET_PATH, local_cookie)
            return local_cookie
        except Exception as e:
            print(f"⚠️ Cookie copy failed: {e}", file=sys.stderr)
            return None

    return None


# =========================================================
# UTILITY: CLEAN VTT (Token Optimization)
# =========================================================

def clean_vtt_text(vtt_content):
    lines = vtt_content.splitlines()
    clean_lines = []
    seen = set()

    for line in lines:
        if (
            "WEBVTT" in line
            or "-->" in line
            or line.strip().isdigit()
            or not line.strip()
        ):
            continue

        line = re.sub(r"<[^>]+>", "", line).strip()

        if line and line not in seen:
            seen.add(line)
            clean_lines.append(line)

    return " ".join(clean_lines)


# =========================================================
# SUBTITLE EXTRACTION (Render-Safe)
# =========================================================

def get_transcript_from_subs(url):
    os.makedirs(TMP_DIR, exist_ok=True)

    for f in glob.glob(os.path.join(TMP_DIR, "*.vtt")):
        try:
            os.remove(f)
        except:
            pass

    cookie_file = get_cookie_file()

    meta_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
    }

    target_lang = "en.*"

    try:
        with contextlib.redirect_stdout(open(os.devnull, "w")):
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)

        video_id = info["id"]
        title = info.get("title", "")
        desc = info.get("description", "")

        manual = info.get("subtitles", {}).keys()
        auto = info.get("automatic_captions", {}).keys()
        all_langs = set(manual) | set(auto)

        if any(l.startswith("en") for l in all_langs):
            target_lang = "en.*"
        elif any(l.startswith("hi") for l in all_langs):
            target_lang = "hi.*"
        elif auto:
            target_lang = list(auto)[0]
        else:
            return None, None, None

    except Exception as e:
        print(f"❌ Metadata fetch failed: {e}", file=sys.stderr)
        return None, None, None

    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [target_lang],
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(TMP_DIR, "%(id)s"),
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
    }

    try:
        with contextlib.redirect_stdout(open(os.devnull, "w")):
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

        files = glob.glob(os.path.join(TMP_DIR, f"{video_id}*.vtt"))
        if not files:
            return None, None, None

        with open(files[0], "r", encoding="utf-8") as f:
            raw = f.read()

        return clean_vtt_text(raw), title, desc

    except Exception as e:
        print(f"❌ Subtitle download failed: {e}", file=sys.stderr)
        return None, None, None


# =========================================================
# GEMINI SUMMARIZATION
# =========================================================

def explain_with_gemini(transcript, title="", description=""):
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    safe_text = transcript[:30000]

    prompt = f"""
You are a product-quality note designer.

Create clean, human-friendly notes.

Rules:
- **Bold** for key ideas
- *Italic* for clarity
- No heavy markdown
- No code blocks

Title: {title}

Transcript:
{safe_text}
"""

    response = model.generate_content(prompt)
    return response.text


# =========================================================
# ENTRYPOINT
# =========================================================

def main():
    if len(sys.argv) < 2:
        print("❌ No URL provided", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]

    configure_gemini()

    transcript, title, desc = get_transcript_from_subs(url)

    if not transcript:
        print("❌ No subtitles found", file=sys.stderr)
        sys.exit(1)

    summary = explain_with_gemini(transcript, title, desc)

    print(json.dumps({
        "summary": summary,
        "title": title,
        "method": "render_subtitles"
    }))


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
