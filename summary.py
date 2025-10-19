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

# import os
# import textwrap
# import subprocess
# import wave
# import json
# from urllib.parse import urlparse, parse_qs

# import google.generativeai as genai
# from youtube_transcript_api import YouTubeTranscriptApi
# from pytube import YouTube
# from vosk import Model, KaldiRecognizer


# # ----------------------------
# # Extract video ID from YouTube URL
# # ----------------------------
# def get_video_id(yt_url):
#     parsed_url = urlparse(yt_url)
#     if parsed_url.hostname in ["youtu.be"]:
#         return parsed_url.path[1:]
#     elif parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
#         return parse_qs(parsed_url.query).get("v", [None])[0]
#     return None


# # ----------------------------
# # Try to get transcript via YouTube captions
# # ----------------------------
# def get_transcript_youtube(video_id):
#     try:
#         transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["hi", "en"])
#         transcript = " ".join([t["text"] for t in transcript_list])
#         print("✅ Transcript fetched from YouTube captions.")
#         return transcript
#     except Exception as e:
#         print(f"⚠️ YouTube captions not available: {e}")
#         return None


# # ----------------------------
# # Fallback: Get transcript using Vosk (offline)
# # ----------------------------
# def get_transcript_vosk(yt_url):
#     print("🎧 Falling back to Vosk (offline speech recognition)...")

#     # Step 1: Download audio
#     yt = YouTube(yt_url)
#     audio_stream = yt.streams.filter(only_audio=True).first()
#     audio_path = "audio.mp4"
#     audio_stream.download(filename=audio_path)

#     # Step 2: Convert to WAV (mono, 16kHz)
#     wav_path = "audio.wav"
#     subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", wav_path],
#                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

#     # Step 3: Load Vosk model
#     model_dir = "vosk-model-small-en-us-0.15"
#     if not os.path.exists(model_dir):
#         raise RuntimeError("Vosk model not found. Download it from: "
#                            "https://alphacephei.com/vosk/models")

#     wf = wave.open(wav_path, "rb")
#     rec = KaldiRecognizer(Model(model_dir), wf.getframerate())

#     result_text = ""
#     while True:
#         data = wf.readframes(4000)
#         if len(data) == 0:
#             break
#         if rec.AcceptWaveform(data):
#             result_text += json.loads(rec.Result()).get("text", "") + " "

#     wf.close()
#     os.remove(audio_path)
#     os.remove(wav_path)

#     print("✅ Transcript extracted using Vosk.")
#     return result_text


# # -------------------------------------------------
# # Chunk-based explanation using Gemini
# # -------------------------------------------------
# def explain_in_chunks(transcript, gemini_api_key, chunk_size=1000):
#     genai.configure(api_key=gemini_api_key)
#     gemini_model = genai.GenerativeModel("gemini-1.5-flash")

#     chunks = textwrap.wrap(transcript, chunk_size)
#     explanations = []

#     for i, chunk in enumerate(chunks, start=1):
#         print(f"🧠 Processing chunk {i}/{len(chunks)}...")

#         prompt = f"""
#         Explain the following text in simple, human-like bullet points:
#         {chunk}
#         """

#         for attempt in range(5):
#             try:
#                 response = gemini_model.generate_content(prompt)
#                 explanations.append(response.text)
#                 break
#             except google_exceptions.ResourceExhausted:
#                 wait = (attempt + 1) * 5
#                 print(f"⏳ Rate limit hit — waiting {wait}s before retry...")
#                 time.sleep(wait)
#             except Exception as e:
#                 print(f"⚠️ Gemini error on chunk {i}: {e}")
#                 time.sleep(2)
#                 break

#     return "\n\n".join(explanations)


# # -----------------------------------------
# # Main: Get summary from YouTube
# # -----------------------------------------
# def get_summary(yt_url, gemini_api_key):
#     video_id = get_video_id(yt_url)
#     if not video_id:
#         raise ValueError("Invalid YouTube URL or missing video ID")

#     # Try YouTube transcript first
#     transcript = get_transcript_youtube(video_id)

#     # If unavailable, fallback to Vosk
#     if not transcript or len(transcript.strip()) < 10:
#         transcript = get_transcript_vosk(yt_url)

#     if not transcript:
#         raise RuntimeError("Failed to get transcript via both YouTube and Vosk.")

#     print("📝 Transcript preview:\n", transcript[:500] + "...")
#     summary = explain_in_chunks(transcript, gemini_api_key)

#     return {
#         "transcript": transcript,
#         "summary": summary
#     }

