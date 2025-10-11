# import os
# import yt_dlp
# from urllib.parse import urlparse, parse_qs
# import torch
# import whisper
# import google.generativeai as genai
# import textwrap
# import shutil


# def get_video_id(yt_url):
#     parsed_url = urlparse(yt_url)
#     if parsed_url.hostname in ["youtu.be"]:
#         return parsed_url.path[1:]
#     elif parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
#         return parse_qs(parsed_url.query).get("v", [None])[0]
#     return None


# def get_cookie_file():
#     """
#     Returns a safe, writable path to the cookies file.
#     On Render, copy from /etc/secrets/ to /tmp/ because secrets are read-only.
#     """
#     render_path = "/etc/secrets/cookies.txt"
#     if os.path.exists(render_path):
#         tmp_copy = "/tmp/cookies.txt"
#         if not os.path.exists(tmp_copy):  # copy only once
#             shutil.copy(render_path, tmp_copy)
#         return tmp_copy

#     # Local fallback
#     for name in ["cookies.txt", "youtube.com_cookies.txt"]:
#         local_path = os.path.join(os.getcwd(), name)
#         if os.path.exists(local_path):
#             return local_path

#     return None


# def download_audio_as_id(yt_url, save_dir):
#     video_id = get_video_id(yt_url)
#     if not video_id:
#         raise ValueError("Invalid YouTube URL or missing video ID")

#     output_file = os.path.join(save_dir, f"{video_id}.mp3")

#     ydl_opts = {
#         "format": "bestaudio/best",
#         "outtmpl": os.path.join(save_dir, "%(id)s.%(ext)s"),
#         "postprocessors": [{
#             "key": "FFmpegExtractAudio",
#             "preferredcodec": "mp3",
#             "preferredquality": "192",
#         }],
#         "retries": 10,
#         "fragment_retries": 10,
#         "ignoreerrors": False,  # stop if error
#         "noplaylist": True,
#     }

#     # ✅ Safe cookies usage
#     cookies_file = get_cookie_file()
#     if cookies_file:
#         ydl_opts["cookiefile"] = cookies_file
#         print(f"✅ Using cookies for YouTube authentication: {cookies_file}")
#     else:
#         print("⚠️ No cookies file found, might fail on restricted videos")

#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         ydl.download([yt_url])

#     if not os.path.exists(output_file):
#         raise RuntimeError("❌ Audio download failed")

#     print(f"✅ Audio saved at: {output_file}")
#     return output_file


# def summarize_youtube_video(youtube_link, save_directory):
#     audio_path = download_audio_as_id(youtube_link, save_directory)

#     device = "cuda" if torch.cuda.is_available() else "cpu"
#     model = whisper.load_model("medium", device=device)
#     result = model.transcribe(audio_path, task="translate")
#     transcript = result["text"]

#     if not transcript.strip():
#         raise RuntimeError("❌ Whisper returned empty transcript")

#     print("Transcript:\n", transcript)

#     # ✅ Use ENV var for API key (don’t hardcode!)
#     genai.configure(api_key=os.environ["GEMINI_API_KEY"])
#     model_gemini = genai.GenerativeModel("gemini-1.5-flash")

#     def explain_in_chunks(transcript, chunk_size=3000):
#         chunks = textwrap.wrap(transcript, chunk_size)
#         explanations = []
#         for i, chunk in enumerate(chunks, start=1):
#             prompt = f"""
#             Explain this in very simple language + give summary in bullet points:
#             {chunk}
#             """
#             print(f"Processing chunk {i}/{len(chunks)}...")
#             response = model_gemini.generate_content(prompt)
#             explanations.append(response.text)
#         return "\n\n".join(explanations)

#     final_explanation = explain_in_chunks(transcript)
#     if not final_explanation.strip():
#         raise RuntimeError("❌ Gemini returned empty summary")

#     return final_explanation

# import os
# import yt_dlp
# from urllib.parse import urlparse, parse_qs
# import torch
# import whisper
# import google.generativeai as genai
# import textwrap

# # ----------------------------
# # Function to extract video ID
# # ----------------------------
# def get_video_id(yt_url):
#     parsed_url = urlparse(yt_url)
#     if parsed_url.hostname in ["youtu.be"]:
#         return parsed_url.path[1:]  # remove leading '/'
#     elif parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
#         return parse_qs(parsed_url.query).get("v", [None])[0]
#     return None

