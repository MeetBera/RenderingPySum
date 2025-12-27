from flask import Flask, request, jsonify
import os
import sys

# Import functions from your fixed summary.py
from summary import (
    configure_gemini,
    get_transcript_from_subs,
    explain_with_gemini
)

app = Flask(__name__)

# --- Safe Startup Configuration ---
try:
    configure_gemini()
    print("✅ Gemini Configured Successfully", file=sys.stderr)
except Exception as e:
    print(f"❌ Gemini Configuration Failed: {e}", file=sys.stderr)

@app.route("/")
def home():
    return jsonify({"status": "running", "message": "Video Summary API Ready"})

@app.route("/summarize", methods=["POST"])
def summarize_video():
    data = request.get_json()
    
    # Validation
    if not data or "url" not in data:
        return jsonify({"error": "URL required"}), 400

    url = data["url"]

    try:
        # ---------------------------------------------------------
        # STRATEGY 1: FAST TRACK (Subtitles)
        # ---------------------------------------------------------
        print(f"🚀 Processing URL: {url}", file=sys.stderr)
        transcript, title, description = get_transcript_from_subs(url)

        if transcript:
            print("✅ Subtitles found! Generating summary...", file=sys.stderr)
            
            # Generate Summary from Text
            summary = explain_with_gemini(transcript, title, description)
            
            return jsonify({
                "summary": summary,
                "title": title,
                "description": description[:500] if description else "",
                "method": "subtitles_fast"
            })
        
        # ---------------------------------------------------------
        # STRATEGY 2: FALLBACK (Audio)
        # ---------------------------------------------------------
        # Note: Since we removed audio logic from summary.py to keep it simple/fast,
        # we return an error here. If you add audio download back later, 
        # place that logic here.
        else:
            print("⚠️ No subtitles found. Audio fallback is currently disabled.", file=sys.stderr)
            return jsonify({
                "error": "Could not find subtitles for this video. Audio processing is disabled."
            }), 422

    except Exception as e:
        print(f"❌ API Error: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Render provides the PORT env var
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
