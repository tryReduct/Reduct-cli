import os
from dotenv import load_dotenv
import subprocess
from google import genai
from google.genai import types
import asyncio
from pathlib import Path

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def compress_video(input_path: str, output_path: str) -> str:
    """Compress video to reduce size while maintaining reasonable quality."""
    command = [
        "ffmpeg",
        "-i",
        input_path,
        "-vf",
        "scale=1280:-1",  # Scale to 1280 width, maintain aspect ratio
        "-c:v",
        "libx264",
        "-crf",
        "23",  # Good quality compression
        "-preset",
        "fast",  # Change from "medium" to "fast" for better speed
        "-y",    # Add -y to overwrite without asking
        output_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to compress video: {result.stderr}")
    return output_path


async def index_video(video_path: str):
    print(f"Indexing video: {video_path}")

    # Compress video first
    compressed_path = video_path.replace(".mp4", "_compressed.mp4")
    try:
        compressed_path = compress_video(video_path, compressed_path)
    except Exception as e:
        print(f"Warning: Could not compress video: {e}")
        compressed_path = video_path  # Fallback to original if compression fails

    try:
        video_bytes = open(compressed_path, "rb").read()
        prompt = """
        Every time there is a new scene detected, please provide a summary of the scene in 3 sentences. also give a timestamps of the scene.
        """
        response = gemini_client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=types.Content(
                parts=[
                    types.Part(
                        inline_data=types.Blob(data=video_bytes, mime_type="video/mp4")
                    ),
                    types.Part(text=prompt),
                ]
            ),
        )
        summary_path = os.path.join(
            "outputs", "summary", f"{os.path.basename(video_path)}.txt"
        )
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
        with open(summary_path, "w") as f:
            f.write(response.text)
        return response.text
    finally:
        # Clean up compressed file if it was created
        if compressed_path != video_path and os.path.exists(compressed_path):
            os.remove(compressed_path)


async def extract_audio(video_path: str):
    print(f"Indexing video: {video_path}")

    output_path = os.path.join(
        "outputs", "audio", f"{os.path.basename(video_path)}.mp3"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        extract_audio_command = subprocess.run(
            ["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", output_path],
            capture_output=True,
            text=True,
        )
        if extract_audio_command.returncode != 0:
            raise Exception(f"Failed to extract audio: {extract_audio_command.stderr}")

        with open(output_path, "rb") as f:
            audio_bytes = f.read()

        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                "generate a transcript of the audio",
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type="audio/mp3",
                ),
            ],
        )

        transcript_path = os.path.join(
            "outputs", "transcript", f"{os.path.basename(video_path)}.txt"
        )
        os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
        with open(transcript_path, "w") as f:
            f.write(response.text)
        return transcript_path
    except Exception as e:
        print(f"Error in audio processing: {e}")
        raise


def validate_video_path(video_path: str) -> str:
    """
    Validate and normalize the video path.
    Returns the absolute path if valid, raises an exception otherwise.
    """
    # Strip quotes from the path if present
    video_path = video_path.strip("'\"")
    
    # Convert to Path object for better handling
    path = Path(video_path)
    
    # Convert to absolute path
    abs_path = path.absolute()
    
    # Check if file exists
    if not abs_path.exists():
        raise FileNotFoundError(f"Video file not found at: {abs_path}")
    
    # Check if it's a file
    if not abs_path.is_file():
        raise ValueError(f"Path is not a file: {abs_path}")
    
    # Check if it's a video file (basic check)
    if not abs_path.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv', '.wmv']:
        raise ValueError(f"File is not a supported video format: {abs_path}")
    
    return str(abs_path)


async def main():
    print("Welcome to Reduct CLI")
    while True:
        try:
            video_path = input("Enter the video path: ")
            video_path = validate_video_path(video_path)
            break
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}")
            print("Please try again with a valid video path.")
            continue

    # Create necessary directories
    os.makedirs("outputs/summary", exist_ok=True)
    os.makedirs("outputs/audio", exist_ok=True)
    os.makedirs("outputs/transcript", exist_ok=True)

    try:
        # Run both processes concurrently
        video_task = asyncio.create_task(index_video(video_path))
        audio_task = asyncio.create_task(extract_audio(video_path))

        # Wait for both tasks to complete
        await asyncio.gather(video_task, audio_task)

        print("Processing complete!")
        print("Find your summary in the `outputs/summary` directory")
        print("Find your transcript in the `outputs/transcript` directory")

    except Exception as e:
        print(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
