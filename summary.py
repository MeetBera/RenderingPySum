import sys
import os
import tempfile
import json
import google.generativeai as genai
import yt_dlp
import contextlib

def configure_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)

def download_audio(url):
    temp_dir = "/tmp"
    audio_path = os.path.join(temp_dir, "audio.%(ext)s")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [],
        "format": "bestaudio/best",
        "outtmpl": audio_path,
        "cookiefile": "youtube.com_cookies.txt",
        "headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    try:
        with contextlib.redirect_stdout(open(os.devnull, "w")), contextlib.redirect_stderr(open(os.devnull, "w")):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        final_path = audio_path.replace("%(ext)s", "mp3")
        if not os.path.exists(final_path):
            raise FileNotFoundError("Audio file not created")
        return final_path

    except Exception as e:
        print(f"Audio download failed: {e}", file=sys.stderr)
        return None


def transcribe_with_gemini(audio_path):
    model = genai.GenerativeModel("gemini-2.5-flash")
    with open(audio_path, "rb") as audio_file:
        response = model.generate_content([
            {"mime_type": "audio/mp3", "data": audio_file.read()},
            "Transcribe this audio accurately in English."
        ])
    return response.text


def explain_with_gemini(transcript, title="", description=""):
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    You are an intelligent API. Explain the given YouTube transcript in clear, factual English.
    Use the title and description as context.
    Return only the explanation as plain text.

    Title: {title}
    Description: {description}
    Transcript: {transcript}
    """
    response = model.generate_content(prompt)
    return response.text
