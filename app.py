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
# import os
# from flask import Flask, request, jsonify
# from summary import get_summary  # ✅ only import what exists

# app = Flask(__name__)

# @app.route('/summarize', methods=['POST'])
# def summarize_video():
#     try:
#         # ✅ Support both keys from Node.js: youtube_link or youtube_url
#         youtube_link = request.json.get('youtube_url') or request.json.get('youtube_link')
#         if not youtube_link:
#             return jsonify({"error": "No YouTube URL provided"}), 400

#         # ✅ Ensure GEMINI_API_KEY is present
#         gemini_api_key = os.environ.get('GEMINI_API_KEY')
#         if not gemini_api_key:
#             return jsonify({"error": "GEMINI_API_KEY environment variable not set"}), 500

#         # ✅ Directly summarize via transcript (no audio)
#         summary_result = get_summary(youtube_link, gemini_api_key)

#         # ✅ Always wrap in clean JSON
#         return jsonify({
#             "summary": summary_result.strip() if summary_result else ""
#         })

#     except Exception as e:
#         # ✅ Catch-all to guarantee valid JSON response
#         return jsonify({"error": str(e)}), 500


# # ✅ Entry point for local testing
# if __name__ == '__main__':
#     app.run(debug=True)


# import google.generativeai as genai
# import textwrap

# # -------------------------------------------------
# # Function to extract transcript and summarize
# # -------------------------------------------------
# def get_summary(youtube_url, gemini_api_key):
#     """
#     Summarize a YouTube video's transcript using Gemini.
#     """

#     # ✅ Configure Gemini API
#     genai.configure(api_key=gemini_api_key)
#     model = genai.GenerativeModel("gemini-1.5-flash")

#     # ✅ Extract transcript text directly from YouTube
#     try:
#         from youtube_transcript_api import YouTubeTranscriptApi
#         import re

#         # Extract video ID from URL
#         match = re.search(r"(?:v=|youtu\.be/)([\w-]+)", youtube_url)
#         if not match:
#             raise ValueError("Invalid YouTube URL.")
#         video_id = match.group(1)

#         # Fetch transcript
#         transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "hi"])
#         transcript_text = " ".join([item["text"] for item in transcript_list])

#     except Exception as e:
#         raise RuntimeError(f"Transcript extraction failed: {e}")

#     # ✅ Break long transcript into chunks
#     chunks = textwrap.wrap(transcript_text, 4000)
#     summaries = []

#     for i, chunk in enumerate(chunks, 1):
#         print(f"Summarizing chunk {i}/{len(chunks)}...")
#         prompt = f"Summarize this transcript segment in simple, human-friendly points:\n\n{chunk}"
#         try:
#             response = model.generate_content(prompt)
#             summaries.append(response.text)
#         except Exception as e:
#             summaries.append(f"[Error on chunk {i}: {e}]")

#     final_summary = "\n\n".join(summaries)
#     return final_summary

# from flask import Flask, request, jsonify
# import os
# from google.api_core import exceptions as google_exceptions
# from summary import get_summary

# app = Flask(__name__)

# @app.route("/summarize", methods=["POST"])
# def summarize():
#     try:
#         data = request.get_json(force=True)

#         # ✅ Flexible key: support both youtube_link and youtube_url
#         yt_url = data.get("youtube_link") or data.get("youtube_url")
#         if not yt_url:
#             return jsonify({"error": "Missing YouTube URL in request"}), 400

#         gemini_api_key = os.getenv("GEMINI_API_KEY")
#         if not gemini_api_key:
#             return jsonify({"error": "Missing GEMINI_API_KEY environment variable"}), 500

#         # 🧠 Core logic
#         result = get_summary(yt_url, gemini_api_key)

#         return jsonify({
#             "summary": result.get("summary", "").strip(),
#             "transcript": result.get("transcript", "").strip()
#         })

#     # 🌐 Specific Gemini quota/rate-limit handling
#     except google_exceptions.ResourceExhausted:
#         return jsonify({
#             "error": "Gemini API rate limit reached. Please try again in a minute."
#         }), 429

#     # 🧩 Handle any other unexpected errors
#     except Exception as e:
#         print(f"❌ Flask summarize() error: {e}")
#         return jsonify({"error": str(e)}), 500

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import openai
from summary import get_summary

app = Flask(__name__)
CORS(app)  # ✅ allow frontend (React/Next.js) access from another origin

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "✅ Flask summarizer API running on Render"}), 200


@app.route("/summarize", methods=["POST"])
def summarize():
    try:
        # ---- Parse incoming JSON safely ----
        data = request.get_json(force=True)
        yt_url = data.get("youtube_link") or data.get("youtube_url")
        if not yt_url:
            return jsonify({"error": "Missing YouTube URL in request"}), 400

        # ---- Load API key from Render env vars ----
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("❌ Missing OPENAI_API_KEY in Render environment!")
            return jsonify({"error": "Missing OPENAI_API_KEY environment variable"}), 500

        # ---- Core summarization ----
        result = get_summary(yt_url, openai_api_key)

        return jsonify({
            "summary": result.get("summary", "").strip(),
            "transcript": result.get("transcript", "").strip()
        }), 200

    # ---- Handle OpenAI rate limit explicitly ----
    except openai.error.RateLimitError:
        return jsonify({
            "error": "OpenAI API rate limit reached. Try again later."
        }), 429

    # ---- Catch-all error (log for Render) ----
    except Exception as e:
        print(f"❌ Flask summarize() error: {e}")
        return jsonify({"error": str(e)}), 500


# ---- Render deployment safe ----
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render dynamically assigns port
    app.run(host="0.0.0.0", port=port, debug=False)
