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
from flask import Flask, request, jsonify
from summary import get_summary  # ✅ only import what exists

app = Flask(__name__)

@app.route('/summarize', methods=['POST'])
def summarize_video():
    try:
        # ✅ Support both keys from Node.js: youtube_link or youtube_url
        youtube_link = request.json.get('youtube_url') or request.json.get('youtube_link')
        if not youtube_link:
            return jsonify({"error": "No YouTube URL provided"}), 400

        # ✅ Ensure GEMINI_API_KEY is present
        gemini_api_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_api_key:
            return jsonify({"error": "GEMINI_API_KEY environment variable not set"}), 500

        # ✅ Directly summarize via transcript (no audio)
        summary_result = get_summary(youtube_link, gemini_api_key)

        # ✅ Always wrap in clean JSON
        return jsonify({
            "summary": summary_result.strip() if summary_result else ""
        })

    except Exception as e:
        # ✅ Catch-all to guarantee valid JSON response
        return jsonify({"error": str(e)}), 500


# ✅ Entry point for local testing
if __name__ == '__main__':
    app.run(debug=True)
