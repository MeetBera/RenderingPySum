import sys
import os
import tempfile
import json
import google.generativeai as genai
import yt_dlp
import contextlib
import requests

def configure_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)

def download_audio(url):
    try:
        video_id = url.split("v=")[-1]

        api_url = f"https://pipedapi.kavin.rocks/streams/{video_id}"

        r = requests.get(api_url, timeout=10)
        info = r.json()

        # Get the highest-quality audio stream URL
        audio_url = info["audioStreams"][0]["url"]

        # Download audio directly
        tmp = tempfile.mkdtemp()
        file_path = os.path.join(tmp, "audio.mp3")

        with requests.get(audio_url, stream=True) as resp:
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

        return file_path

    except Exception as e:
        print("Audio download failed:", e)
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
