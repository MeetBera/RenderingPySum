# from flask import Flask, request, jsonify
# from summary import summarize_youtube_video  # import your function

# app = Flask(__name__)

# @app.route("/")
# def home():
#     return "YouTube Summarizer API is running!"

# @app.route("/summarize", methods=["POST"])
# def summarize():
#     try:
#         data = request.get_json()
#         youtube_link = data.get("youtube_link")
#         save_directory = "/tmp"  # safe dir for Render

#         if not youtube_link:
#             return jsonify({"error": "youtube_link is required"}), 400

#         result = summarize_youtube_video(youtube_link, save_directory)
#         return jsonify({"summary": result})
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
import os
import tempfile
from flask import Flask, request, jsonify

# Import the core logic functions from summary.py
# We only need to import the top-level functions
from summary import get_video_id, download_audio_as_id, get_summary

app = Flask(__name__)

# This is the main endpoint that will handle the summarization request.
@app.route('/summarize', methods=['POST'])
def summarize_video():
    # Get the YouTube URL from the request data
    youtube_link = request.json.get('youtube_link') or request.json.get('youtube_url')
    if not youtube_link:
        return jsonify({"error": "No YouTube URL provided"}), 400

    try:
        # Create a temporary directory to save the audio file
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download the audio file to the temporary directory
            audio_path = download_audio_as_id(youtube_link, temp_dir)

            # Get the API key from environment variable for security
            gemini_api_key = os.environ.get('GEMINI_API_KEY')
            if not gemini_api_key:
                return jsonify({"error": "GEMINI_API_KEY environment variable not set."}), 500

            # Perform the transcription and summarization
            summary_result = get_summary(audio_path, gemini_api_key)
            
            return jsonify({"summary": summary_result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# This is the entry point for Gunicorn
if __name__ == '__main__':
    # This block is for local testing only
    app.run(debug=True)
