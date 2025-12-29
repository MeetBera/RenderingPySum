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
    import os, sys, glob, shutil, contextlib
    import yt_dlp
    import requests

    # -----------------------------
    # 1. Cookie handling (Render-safe)
    # -----------------------------
    cookie_file = None
    if os.path.exists("/etc/secrets/youtube.com_cookies.txt"):
        try:
            shutil.copy(
                "/etc/secrets/youtube.com_cookies.txt",
                "/tmp/youtube_cookies.txt"
            )
            cookie_file = "/tmp/youtube_cookies.txt"
        except:
            cookie_file = "/etc/secrets/youtube.com_cookies.txt"
    elif os.path.exists("youtube.com_cookies.txt"):
        cookie_file = "youtube.com_cookies.txt"

    # -----------------------------
    # 2. Temp dir (Render compatible)
    # -----------------------------
    temp_dir = "/tmp/ytdlp_subs"
    os.makedirs(temp_dir, exist_ok=True)

    # cleanup old subs
    for f in glob.glob(os.path.join(temp_dir, "*.vtt")):
        try:
            os.remove(f)
        except:
            pass

    # -----------------------------
    # 3. METADATA pass (language decision only)
    # -----------------------------
    meta_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
        "ignore_no_formats_error": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        video_id = info.get("id")
        title = info.get("title", "Unknown Title")
        desc = info.get("description", "")

        manual = info.get("subtitles", {}) or {}
        auto = info.get("automatic_captions", {}) or {}
        all_langs = set(manual.keys()) | set(auto.keys())

        if not all_langs:
            print("❌ No subtitles advertised.", file=sys.stderr)
            return None, None, None

        # Priority: English → Hindi → anything
        if any(l.startswith("en") for l in all_langs):
            target_lang = "en.*"
        elif any(l.startswith("hi") for l in all_langs):
            target_lang = "hi.*"
        else:
            target_lang = ".*"

    except Exception as e:
        print(f"⚠️ Metadata extraction failed: {e}", file=sys.stderr)
        return None, None, None

    # -----------------------------
    # 4. FORCED subtitle download (critical for Render)
    # -----------------------------
    dl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [target_lang],
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(temp_dir, "%(id)s"),
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
        "ignore_no_formats_error": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([url])

        vtt_files = glob.glob(os.path.join(temp_dir, f"{video_id}*.vtt"))
        if not vtt_files:
            print("❌ Subtitle download produced no files.", file=sys.stderr)
            return None, None, None

        with open(vtt_files[0], "r", encoding="utf-8") as f:
            raw_text = f.read()

        clean_text = clean_vtt_text(raw_text)

        # optional cleanup
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

        return clean_text, title, desc

    except Exception as e:
        print(f"⚠️ Subtitle download failed: {e}", file=sys.stderr)
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

