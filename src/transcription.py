'''
Write edge cases for teh transcription generation  (if file already exits or whatever)

use data structures for speed and store them systemically

'''

import os
from ffmpeg import FFmpeg
from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)


def extract_audio(video_path: str, output_path: str):
    ffmpeg = FFmpeg()
    ffmpeg.input(video_path).output(
        output_path,
        acodec='libmp3lame',
        loglevel='error'
    ).execute()
    
def transcribe_audio(audio_path: str):
    
    my_file = client.files.upload(file=audio_path)
    prompt = "Please transcribe the following audio file"
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt,my_file],
    ) 
    print(response.text)
    return response.text



def main():
    print("Hello from src!")
    extract_audio("sample.mp4", "audio.mp3")
    transcript = transcribe_audio("audio.mp3")
    with open("transcript.txt", "w") as f:
        f.write(transcript)


if __name__ == "__main__":
    main()
