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

# Import the core logic from your summary.py file
from summary import get_video_id, download_audio_as_id, explain_in_chunks

app = Flask(__name__)

# This is the main endpoint that will handle the summarization request.
@app.route('/summarize', methods=['POST'])
def summarize_video():
    # Get the YouTube URL from the request data
    youtube_link = request.json.get('youtube_url')
    if not youtube_link:
        return jsonify({"error": "No YouTube URL provided"}), 400

    try:
        # Create a temporary directory to save the audio file
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download the audio file to the temporary directory
            audio_path = download_audio_as_id(youtube_link, temp_dir)

            # NOTE: Your summary.py script is hardcoded to use specific paths
            # and will not work as-is in this setup.
            # You will need to modify the script to make the transcription
            # logic a function that takes the audio_path as an argument.
            
            # For demonstration, we'll assume you've modified summary.py
            # to make the transcription and summarization logic a function.
            # Here, we will simulate the process.
            # In a real app, you would import and call those functions.
            
            # This is a placeholder for your actual transcription/summary logic
            # You would replace this with your actual code from summary.py
            print(f"Processing audio at {audio_path}")
            
            # Get API key from environment variable for security
            os.environ.get('GEMINI_API_KEY')
            
            # Placeholder for the actual summary
            summary_result = "This is a placeholder summary. Please modify summary.py to be callable from this app."
            
            return jsonify({"summary": summary_result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# This is the entry point for Gunicorn
if __name__ == '__main__':
    # This block is for local testing only
    app.run(debug=True)
