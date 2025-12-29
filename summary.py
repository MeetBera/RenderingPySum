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
    cookie_file = None
    if os.path.exists("/etc/secrets/youtube.com_cookies.txt"):
        try:
            dest = "/tmp/youtube_cookies.txt"
            shutil.copy("/etc/secrets/youtube.com_cookies.txt", dest)
            cookie_file = dest
        except:
            cookie_file = "/etc/secrets/youtube.com_cookies.txt"
    elif os.path.exists("youtube.com_cookies.txt"):
        cookie_file = "youtube.com_cookies.txt"

    print(f"🍪 Cookie file used: {cookie_file}", file=sys.stderr)

    # --- 3. FETCH METADATA & SELECT LANGUAGE ---
    meta_opts = {
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
    "cookiefile": cookie_file,
    "format": "bestaudio/best",
    "ignore_no_formats_error": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web", "ios"]
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
        if "en" in auto_subs:
            target_lang = "en"
            use_auto = True
        elif "hi" in auto_subs:
            target_lang = "hi"
            use_auto = True
        elif auto_subs:
            target_lang = list(auto_subs.keys())[0]
            use_auto = True
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
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "ios"]
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
def explain_with_gemini(transcript, title="", description=""):
    # FIX: Use 1.5-flash (2.5 doesn't exist publicly)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    safe_transcript = transcript[:100000] 
    
    prompt = f"""
    You are a product-quality note designer.
    Turn this video transcript into **beautiful, human-friendly notes**.

    METADATA:
    Title: {title}
    Description: {description[:500]}

    TRANSCRIPT:
    {safe_transcript}

    OUTPUT FORMAT:
    ## Summary
    (Concise overview)

    ## Key Points
    - (Bulleted list)
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise Exception(f"Gemini API Error: {str(e)}")

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
        print("❌ FATAL: Could not retrieve subtitles.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

