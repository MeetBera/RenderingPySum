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

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import os
# from summary import get_summary

# app = Flask(__name__)
# CORS(app)  # Allow cross-origin access (for React/Next.js frontend)


# @app.route("/", methods=["GET"])
# def home():
#     return jsonify({"status": "✅ Flask summarizer API running"}), 200


# @app.route("/summarize", methods=["POST"])
# def summarize():
#     try:
#         data = request.get_json(force=True)
#         yt_url = data.get("youtube_link") or data.get("youtube_url")
#         if not yt_url:
#             return jsonify({"error": "Missing YouTube URL"}), 400

#         api_key = os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             return jsonify({"error": "Server missing OpenAI API key"}), 500

#         result = get_summary(yt_url, api_key)

#         return jsonify({
#             "summary": result.get("summary", "").strip(),
#             "transcript": result.get("transcript", "").strip()
#         }), 200

#     except Exception as e:
#         print(f"❌ Error: {type(e).__name__} - {e}")
#         return jsonify({"error": str(e)}), 500


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

from flask import Flask, request, jsonify
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
import tempfile
import os
import traceback

app = Flask(__name__)

# Initialize OpenAI client (Render has the API key set in environment)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def extract_video_id(youtube_url: str):
    """Extract the video ID from YouTube URL."""
    try:
        if "youtu.be" in youtube_url:
            return youtube_url.split("/")[-1]
        elif "youtube.com" in youtube_url:
            from urllib.parse import urlparse, parse_qs
            query = urlparse(youtube_url)
            return parse_qs(query.query).get("v", [None])[0]
    except Exception:
        return None


def get_youtube_captions(video_id: str):
    """Try to get English captions using YouTube Transcript API."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        text = " ".join([t['text'] for t in transcript])
        return text.strip()
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception as e:
        print(f"⚠️ Caption fetch error: {e}")
        return None


def transcribe_audio_from_youtube(video_url: str):
    """Download and transcribe audio using OpenAI Whisper."""
    try:
        yt = YouTube(video_url)
        audio_stream = yt.streams.filter(only_audio=True).first()

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_path = temp_file.name
            audio_stream.download(filename=temp_path)

        with open(temp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",  # or "whisper-1" for older model
                file=audio_file
            )

        os.remove(temp_path)
        return transcript.text
    except Exception as e:
        print(f"❌ Audio transcription failed: {e}")
        traceback.print_exc()
        return None


def summarize_text(text: str):
    """Summarize text using GPT model."""
    try:
        prompt = f"Summarize this YouTube video transcript in clear, concise bullet points:\n\n{text}"
        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # efficient and good for summaries
            messages=[
                {"role": "system", "content": "You are a helpful summarizer."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.5
        )
        summary = completion.choices[0].message.content.strip()
        return summary
    except Exception as e:
        print(f"❌ Summarization failed: {e}")
        traceback.print_exc()
        return None


@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "YouTube Summarizer Flask API"})


@app.route("/summarize", methods=["POST"])
def summarize_video():
    try:
        data = request.get_json()
        youtube_url = data.get("youtube_link")

        if not youtube_url:
            return jsonify({"error": "youtube_link missing"}), 400

        video_id = extract_video_id(youtube_url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL"}), 400

        print(f"🎥 Processing video: {youtube_url}")

        # Step 1: Try to get captions
        captions = get_youtube_captions(video_id)

        # Step 2: If no captions, transcribe audio
        if not captions:
            print("🗣 No captions found — using speech-to-text...")
            captions = transcribe_audio_from_youtube(youtube_url)
            if not captions:
                return jsonify({"error": "Failed to transcribe audio"}), 500

        # Step 3: Summarize
        print("🧠 Summarizing text...")
        summary = summarize_text(captions)
        if not summary:
            return jsonify({"error": "Failed to summarize text"}), 500

        print("✅ Summary generated successfully.")
        return jsonify({"summary": summary})

    except Exception as e:
        print("🔥 Unexpected error:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
