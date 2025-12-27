import sys
import os
import json
import re
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

PIPED_INSTANCES = [
    "https://piped.video",
    "https://piped.projectsegfau.lt",
    "https://piped.lunar.icu",
]

def configure_gemini():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY missing", file=sys.stderr)
        sys.exit(1)
    genai.configure(api_key=api_key)

# ---------------------------------------------------------
# UTILITY
# ---------------------------------------------------------

def extract_video_id(url: str) -> str | None:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None


def clean_vtt_text(vtt: str) -> str:
    lines = vtt.splitlines()
    out = []
    seen = set()

    for line in lines:
        if (
            not line.strip()
            or "WEBVTT" in line
            or "-->" in line
            or line.strip().isdigit()
        ):
            continue

        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line not in seen:
            seen.add(line)
            out.append(line)

    return " ".join(out)

# ---------------------------------------------------------
# STRATEGY 1: PIPED CAPTION MIRROR (RENDER SAFE)
# ---------------------------------------------------------

def get_transcript_via_piped(video_id):
    for base in PIPED_INSTANCES:
        try:
            meta = requests.get(
                f"{base}/api/v1/captions/{video_id}",
                timeout=8
            )
            meta.raise_for_status()
            captions = meta.json()

            if not captions:
                continue

            # Prefer English
            for cap in captions:
                if cap.get("language", "").startswith("en"):
                    vtt = requests.get(cap["url"], timeout=8).text
                    return clean_vtt_text(vtt)

            # Fallback to first available
            vtt = requests.get(captions[0]["url"], timeout=8).text
            return clean_vtt_text(vtt)

        except Exception:
            continue

    return None

# ---------------------------------------------------------
# METADATA (OPTIONAL, NON-BLOCKING)
# ---------------------------------------------------------

def get_metadata_via_piped(video_id):
    for base in PIPED_INSTANCES:
        try:
            r = requests.get(
                f"{base}/api/v1/video/{video_id}",
                timeout=8
            )
            r.raise_for_status()
            data = r.json()
            return data.get("title", ""), data.get("description", "")
        except Exception:
            continue

    return "Unknown Title", ""

# ---------------------------------------------------------
# GEMINI SUMMARIZATION
# ---------------------------------------------------------

def explain_with_gemini(transcript, title="", description=""):
    model = genai.GenerativeModel("gemini-2.5-flash")

    safe_transcript = transcript[:100_000]

    prompt = f"""
You are a product-quality note designer.

Create calm, clear, human-friendly notes.

Title: {title}
Description: {description[:500]}

Transcript:
{safe_transcript}

Output:
## Summary
(short overview)

## Key Points
- clear bullets
"""

    response = model.generate_content(prompt)
    return response.text

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No URL provided"}))
        sys.exit(1)

    url = sys.argv[1]
    configure_gemini()

    video_id = extract_video_id(url)
    if not video_id:
        print(json.dumps({"error": "Invalid YouTube URL"}))
        sys.exit(1)

    print(f"🚀 Processing video: {video_id}", file=sys.stderr)

    transcript = get_transcript_via_piped(video_id)
    if not transcript:
        print("❌ No captions available (mirror-safe failure).", file=sys.stderr)
        sys.exit(1)

    title, desc = get_metadata_via_piped(video_id)

    summary = explain_with_gemini(transcript, title, desc)
    summary = summary.replace("\u2028", "").replace("\u2029", "")

    print(json.dumps({
        "title": title,
        "summary": summary,
        "method": "piped_captions"
    }))

if __name__ == "__main__":
    main()
