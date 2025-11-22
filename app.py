from flask import Flask, request, jsonify
import yt_dlp
from summary import (
    configure_gemini,
    download_audio,
    transcribe_with_gemini,
    explain_with_gemini
)

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
        audio_path = download_audio(url)
        if not audio_path:
            return jsonify({"error": "Audio download failed"}), 500

        transcript = transcribe_with_gemini(audio_path)

        # Extract video metadata
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get("title", "")
        description = info.get("description", "")

        summary = explain_with_gemini(transcript, title, description)

        return jsonify({"summary": summary})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
