from flask import Flask, request, jsonify
from flask_cors import CORS 
import os
import sys

# Import the updated functions from summary.py
from summary import (
    configure_gemini,
    get_video_metadata,
    explain_with_gemini
)

app = Flask(__name__)
# Enable CORS for all routes
CORS(app)

# --- Safe Startup Configuration ---
try:
    configure_gemini()
    print("✅ Gemini Configured Successfully", file=sys.stderr)
except Exception as e:
    print(f"❌ Gemini Configuration Failed: {e}", file=sys.stderr)

@app.route("/")
def home():
    """Health Check Route"""
    return jsonify({
        "status": "running", 
        "message": "Video Summary API Ready (Metadata Mode)",
        "service": "Render"
    })

@app.route("/summarize", methods=["POST"])
def summarize_video():
    data = request.get_json()
    
    # 1. Validation
    if not data or "url" not in data:
        return jsonify({"error": "URL required"}), 400

    url = data["url"]

    try:
        print(f"🚀 Processing URL: {url}", file=sys.stderr)
        
        # 2. Fetch Metadata (Title, Description, Channel)
        # This uses the fast yt-dlp mode we added to summary.py
        title, description, channel = get_video_metadata(url)

        if not title:
            return jsonify({"error": "Could not fetch video metadata"}), 404
        
        # 3. Generate Summary using Metadata
        summary_text = explain_with_gemini(url, title, description, channel)
        
        # Clean up specific unicode characters that might break JSON
        summary_text = summary_text.replace("\u2028", "").replace("\u2029", "")
        
        # 4. Successful Response
        return jsonify({
            "summary": summary_text,
            "title": title, 
            "channel": channel,
            "description": description[:200] + "..." if description else "", # Truncate for cleaner JSON
            "method": "metadata_only"
        })

    except Exception as e:
        print(f"❌ API Error: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Render automatically sets the 'PORT' environment variable.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# from flask import Flask, request, jsonify
# from flask_cors import CORS  # Optional: logic to allow frontend requests
# import os
# import sys

# # Import functions from your summary.py
# from summary import (
#     configure_gemini,
#     get_transcript_from_subs,
#     explain_with_gemini
# )

# app = Flask(__name__)
# # Enable CORS for all routes (Crucial if your frontend is on a different domain/port)
# CORS(app)

# # --- Safe Startup Configuration ---
# # We configure Gemini once when the app starts
# try:
#     configure_gemini()
#     print("✅ Gemini Configured Successfully", file=sys.stderr)
# except Exception as e:
#     print(f"❌ Gemini Configuration Failed: {e}", file=sys.stderr)
#     # We don't exit here so the server can still start and report health

# @app.route("/")
# def home():
#     """Health Check Route"""
#     return jsonify({
#         "status": "running", 
#         "message": "Video Summary API Ready",
#         "service": "Render"
#     })

# @app.route("/summarize", methods=["POST"])
# def summarize_video():
#     data = request.get_json()
    
#     # 1. Validation
#     if not data or "url" not in data:
#         return jsonify({"error": "URL required"}), 400

#     url = data["url"]

#     try:
#         # ---------------------------------------------------------
#         # STRATEGY 1: FAST TRACK (Subtitles)
#         # ---------------------------------------------------------
#         print(f"🚀 Processing URL: {url}", file=sys.stderr)
        
#         # Call the function from summary.py
#         transcript, title, description = get_transcript_from_subs(url)

#         if transcript:
#             print("✅ Subtitles found! Generating AI summary...", file=sys.stderr)
            
#             # Generate Summary from Text
#             summary = explain_with_gemini(transcript, title, description)
            
#             # Successful Response
#             return jsonify({
#                 "summary": summary,
#                 "title": title,
#                 "description": description[:500] if description else "",
#                 "method": "subtitles_fast"
#             })
        
#         # ---------------------------------------------------------
#         # STRATEGY 2: FALLBACK (Currently Disabled)
#         # ---------------------------------------------------------
#         else:
#             print("⚠️ No subtitles found. Audio fallback is disabled.", file=sys.stderr)
#             return jsonify({
#                 "error": "Could not find subtitles for this video. Please ensure the video has captions."
#             }), 422

#     except Exception as e:
#         print(f"❌ API Error: {e}", file=sys.stderr)
#         return jsonify({"error": str(e)}), 500

# if __name__ == "__main__":
#     # Render automatically sets the 'PORT' environment variable.
#     # We must listen on 0.0.0.0 to be accessible externally.
#     port = int(os.environ.get("PORT", 5000))
#     app.run(host="0.0.0.0", port=port)
