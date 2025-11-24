from flask import Flask, request, jsonify
from summary import (
    configure_gemini,
    download_audio,
    transcribe_with_gemini,
    explain_with_gemini
)
import os

app = Flask(__name__)
configure_gemini()  # Load Gemini API key from environment


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
        # Unpack all 3 values returned by download_audio()
        audio_path, title, description = download_audio(url)

        if not audio_path:
            return jsonify({"error": "Audio download failed"}), 500

        # Transcription
        transcript = transcribe_with_gemini(audio_path)

        # Summary generation
        summary = explain_with_gemini(transcript, title, description)

        # Auto-cleanup audio file
        try:
            os.remove(audio_path)
        except Exception:
            pass

        return jsonify({
            "summary": summary,
            "title": title,
            "description": description[:500]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
