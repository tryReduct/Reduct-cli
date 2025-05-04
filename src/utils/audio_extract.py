import os 
import subprocess
import json 
import asyncio


async def extract_audio(video_path: str, output_dir: str):
    """
    Extract audio from a video file and save it as an MP3 file.

    Args:
        video_path (str): The path to the video file.
        output_dir (str): The directory to save the extracted audio.
    """ 
    try:
        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Get the base name of the video file
        base_name = os.path.splitext(os.path.basename(video_path))[0]

        # Define the output file path
        output_file = os.path.join(output_dir, f"{base_name}.mp3")

        # Use ffmpeg to extract audio with suppressed output
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", video_path, "-q:a", "0", "-map", "0:a", output_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for the process to complete
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"FFmpeg failed: {stderr.decode()}")
            
        print(f"Audio extracted successfully and saved to: {output_file}")
        return output_file
    except Exception as e:
        raise Exception(f"Failed to extract audio: {str(e)}")
    

async def main():
    video_path = input("Enter the video path: ")
    output_dir = "outputs/audio"
    return await extract_audio(video_path, output_dir)

if __name__ == "__main__":
    asyncio.run(main())
