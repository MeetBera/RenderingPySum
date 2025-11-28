# from flask import Flask, request, jsonify
# from summary import (
#     configure_gemini,
#     download_audio,
#     transcribe_with_gemini,
#     explain_with_gemini
# )
# import os

# app = Flask(__name__)
# configure_gemini()  # Load Gemini API key from environment


# @app.route("/")
# def home():
#     return {"status": "running", "message": "Video Summary API"}


# @app.route("/summarize", methods=["POST"])
# def summarize_video():
#     data = request.get_json()
#     if not data or "url" not in data:
#         return jsonify({"error": "URL required"}), 400

#     url = data["url"]

#     try:
#         # Unpack all 3 values returned by download_audio()
#         audio_path, title, description = download_audio(url)

#         if not audio_path:
#             return jsonify({"error": "Audio download failed"}), 500

#         # Transcription
#         transcript = transcribe_with_gemini(audio_path)

#         # Summary generation
#         summary = explain_with_gemini(transcript, title, description)

#         # Auto-cleanup audio file
#         try:
#             os.remove(audio_path)
#         except Exception:
#             pass

#         return jsonify({
#             "summary": summary,
#             "title": title,
#             "description": description[:500]
#         })

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000)
from flask import Flask, request, jsonify
import os
import sys
from summary import (
    configure_gemini,
    get_transcript_from_subs,  # <--- NEW IMPORT
    download_audio,
    transcribe_with_gemini,
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
    return {"status": "running", "message": "Video Summary API"}

@app.route("/summarize", methods=["POST"])
def summarize_video():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "URL required"}), 400

    url = data["url"]

    try:
        # ---------------------------------------------------------
        # STRATEGY 1: FAST TRACK (Subtitles)
        # ---------------------------------------------------------
        print("🚀 Attempting Fast Track (Subtitles)...", file=sys.stderr)
        transcript, title, description = get_transcript_from_subs(url)

        if transcript:
            print("✅ Subtitles found! Skipping audio download.", file=sys.stderr)
            
            # Generate Summary from Text
            summary = explain_with_gemini(transcript, title, description)
            
            return jsonify({
                "summary": summary,
                "title": title,
                "description": description[:500],
                "method": "subtitles_fast"
            })

        # ---------------------------------------------------------
        # STRATEGY 2: SLOW TRACK (Audio Fallback)
        # ---------------------------------------------------------
        print("⚠️ No subtitles found. Falling back to Audio (Slow)...", file=sys.stderr)
        
        # 1. Download Audio
        audio_path, title, description = download_audio(url)

        if not audio_path:
            return jsonify({"error": "Audio download failed"}), 500

        try:
            # 2. Transcribe Audio
            transcript = transcribe_with_gemini(audio_path)

            # 3. Generate Summary
            summary = explain_with_gemini(transcript, title, description)

            return jsonify({
                "summary": summary,
                "title": title,
                "description": description[:500],
                "method": "audio_slow"
            })

        finally:
            # Always clean up the large audio file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    print(f"🧹 Cleaned up file: {audio_path}", file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Cleanup failed {e}", file=sys.stderr)

    except Exception as e:
        print(f"❌ API Error: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
