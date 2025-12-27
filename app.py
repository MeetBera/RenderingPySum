from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys

# Import from updated summary.py (Piped-based)
from summary import (
    configure_gemini,
    extract_video_id,
    get_transcript_via_piped,
    get_metadata_via_piped,
    explain_with_gemini
)

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

try:
    configure_gemini()
    print("✅ Gemini configured", file=sys.stderr)
except Exception as e:
    print(f"❌ Gemini configuration failed: {e}", file=sys.stderr)

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "service": "Video Summary API",
        "backend": "Render",
        "captions": "Piped"
    })


@app.route("/summarize", methods=["POST"])
def summarize_video():
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "URL is required"}), 400

    url = data["url"]
    print(f"🚀 Processing URL: {url}", file=sys.stderr)

    # ---------------------------------------------------------
    # 1. Extract video ID
    # ---------------------------------------------------------
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    # ---------------------------------------------------------
    # 2. Get captions via Piped (safe)
    # ---------------------------------------------------------
    transcript = get_transcript_via_piped(video_id)
    if not transcript:
        return jsonify({
            "error": "No captions available for this video."
        }), 422

    # ---------------------------------------------------------
    # 3. Metadata via Piped (optional)
    # ---------------------------------------------------------
    title, description = get_metadata_via_piped(video_id)

    # ---------------------------------------------------------
    # 4. Gemini summarization
    # ---------------------------------------------------------
    try:
        summary = explain_with_gemini(transcript, title, description)
        summary = summary.replace("\u2028", "").replace("\u2029", "")
    except Exception as e:
        print(f"❌ Gemini error: {e}", file=sys.stderr)
        return jsonify({"error": "AI summarization failed"}), 500

    # ---------------------------------------------------------
    # SUCCESS
    # ---------------------------------------------------------
    return jsonify({
        "title": title,
        "summary": summary,
        "method": "piped_captions"
    })


# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
