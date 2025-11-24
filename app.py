from flask import Flask, request, jsonify
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
        # FIX: unpack all 3 return values
        audio_path, title, description = download_audio(url)

        if not audio_path:
            return jsonify({"error": "Audio download failed"}), 500

        # Transcribe
        transcript = transcribe_with_gemini(audio_path)

        # Summarize
        summary = explain_with_gemini(transcript, title, description)

        return jsonify({
            "summary": summary,
            "title": title,
            "description": description[:500]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