import os
import textwrap
import subprocess
import wave
import json
import tempfile
import urllib.request
from urllib.parse import urlparse, parse_qs
from http.client import IncompleteRead

from openai import OpenAI, OpenAIError
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
from vosk import Model, KaldiRecognizer


# ----------------------------
# Extract video ID from YouTube URL
# ----------------------------
def get_video_id(yt_url):
    parsed_url = urlparse(yt_url)
    if parsed_url.hostname in ["youtu.be"]:
        return parsed_url.path[1:]
    elif parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
        return parse_qs(parsed_url.query).get("v", [None])[0]
    return None


# ----------------------------
# Try to get transcript via YouTube captions (modern version)
# ----------------------------
def get_transcript_youtube(video_id):
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try Hindi or English transcript
        for lang in ["hi", "en"]:
            try:
                t = transcripts.find_transcript([lang])
                transcript = " ".join([seg["text"] for seg in t.fetch()])
                print(f"✅ Transcript fetched in {lang.upper()} from YouTube captions.")
                return transcript
            except Exception:
                continue

        print("⚠️ No valid transcript language found.")
        return None

    except Exception as e:
        print(f"⚠️ YouTube captions not available: {e}")
        return None


# ----------------------------
# Fallback: Get transcript using Vosk (offline)
# ----------------------------
def get_transcript_vosk(yt_url):
    print("🎧 Using Vosk for offline speech recognition...")

    try:
        yt = YouTube(yt_url)
        audio_stream = yt.streams.filter(only_audio=True).first()

        # Use temporary directory (Render-safe ephemeral FS)
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp4")
            wav_path = os.path.join(tmpdir, "audio.wav")

            print("⬇️ Downloading YouTube audio...")
            audio_stream.download(filename=audio_path)

            print("🔄 Converting to WAV...")
            subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", wav_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            model_dir = os.path.join(tmpdir, "vosk-model-small-en-us-0.15")
            if not os.path.exists(model_dir):
                print("📦 Downloading Vosk model...")
                model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
                zip_path = os.path.join(tmpdir, "vosk_model.zip")
                urllib.request.urlretrieve(model_url, zip_path)
                subprocess.run(["unzip", "-q", zip_path, "-d", tmpdir])

            wf = wave.open(wav_path, "rb")
            rec = KaldiRecognizer(Model(model_dir), wf.getframerate())

            result_text = ""
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    result_text += json.loads(rec.Result()).get("text", "") + " "

            wf.close()

        print("✅ Transcript created using Vosk.")
        return result_text.strip()

    except Exception as e:
        print(f"❌ Vosk transcription failed: {e}")
        return None


# -------------------------------------------------
# Chunk-based summarization using OpenAI (no retry)
# -------------------------------------------------
def explain_in_chunks(transcript, openai_api_key, chunk_size=1500):
    client = OpenAI(api_key=openai_api_key)
    chunks = textwrap.wrap(transcript, chunk_size)
    explanations = []

    for i, chunk in enumerate(chunks, start=1):
        print(f"🧠 Summarizing chunk {i}/{len(chunks)}...")

        try:
            response = client.chat.completions.create(
                model="gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are a concise and human-like summarizer."},
                    {"role": "user", "content": f"Summarize this in bullet points:\n\n{chunk}"}
                ],
                temperature=0.5,
                max_tokens=800,
            )
            content = response.choices[0].message.content.strip()
            explanations.append(content)

        except OpenAIError as e:
            print(f"❌ OpenAI error on chunk {i}: {e}")
            raise RuntimeError(f"OpenAI summarization failed: {e}")

        except IncompleteRead:
            print("⚠️ Incomplete response from API. Stopping early.")
            break

    return "\n\n".join(explanations)


# -----------------------------------------
# Main: Get summary from YouTube
# -----------------------------------------
def get_summary(yt_url, openai_api_key=None):
    if not openai_api_key:
        openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment or argument.")

    video_id = get_video_id(yt_url)
    if not video_id:
        raise ValueError("Invalid YouTube URL or missing video ID.")

    transcript = get_transcript_youtube(video_id)
    if not transcript or len(transcript.strip()) < 10:
        print("⚠️ Falling back to Vosk transcription...")
        transcript = get_transcript_vosk(yt_url)

    if not transcript:
        raise RuntimeError("Failed to obtain transcript via both YouTube and Vosk.")

    print("📝 Transcript preview:\n", transcript[:400] + "...")
    summary = explain_in_chunks(transcript, openai_api_key)
    return {"transcript": transcript, "summary": summary}
