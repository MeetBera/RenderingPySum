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
    # 1. Handle Cookie File
    cookie_file = None
    if os.path.exists("/etc/secrets/youtube.com_cookies.txt"):
        # Copy to temp to ensure it's writable/readable
        try:
            shutil.copy("/etc/secrets/youtube.com_cookies.txt", "/tmp/youtube_cookies.txt")
            cookie_file = "/tmp/youtube_cookies.txt"
        except:
            cookie_file = "/etc/secrets/youtube.com_cookies.txt"
    elif os.path.exists("youtube.com_cookies.txt"):
        cookie_file = "youtube.com_cookies.txt"

    # 2. Configure yt-dlp
    # We allow 'android' AND 'web' clients to give yt-dlp options if one fails
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
        "extract_flat": False,
        "forcejson": True,
        # PROXY: If you have a proxy, add it here: 'proxy': 'http://user:pass@host:port',
        "extractor_args": {
            "youtube": {
                # Try android first (good for age-gate), then web (standard)
                "player_client": ["android", "web"]
            }
        },
        # User Agent to look like a standard browser
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # This is where it was failing. Updating yt-dlp fixes this.
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "Unknown Title")
        desc = info.get("description", "")

        # 3. Extract Subtitles manually
        captions = {}
        captions.update(info.get("subtitles") or {})
        captions.update(info.get("automatic_captions") or {})


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

        # Get the URL of the VTT format
        subs_list = captions.get(lang, [])
        vtt_url = None
        
        # Look for vtt format specifically
        for sub in subs_list:
            if sub.get('ext') == 'vtt':
                vtt_url = sub.get('url')
                break
        
        # Fallback to whatever URL is there (usually json3 or srv1, but we need text)
        if not vtt_url and subs_list:
            vtt_url = subs_list[0].get('url')

        if not vtt_url:
            return None, None, None

        # 4. Download content directly (Bypassing yt-dlp download logic)
        # Using the same cookies for the request is sometimes needed
        headers = {"User-Agent": ydl_opts["user_agent"]}
        
        # Note: We don't usually pass cookies to the subtitle URL fetch, 
        # but if it fails, you might need to use a session with cookies.
        r = requests.get(vtt_url, headers=headers, timeout=10)
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
    # FIX: Use 1.5-flash (2.5 doesn't exist publicly)
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
