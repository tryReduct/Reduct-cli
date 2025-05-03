import os
from dotenv import load_dotenv
from vision import compress_video,analyze_video
from google import genai
import asyncio
from pathlib import Path
from rich import print
from art import * 
from openai import OpenAI
load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def get_unique_file_path(base_path: str) -> str:
    """
    Generate a unique file path by adding an incrementing number if the file exists.
    
    Args:
        base_path (str): The original desired file path
        
    Returns:
        str: A unique file path that doesn't exist
    """
    if not os.path.exists(base_path):
        return base_path
        
    directory = os.path.dirname(base_path)
    filename, ext = os.path.splitext(os.path.basename(base_path))
    counter = 1
    
    while True:
        new_path = os.path.join(directory, f"{filename}_{counter}{ext}")
        if not os.path.exists(new_path):
            return new_path
        counter += 1

   

async def extract_audio(video_path: str):
    pass

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

async def clean_user_prompt(prompt: str) -> str:
    user_prompt = prompt.strip()
    with open('src/system_prompt.txt') as f:
        system_prompt = f.read()
    response = gemini_client.models.generate_content(
        model="models/gemini-2.0-flash",
        contents=[
            f'''
            You are a helpful assistant that cleans up user prompts for an ai powered video editor.
            Please clean up this user prompt {user_prompt} using the following system prompt:
            {system_prompt}
            '''
        ],
    )
    system_prompt = response.text
    return system_prompt


async def edit_video(system_prompt: str, input_path: str) -> str:
    pass


async def main():
    # tprint("Reduct CLI", font="broadway")
    print(art("cute_face"), "[bold purple]Welcome to Reduct CLI[/bold purple]", (art("cute_face")))
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
        video_task = asyncio.create_task(compress_video(analyze_video(video_path)))
        # audio_task = asyncio.create_task(extract_audio(video_path))

        # Wait for both tasks to complete
        await asyncio.gather(video_task)
        print("Processing complete!")
        print("How do you want to edit the video?: ")
        prompt = input("Enter your prompt: ")
        prompt = await clean_user_prompt(prompt)
        generated_video = await edit_video(prompt, video_path)
        print(f"Video generated successfully: {generated_video}")

    except Exception as e:
        print(f"An error occurred: {e}")
        raise
        


if __name__ == "__main__":
    asyncio.run(main())
