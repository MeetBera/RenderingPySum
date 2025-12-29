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
    temp_dir = "/tmp"
    if os.name == 'nt': 
        temp_dir = os.path.join(os.getcwd(), "temp_subs")
    
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    for f in glob.glob(os.path.join(temp_dir, "*.vtt")):
        try: os.remove(f)
        except: pass

    cookie_file = None
    possible_paths = ["youtube.com_cookies.txt", "/etc/secrets/youtube.com_cookies.txt"]
    for path in possible_paths:
        if os.path.exists(path):
            cookie_file = path
            print(f"🍪 Using cookies from: {path}", file=sys.stderr)
            break

    # 1. FETCH METADATA
    meta_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_file
    }
    
    target_lang = 'en.*' # Default safest fallback

    try:
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_id = info.get('id')
                title = info.get('title', 'No Title')
                desc = info.get('description', '')
                
                # Get all available subtitle languages
                manual_subs = list(info.get('subtitles', {}).keys())
                auto_subs = list(info.get('automatic_captions', {}).keys())
                all_langs = set(manual_subs + auto_subs)
                
                print(f"ℹ️ Available Languages: {all_langs}", file=sys.stderr)

                # SMART PRIORITY LIST
                # 1. English (Any variant)
                # 2. Hindi (Any variant)
                # 3. Auto-detected Native (if sensible)
                
                if any(l.startswith('en') for l in all_langs):
                    target_lang = 'en.*'
                    print("ℹ️ Selecting English subtitles.", file=sys.stderr)
                elif any(l.startswith('hi') for l in all_langs):
                    target_lang = 'hi.*'
                    print("ℹ️ Selecting Hindi subtitles.", file=sys.stderr)
                elif auto_subs:
                    target_lang = auto_subs[0]
                    print(f"ℹ️ Selecting Auto-detected: {target_lang}", file=sys.stderr)
                else:
                    print("❌ No subtitles found.", file=sys.stderr)
                    return None, None, None

    except Exception as e:
        print(f"⚠️ Metadata fetch failed: {e}", file=sys.stderr)
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

