import sys
import os
import glob
import re
import json
import shutil
import contextlib
import random
import time
import requests  # <--- Added missing import
import google.generativeai as genai
import yt_dlp
from dotenv import load_dotenv

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
def configure_gemini():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Fallback for local testing
    if not api_key:
        # api_key = "AIzaSy..." 
        pass
        
    if api_key:
        genai.configure(api_key=api_key)
    else:
        print("❌ Error: No GEMINI_API_KEY found.", file=sys.stderr)
        # We don't exit here to allow debugging of subtitles even if AI fails

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
# CORE LOGIC: Robust Subtitle Fetch
# ---------------------------------------------------------

def get_transcript_from_subs(url):
    import os, sys, shutil, glob, yt_dlp

    # --- 1. SETUP TEMP DIRECTORY (Render Safe) ---
    temp_dir = "/tmp/yt_subs"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    # --- 2. HANDLE COOKIES ---
   # --- 2. HANDLE COOKIES ---
    cookie_file = None
    if os.path.exists("/etc/secrets/youtube.com_cookies.txt"):
        try:
            dest = "/tmp/youtube_cookies.txt"
            shutil.copy("/etc/secrets/youtube.com_cookies.txt", dest)
            cookie_file = dest
            # DEBUG: Print size to confirm it's not empty
            file_size = os.path.getsize(cookie_file)
            print(f"🍪 Cookie file loaded from secrets ({file_size} bytes)", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Cookie copy failed: {e}", file=sys.stderr)
            cookie_file = "/etc/secrets/youtube.com_cookies.txt"
    elif os.path.exists("youtube.com_cookies.txt"):
        cookie_file = "youtube.com_cookies.txt"
        print(f"🍪 Cookie file loaded from local path", file=sys.stderr)
    else:
        print("⚠️ No cookie file found!", file=sys.stderr)

    # --- 3. FETCH METADATA & SELECT LANGUAGE ---
   # --- 3. FETCH METADATA & SELECT LANGUAGE ---
    meta_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
        "format": "bestaudio/best",
        "ignore_no_formats_error": True,
        "allow_unplayable_formats": True,  # VITAL: Fetches info even if video is restricted
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"], # Rotate clients
                "player_skip": ["webpage", "configs"],      # Skip blocks that trigger bot detection
            }
        }
    }

    video_id = "unknown"
    title = "Unknown"
    desc = ""
    target_lang = None
    use_auto = True

    try:
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        video_id = info.get("id")
        title = info.get("title", "No Title")
        desc = info.get("description", "")

        auto_subs = info.get("automatic_captions", {})
        manual_subs = info.get("subtitles", {})

        print(
            f"ℹ️ Auto: {list(auto_subs.keys())} | Manual: {list(manual_subs.keys())}",
            file=sys.stderr,
        )

        # --- LANGUAGE PRIORITY (NO REGEX) ---
        # --- LANGUAGE PRIORITY (ANTI-429, ORIGINAL FIRST) ---

        # 1. Prefer original language (hi-orig, ta-orig, etc.)
        orig_langs = [l for l in auto_subs if l.endswith("-orig")]
        if orig_langs:
            target_lang = orig_langs[0]
            use_auto = True
        
        # 2️⃣ Prefer Hindi auto captions
        elif "hi" in auto_subs:
            target_lang = "hi"
            use_auto = True
        
        # 3️⃣ Prefer English auto captions
        elif "en" in auto_subs:
            target_lang = "en"
            use_auto = True
        
        # 4️⃣ English manual captions fallback
        elif "en" in manual_subs:
            target_lang = "en"
            use_auto = False
        
        # 5️⃣ Any remaining auto captions
        elif auto_subs:
            target_lang = list(auto_subs.keys())[0]
            use_auto = True
        
        # 6️⃣ Any remaining manual captions
        elif manual_subs:
            target_lang = list(manual_subs.keys())[0]
            use_auto = False
        
        else:
            print("❌ No subtitles available", file=sys.stderr)
            return None, None, None


        print(
            f"✅ Selected language: {target_lang} ({'auto' if use_auto else 'manual'})",
            file=sys.stderr,
        )

    except Exception as e:
        print(f"⚠️ Metadata fetch failed: {e}", file=sys.stderr)
        return None, None, None

        # --- 4. DOWNLOAD SUBTITLES (ONE REQUEST ONLY) ---
    # --- 4. DOWNLOAD SUBTITLES (ONE REQUEST ONLY) ---
    dl_opts = {
        "skip_download": True,
        "subtitleslangs": [target_lang],
        "subtitlesformat": "vtt",
        "outtmpl": f"{temp_dir}/%(id)s",
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
        "writesubtitles": not use_auto,
        "writeautomaticsub": use_auto,
        "format": "bestaudio/best",
        "ignore_no_formats_error": True,
        "allow_unplayable_formats": True, # Match meta_opts
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"],
                "player_skip": ["webpage", "configs"],
            }
        }
    }


    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([url])

        files = glob.glob(os.path.join(temp_dir, "*.vtt"))
        if not files:
            print("❌ Subtitle download finished but no file found", file=sys.stderr)
            return None, None, None

        sub_path = files[0]
        print(f"📂 Reading: {sub_path}", file=sys.stderr)

        with open(sub_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        clean_text = clean_vtt_text(raw_text)
        shutil.rmtree(temp_dir)
        return clean_text, title, desc

    except Exception as e:
        print(f"⚠️ Subtitle download failed: {e}", file=sys.stderr)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None, None, None

# ---------------------------------------------------------
# GEMINI SUMMARIZATION
# ---------------------------------------------------------
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",  # cheapest, fastest
    "gemini-2.5-flash",       # higher quality
]

def explain_with_gemini(transcript, title="", description=""):
    safe_transcript = transcript[:100000]

    prompt = f"""
    Your task: Generate useful, explained and understandable notes from this transcript.
    language: English

    Tone & Care:
    - Make it calm, helpful, and easy to scan

    Formatting Rules:
    - Use **bold** for important ideas
    - Avoid heavy Markdown (no ## headings)
    
    Title: {title}
    Description: {description[:500]}

    Transcript:
    {safe_transcript}
    """

    last_error = None

    for model_name in GEMINI_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = e
            print(f"⚠️ Model {model_name} failed, trying next...", file=sys.stderr)

    raise Exception(f"All Gemini models failed: {last_error}")
    
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
    transcript, title, desc = get_transcript_from_subs(url)

    if transcript:
        print("✅ Transcript acquired.", file=sys.stderr)
        try:
            summary = explain_with_gemini(transcript, title, desc)
            summary = summary.replace("\u2028", "").replace("\u2029", "")
            print(json.dumps({
                "summary": summary,
                "title": title,
                "method": "subtitles_clean"
            }))
        except Exception as e:
            print(f"❌ Gemini Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json.dumps({
            "error": "Unable to retrieve subtitles. The video might be restricted or lacking captions.",
            "title": title if 'title' in locals() else "Unknown",
            "summary": None
        }))
        sys.exit(0)

if __name__ == "__main__":
    main()

