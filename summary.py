import sys
import os
import glob
import re
import json
import shutil
import contextlib
import random
import time
import requests
import google.generativeai as genai
import yt_dlp
from dotenv import load_dotenv

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
def configure_gemini():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        # Fallback for local testing (Empty is fine if just testing connection)
        pass 
        
    if api_key:
        genai.configure(api_key=api_key)
    else:
        print("❌ Error: No GEMINI_API_KEY found.", file=sys.stderr)

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
    # 1. Handle Cookie File
    cookie_file = None
    if os.path.exists("/etc/secrets/youtube.com_cookies.txt"):
        try:
            shutil.copy("/etc/secrets/youtube.com_cookies.txt", "/tmp/youtube_cookies.txt")
            cookie_file = "/tmp/youtube_cookies.txt"
            print("🍪 Cookies loaded from Render secrets.", file=sys.stderr)
        except:
            cookie_file = "/etc/secrets/youtube.com_cookies.txt"
    elif os.path.exists("youtube.com_cookies.txt"):
        cookie_file = "youtube.com_cookies.txt"
        print("🍪 Cookies loaded from local file.", file=sys.stderr)

    # 2. Configure yt-dlp
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
        "nocheckcertificate": True,
        "extract_flat": False,
        # Force using Android client to bypass common web blocks
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"]
            }
        },
        "user_agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }

    try:
        # Step A: Extract Metadata (No Download)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "Unknown Title")
        desc = info.get("description", "")

        # Step B: Find Subtitles manually
        captions = info.get("subtitles") or info.get("automatic_captions") or {}

        if not captions:
            print("❌ No captions found in metadata.", file=sys.stderr)
            return None, None, None

        # Logic: English -> Hindi -> First Available
        lang = None
        
        # Check for English
        for k in captions:
            if k.startswith("en"):
                lang = k
                break
        
        # Check for Hindi
        if not lang:
            for k in captions:
                if k.startswith("hi"):
                    lang = k
                    break
        
        # Fallback
        if not lang:
            lang = list(captions.keys())[0]

        print(f"✅ Selected Language: {lang}", file=sys.stderr)

        # Step C: Get VTT URL
        subs_list = captions.get(lang, [])
        vtt_url = None
        
        # Look for 'vtt' format specifically
        for sub in subs_list:
            if sub.get('ext') == 'vtt':
                vtt_url = sub.get('url')
                break
        
        # Fallback to any URL found
        if not vtt_url and subs_list:
            vtt_url = subs_list[0].get('url')

        if not vtt_url:
            print("❌ No subtitle URL found.", file=sys.stderr)
            return None, None, None

        # Step D: Fetch Content via Requests (Bypasses 429 often)
        r = requests.get(vtt_url, timeout=10)
        r.raise_for_status()

        clean_text = clean_vtt_text(r.text)
        return clean_text, title, desc

    except Exception as e:
        print(f"⚠️ Subtitle extraction failed: {e}", file=sys.stderr)
        return None, None, None

# ---------------------------------------------------------
# GEMINI SUMMARIZATION
# ---------------------------------------------------------
def explain_with_gemini(transcript, title="", description=""):
    # Correct Model Name
    model = genai.GenerativeModel("gemini-1.5-flash")
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
            # Remove line breaks that break JSON
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
        # Generic error to keep frontend clean
        print("❌ FATAL: Could not retrieve subtitles.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