# # ---------------------------------------
# # Function to download audio from YouTube
# # ---------------------------------------
# def download_audio_as_id(yt_url, save_dir):
#     video_id = get_video_id(yt_url)
#     if not video_id:
#         raise ValueError("Invalid YouTube URL or missing video ID")

#     output_path = os.path.join(save_dir, f"{video_id}.mp3")

#     # Render secure cookies path
#     cookies_path = os.path.join(os.getcwd(), "youtube.com_cookies.txt")
#     print("Cookie file exists?", os.path.exists(cookies_path))
#     if not os.path.exists(cookies_path):
#         raise FileNotFoundError(
#             "YouTube cookies file not found! "
#             "Upload it as a Render secret file."
#         )

#     ydl_opts = {
#         'format': 'bestaudio/best',
#         'outtmpl': output_path,
#         'postprocessors': [{
#             'key': 'FFmpegExtractAudio',
#             'preferredcodec': 'mp3',
#             'preferredquality': '192',
#         }],
#         'quiet': True,
#         'no_warnings': True,
#         'cookiefile': cookies_path,  # ✅ Use secure file on Render
#         'cachedir': False,  # ✅ Disable writing cache
#     }

#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         ydl.download([yt_url])

#     print(f"Audio saved at: {output_path}")
#     return output_path

# # -------------------------------------------------
# # Helper function for chunk-based explanation
# # -------------------------------------------------
# def explain_in_chunks(transcript, gemini_api_key, chunk_size=3000):
#     genai.configure(api_key=gemini_api_key)
#     gemini_model = genai.GenerativeModel("gemini-1.5-flash")

#     chunks = textwrap.wrap(transcript, chunk_size)
#     explanations = []

#     for i, chunk in enumerate(chunks, start=1):
#         prompt = f"""
#         explain this {chunk} in very simple language + give summary in easy points
#         """
#         print(f"Processing chunk {i}/{len(chunks)}...")
#         response = gemini_model.generate_content(prompt)
#         explanations.append(response.text)

#     return "\n\n".join(explanations)

# # -----------------------------------------
# # Function to transcribe and summarize audio
# # -----------------------------------------
# def get_summary(audio_path, gemini_api_key):
#     device = "cuda" if torch.cuda.is_available() else "cpu"
#     model = whisper.load_model("medium", device=device)
#     result = model.transcribe(audio_path, task="translate", language="hi")
#     transcript = result["text"]

#     print("Transcript:\n", transcript[:500] + "...")

#     final_explanation = explain_in_chunks(transcript, gemini_api_key)
#     return final_explanation

import os
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
import textwrap

# ----------------------------
# Function to extract video ID
# ----------------------------
from urllib.parse import urlparse, parse_qs

def get_video_id(yt_url):
    parsed_url = urlparse(yt_url)
    if parsed_url.hostname in ["youtu.be"]:
        return parsed_url.path[1:]  # remove leading '/'
    elif parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
        return parse_qs(parsed_url.query).get("v", [None])[0]
    return None


# -------------------------------------------------
# Chunk-based transcript explanation using Gemini
# -------------------------------------------------
def explain_in_chunks(transcript, gemini_api_key, chunk_size=3000):
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")

    chunks = textwrap.wrap(transcript, chunk_size)
    explanations = []

    for i, chunk in enumerate(chunks, start=1):
        prompt = f"""
        Explain the following text in simple language and provide easy-to-read bullet points:
        {chunk}
        """
        print(f"Processing chunk {i}/{len(chunks)}...")
        response = gemini_model.generate_content(prompt)
        explanations.append(response.text)

    return "\n\n".join(explanations)


# -----------------------------------------
# Function to get transcript & summary
# -----------------------------------------
def get_summary_from_youtube(yt_url, gemini_api_key):
    video_id = get_video_id(yt_url)
    if not video_id:
        raise ValueError("Invalid YouTube URL or missing video ID")

    # Fetch transcript directly
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi','en'])
    except Exception as e:
        raise RuntimeError(f"Failed to fetch transcript: {str(e)}")

    transcript = " ".join([t['text'] for t in transcript_list])
    print("Transcript preview:\n", transcript[:500] + "...")

    summary = explain_in_chunks(transcript, gemini_api_key)

    return {
        "transcript": transcript,
        "summary": summary
    }

