import subprocess
import json
import os
from pathlib import Path
from utils.video_index import compress_video,analyze_video
from google import genai
import asyncio
from pathlib import Path
from rich import print
from art import * 
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


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
    try:
        USER_REQUEST = prompt.strip()
        SYSTEM_PROMPT = Path('prompts/clean_user_prompt.txt').read_text(encoding='utf-8')
        response = gemini_client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=[
                f'''
                {SYSTEM_PROMPT},
                {USER_REQUEST}
                '''
            ],
        )
        os.makedirs('outputs/metadata', exist_ok=True)
        
        # Clean the response text to ensure it's valid JSON
        response_text = response.text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse and re-serialize to ensure clean JSON
        try:
            json_data = json.loads(response_text)
            with open('outputs/metadata/CLEAN_REQUEST.json', 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            return response_text
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from Gemini: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to clean user prompt: {str(e)}")

async def generate_ffmpeg_command(video_path: str):
    try:
        # Read and parse JSON files
        video_metadata_path = Path('outputs/metadata/VIDEO_METADATA.json')
        clean_request_path = Path('outputs/metadata/CLEAN_REQUEST.json')
        
        if not video_metadata_path.exists() or not clean_request_path.exists():
            raise FileNotFoundError("Required metadata files not found")
            
        video_metadata_text = video_metadata_path.read_text(encoding='utf-8')
        clean_request_text = clean_request_path.read_text(encoding='utf-8')
        
        try:
            video_metadata = json.loads(video_metadata_text)
            clean_request = json.loads(clean_request_text)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON format in metadata files: {str(e)}")
        
        # Get the compressed video path and output path
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        compressed_path = os.path.join("outputs", "compressed", f"{base_name}_compressed.mp4")
        output_path = os.path.join("outputs", "edited", f"{base_name}_edited.mp4")
        
        # Ensure the compressed video exists
        if not os.path.exists(compressed_path):
            raise FileNotFoundError(f"Compressed video not found at: {compressed_path}")
        
        # Read the system prompt and replace placeholders
        system_prompt = Path('prompts/generate_ffmpeg_command.txt').read_text(encoding='utf-8')
        system_prompt = system_prompt.replace('"input.mp4"', f'"{compressed_path}"')
        system_prompt = system_prompt.replace('"output.mp4"', f'"{output_path}"')
        
        # Prepare input for Gemini
        input_data = {
            "VIDEO_METADATA": video_metadata,
            "CLEAN_REQUEST": clean_request,
            "INPUT_PATH": compressed_path,
            "OUTPUT_PATH": output_path
        }
        
        response = gemini_client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=[
                system_prompt,
                json.dumps(input_data, indent=2)
            ]
        )
        
        # Clean the response text to remove any markdown markers
        command_text = response.text.strip()
        if command_text.startswith('```bash'):
            command_text = command_text[7:]
        if command_text.endswith('```'):
            command_text = command_text[:-3]
        command_text = command_text.strip()
        
        # Ensure the command uses the correct paths and properly formats filter_complex
        command_text = command_text.replace('input.mp4', compressed_path)
        command_text = command_text.replace('output.mp4', output_path)
        
        # Format the filter_complex part properly
        if '-filter_complex' in command_text:
            parts = command_text.split('-filter_complex')
            if len(parts) > 1:
                filter_part = parts[1].strip()
                # Remove any quotes around the filter
                filter_part = filter_part.strip('"\'')
                # Ensure proper spacing in the filter
                filter_part = ' '.join(filter_part.split())
                # Reconstruct the command
                command_text = parts[0] + '-filter_complex ' + filter_part
        
        # Save the cleaned command
        os.makedirs('outputs/ffmpeg_commands', exist_ok=True)
        with open('outputs/ffmpeg_commands/FFMPEG_COMMAND.txt', 'w', encoding='utf-8') as f:
            f.write(command_text)
        return command_text
    except Exception as e:
        raise Exception(f"Failed to generate ffmpeg command: {str(e)}")


async def edit_video(video_path: str):
    try:
        # Read and clean the command
        command_path = Path('outputs/ffmpeg_commands/FFMPEG_COMMAND.txt')
        if not command_path.exists():
            raise FileNotFoundError("FFmpeg command file not found")
            
        FFMPEG_COMMAND = command_path.read_text(encoding='utf-8').strip()
        
        # Clean the command again in case it was saved with markers
        if FFMPEG_COMMAND.startswith('```bash'):
            FFMPEG_COMMAND = FFMPEG_COMMAND[7:]
        if FFMPEG_COMMAND.endswith('```'):
            FFMPEG_COMMAND = FFMPEG_COMMAND[:-3]
        FFMPEG_COMMAND = FFMPEG_COMMAND.strip()
        
        # Create edited output directory if it doesn't exist
        os.makedirs("outputs/edited", exist_ok=True)
        
        # Split the command into parts, handling filter_complex specially
        command_parts = []
        current_part = []
        in_filter = False
        
        for part in FFMPEG_COMMAND.split():
            if part == '-filter_complex':
                in_filter = True
                if current_part:
                    command_parts.append(' '.join(current_part))
                    current_part = []
                command_parts.append(part)
            elif in_filter and part.endswith('"'):
                current_part.append(part[:-1])  # Remove the closing quote
                command_parts.append(' '.join(current_part))
                current_part = []
                in_filter = False
            elif in_filter:
                current_part.append(part)
            else:
                command_parts.append(part)
        
        if current_part:
            command_parts.append(' '.join(current_part))
        
        # Execute the command
        result = subprocess.run(command_parts, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"FFmpeg command failed: {result.stderr}")
            
        # Get the output file path
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join("outputs", "edited", f"{base_name}_edited.mp4")
        
        if not os.path.exists(output_path):
            raise Exception(f"Edited video was not created at: {output_path}")
            
        print(f"Video edited successfully and saved to: {output_path}")
        return output_path
    except Exception as e:
        raise Exception(f"Failed to edit video: {str(e)}")

async def main():
    while True:
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
        
        try:
            # Create necessary directories
            os.makedirs("outputs/metadata", exist_ok=True)
            os.makedirs("outputs/ffmpeg_commands", exist_ok=True)
            os.makedirs("outputs/edited", exist_ok=True)
            
            # Run both processes concurrently
            video_task = asyncio.create_task(compress_video(video_path))
            await analyze_video(video_path)

            # Wait for both tasks to complete
            await asyncio.gather(video_task)
            print("Processing complete!\n How do you want to edit the video?: ")
            prompt = input("Enter your prompt: ")
            await clean_user_prompt(prompt)
            await generate_ffmpeg_command(video_path)
            print("Edit command generated successfully")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Please try again or contact support if the issue persists.")
            break


if __name__ == "__main__":
    asyncio.run(main())
