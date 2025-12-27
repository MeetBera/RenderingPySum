import sys
import os
import json
import google.generativeai as genai
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from dotenv import load_dotenv

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
def configure_gemini():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
    else:
        # We don't exit here, so we can at least print the transcript if API fails
        print("⚠️ Warning: GEMINI_API_KEY not found.", file=sys.stderr)

# ---------------------------------------------------------
# STRATEGY 2: The "API" Method (Bypasses Player Block)
# ---------------------------------------------------------
def get_transcript_data(url):
    video_id = ""
    
    # 1. Extract Video ID securely
    try:
        # Simple regex to get ID from standard URL
        if "v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        else:
            # Fallback to yt-dlp just for ID extraction if regex fails
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                video_id = info.get('id')
    except Exception as e:
        print(f"❌ Could not extract Video ID: {e}", file=sys.stderr)
        return None, None, None

    print(f"🆔 Video ID: {video_id}", file=sys.stderr)

    # 2. Fetch Transcript via specialized API (Bypasses yt-dlp blocks)
    transcript_text = ""
    try:
        # Try fetching transcript (Auto-detected priority: Manual English -> Manual Hindi -> Auto)
        # This library handles the complex "which language" logic automatically
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Priority Logic:
        # 1. Manually created English
        # 2. Manually created Hindi
        # 3. Auto-generated English
        try:
            transcript = transcript_list.find_transcript(['en', 'hi'])
        except:
            # Fallback to auto-generated if manual not found
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                # Absolute fallback: just give me anything you have
                transcript = transcript_list.find_manually_created_transcript(['en', 'hi'])

        # Fetch the actual data
        full_data = transcript.fetch()
        
        # Format to clean text
        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(full_data)
        
        # Clean up whitespace
        transcript_text = transcript_text.replace("\n", " ")

    except Exception as e:
        print(f"⚠️ Transcript API failed: {e}", file=sys.stderr)
        return None, None, None

    # 3. Fetch Metadata (Title/Desc) via yt-dlp (Lightweight)
    # Even if this fails due to 429, we still have the transcript!
    title = "Unknown Title"
    desc = ""
    try:
        opts = {
            'quiet': True, 
            'skip_download': True,
            'ignoreerrors': True, # Don't crash if metadata fetch fails
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                title = info.get('title', 'Unknown Title')
                desc = info.get('description', '')
    except:
        print("⚠️ Metadata fetch failed (Title might be missing), but transcript is safe.", file=sys.stderr)

    return transcript_text, title, desc

# ---------------------------------------------------------
# GEMINI SUMMARIZATION
# ---------------------------------------------------------
def explain_with_gemini(transcript, title="", description=""):
    model = genai.GenerativeModel("gemini-2.5-flash")
    # Safety limit
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
    
    # Use the new robust method
    transcript, title, desc = get_transcript_data(url)

    if transcript:
        print("✅ Transcript acquired. Summarizing...", file=sys.stderr)
        try:
            summary = explain_with_gemini(transcript, title, desc)
            summary = summary.replace("\u2028", "").replace("\u2029", "")
            print(json.dumps({
                "summary": summary,
                "title": title,
                "method": "youtube_transcript_api"
            }))
        except Exception as e:
            print(f"❌ Gemini Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("❌ FATAL: Could not retrieve subtitles.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
