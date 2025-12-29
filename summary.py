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
import os
import glob
import shutil
import sys
import yt_dlp
import contextlib

def get_transcript_from_subs(url):
    # --- 1. SETUP TEMP DIRECTORY (Render Safe) ---
    # We use a specific subfolder in /tmp to avoid file collisions
    temp_dir = "/tmp/yt_subs"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)  # Clean start
    os.makedirs(temp_dir)

    # --- 2. HANDLE COOKIES (Render Secrets) ---
    cookie_file = None
    if os.path.exists("/etc/secrets/youtube.com_cookies.txt"):
        try:
            # Copy to temp to ensure permissions work
            dest = "/tmp/youtube_cookies.txt"
            shutil.copy("/etc/secrets/youtube.com_cookies.txt", dest)
            cookie_file = dest
        except:
            cookie_file = "/etc/secrets/youtube.com_cookies.txt"
    elif os.path.exists("youtube.com_cookies.txt"):
        cookie_file = "youtube.com_cookies.txt"

    print(f"🍪 Cookie file used: {cookie_file}", file=sys.stderr)

    # --- 3. METADATA & LANGUAGE SELECTION ---
    # We fetch metadata first to check what languages exist
    meta_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }

    target_lang = 'en.*' # Default fallback
    video_id = "unknown"
    title = "Unknown"
    desc = ""

    try:
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get('id')
            title = info.get('title', 'No Title')
            desc = info.get('description', '')

            # Combine manual and auto-generated captions
            manual_subs = list(info.get('subtitles', {}).keys())
            auto_subs = list(info.get('automatic_captions', {}).keys())
            all_langs = set(manual_subs + auto_subs)
            
            print(f"ℹ️ Found Languages: {all_langs}", file=sys.stderr)

            # --- SMART PRIORITY LOGIC ---
            # 1. English
            if any(l.startswith('en') for l in all_langs):
                target_lang = 'en.*'
                print("✅ Selected: English", file=sys.stderr)
            # 2. Hindi
            elif any(l.startswith('hi') for l in all_langs):
                target_lang = 'hi.*'
                print("✅ Selected: Hindi", file=sys.stderr)
            # 3. Fallback to whatever is available (e.g., auto-generated)
            elif len(all_langs) > 0:
                target_lang = list(all_langs)[0]
                print(f"✅ Selected Fallback: {target_lang}", file=sys.stderr)
            else:
                print("❌ No subtitles found at all.", file=sys.stderr)
                return None, None, None

    except Exception as e:
        print(f"⚠️ Metadata fetch failed: {e}", file=sys.stderr)
        return None, None, None

    # --- 4. DOWNLOAD SUBTITLES ---
    # Now we download ONLY the selected subtitle file
    dl_opts = {
        'skip_download': True,      # Don't download video
        'writesubtitles': True,     # Download manual subs
        'writeautomaticsub': True,  # Download auto subs
        'subtitleslangs': [target_lang], 
        'subtitlesformat': 'vtt',   # Force VTT format
        'outtmpl': f"{temp_dir}/%(id)s", # Save to our temp folder
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_file,
    }

    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([url])

        # --- 5. FIND AND READ FILE ---
        # yt-dlp appends the language code to the filename (e.g., videoID.en.vtt)
        # We use glob to find whatever file appeared in our temp folder
        potential_files = glob.glob(os.path.join(temp_dir, "*.vtt"))

        if potential_files:
            sub_path = potential_files[0]
            print(f"📂 Reading file: {sub_path}", file=sys.stderr)
            
            with open(sub_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()

            # Clean the text using your existing function
            clean_text = clean_vtt_text(raw_text)

            # --- 6. CLEANUP ---
            shutil.rmtree(temp_dir)
            
            return clean_text, title, desc
        else:
            print("❌ Download finished but no .vtt file found.", file=sys.stderr)
            return None, None, None

    except Exception as e:
        print(f"⚠️ Subtitle download failed: {e}", file=sys.stderr)
        # Cleanup on fail
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None, None, None
    # 2. DOWNLOAD SELECTED LANGUAGE
    opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [target_lang], # Use our smart choice
        'subtitlesformat': 'vtt',
        'outtmpl': os.path.join(temp_dir, '%(id)s'), 
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_file
    }

    try:
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

        potential_files = glob.glob(os.path.join(temp_dir, f"{video_id}*.vtt"))
        
        if potential_files:
            sub_path = potential_files[0]
            print(f"✅ Found subtitles: {sub_path}", file=sys.stderr)
            
            with open(sub_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            
            clean_text = clean_vtt_text(raw_text)
            try: shutil.rmtree(temp_dir)
            except: pass
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

