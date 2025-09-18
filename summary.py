import os
import yt_dlp
from urllib.parse import urlparse, parse_qs
import torch
import whisper
import google.generativeai as genai
import textwrap

def get_video_id(yt_url):
    parsed_url = urlparse(yt_url)
    if parsed_url.hostname in ["youtu.be"]:
        return parsed_url.path[1:]
    elif parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
        return parse_qs(parsed_url.query).get("v", [None])[0]
    return None

def download_audio_as_id(yt_url, save_dir):
    video_id = get_video_id(yt_url)
    if not video_id:
        raise ValueError("Invalid YouTube URL or missing video ID")

    output_file = os.path.join(save_dir, f"{video_id}.mp3")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(save_dir, "%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "retries": 10,
        "fragment_retries": 10,
        "ignoreerrors": False,  # stop if error
        "noplaylist": True,
    }

    cookies_file = os.path.join(os.getcwd(), "cookies.txt")
    if os.path.exists(cookies_file):
        ydl_opts["cookiefile"] = cookies_file
        print("✅ Using cookies.txt for YouTube authentication")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([yt_url])

    if not os.path.exists(output_file):
        raise RuntimeError("❌ Audio download failed")

    print(f"✅ Audio saved at: {output_file}")
    return output_file

def summarize_youtube_video(youtube_link, save_directory):
    audio_path = download_audio_as_id(youtube_link, save_directory)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("medium", device=device)
    result = model.transcribe(audio_path, task="translate")
    transcript = result["text"]

    if not transcript.strip():
        raise RuntimeError("❌ Whisper returned empty transcript")

    print("Transcript:\n", transcript)

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model_gemini = genai.GenerativeModel("gemini-1.5-flash")

    def explain_in_chunks(transcript, chunk_size=3000):
        chunks = textwrap.wrap(transcript, chunk_size)
        explanations = []
        for i, chunk in enumerate(chunks, start=1):
            prompt = f"""
            Explain this in very simple language + give summary in bullet points:
            {chunk}
            """
            print(f"Processing chunk {i}/{len(chunks)}...")
            response = model_gemini.generate_content(prompt)
            explanations.append(response.text)
        return "\n\n".join(explanations)

    final_explanation = explain_in_chunks(transcript)
    if not final_explanation.strip():
        raise RuntimeError("❌ Gemini returned empty summary")

    return final_explanation
