import os
from dotenv import load_dotenv
import subprocess
from google import genai
from google.genai import types
import asyncio
from pathlib import Path
from rich import print
from rich.progress import Progress
from rich.console import Console
from art import * 
from openai import OpenAI
load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

async def index_video(video_path: str):
    with Progress() as progress:
        # Create tasks for different stages
        compression_task = progress.add_task("[cyan]Compressing video...", total=100)
        processing_task = progress.add_task("[green]Processing with Gemini...", total=100)
        
        # Compress video first
        compressed_path = video_path.replace(".mp4", "_compressed.mp4")
        try:
            compressed_path = compress_video(video_path, compressed_path)
            progress.update(compression_task, completed=100)
        except Exception as e:
            print(f"Warning: Could not compress video: {e}")
            compressed_path = video_path  # Fallback to original if compression fails
            progress.update(compression_task, completed=100)

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
            progress.update(processing_task, completed=100)
            
            # Get unique file path for summary
            summary_path = os.path.join(
                "outputs", "summary", f"{os.path.basename(video_path)}.txt"
            )
            summary_path = get_unique_file_path(summary_path)
            
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, "w") as f:
                f.write(response.text)
            return response.text
        finally:
            # Clean up compressed file if it was created
            if compressed_path != video_path and os.path.exists(compressed_path):
                os.remove(compressed_path)


async def extract_audio(video_path: str):
    with Progress() as progress:
        # Create tasks for different stages
        extraction_task = progress.add_task("[cyan]Extracting audio...", total=100)
        transcription_task = progress.add_task("[green]Transcribing audio...", total=100)

        # Get unique file path for audio
        output_path = os.path.join(
            "outputs", "audio", f"{os.path.basename(video_path)}.mp3"
        )
        output_path = get_unique_file_path(output_path)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            extract_audio_command = subprocess.run(
                ["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", output_path],
                capture_output=True,
                text=True,
            )
            if extract_audio_command.returncode != 0:
                raise Exception(f"Failed to extract audio: {extract_audio_command.stderr}")
            progress.update(extraction_task, completed=100)

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
            progress.update(transcription_task, completed=100)

            # Get unique file path for transcript
            transcript_path = os.path.join(
                "outputs", "transcript", f"{os.path.basename(video_path)}.txt"
            )
            transcript_path = get_unique_file_path(transcript_path)
            
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

async def edit_video(prompt: str, input_path: str) -> str:
    with Progress() as progress:
        edit_task = progress.add_task("[green]Editing video...", total=100)
        """
        Edit a video based on user prompt using Gemini to generate FFmpeg commands.
        
        Args:
            prompt (str): User's editing instructions
            input_path (str): Path to the input video file
            
        Returns:
            str: Path to the edited video
            
        Raises:
            ValueError: If the generated command is invalid
            subprocess.CalledProcessError: If FFmpeg command fails
        """
        # Create output directory if it doesn't exist
        output_dir = os.path.join("outputs", "edited")
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output path
        output_path = os.path.join(
            output_dir,
            f"{os.path.splitext(os.path.basename(input_path))[0]}_edited.mp4"
        )
        
        # Create a more structured prompt for Gemini
        prompt_for_gemini = f"""
        Generate an FFmpeg command to edit a video based on these requirements:
        - Input video path: {input_path}
        - Output video path: {output_path}
        - User's request: {prompt}
        
        Return ONLY the FFmpeg command as a list of arguments, one per line.
        Do not include any explanations or additional text.
        The command should:
        1. Use the input path provided
        2. Save to the output path provided
        3. Include -y flag to overwrite existing files
        4. Use proper FFmpeg filter syntax
        5. Be safe and valid FFmpeg syntax
        6. Include both video and audio streams
        7. For filter_complex, use this exact format for each segment:
           [0:v]trim=start=START:end=END,setpts=PTS-STARTPTS[vN];
           [0:a]atrim=start=START:end=END,asetpts=PTS-STARTPTS[aN];
           Where N is the segment number (1, 2, 3, etc.) and START/END are timestamps.
        8. End with proper concatenation like: [v1][a1][v2][a2]concat=n=2:v=1:a=1[out]
        9. Use proper -map [out] to map the output stream
        """
        
        try:
            # Get command from Gemini
            response = gemini_client.models.generate_content(
                model="models/gemini-2.0-flash",
                contents=[prompt_for_gemini]
            )
            
            # Parse the response into a command list
            command = response.text.strip().split('\n')
            
            # Clean up the command list
            command = [arg.strip() for arg in command if arg.strip() and not arg.strip().startswith('```')]
            
            # Ensure the first command is ffmpeg
            if command[0].lower() != "ffmpeg":
                command.insert(0, "ffmpeg")
            
            # Validate command structure
            if not command or not all(isinstance(arg, str) for arg in command):
                raise ValueError("Invalid command format generated by Gemini")
            
            # Add -y flag if not present
            if "-y" not in command:
                command.insert(1, "-y")
            
            # Add input path if not present
            if input_path not in command:
                command.insert(2, "-i")
                command.insert(3, input_path)
            
            # Add output path if not present
            if output_path not in command:
                command.append(output_path)
            
            # Remove outer quotes from all arguments
            for i, arg in enumerate(command):
                if arg.startswith('"') and arg.endswith('"'):
                    command[i] = arg[1:-1]  # Remove outer quotes
                elif arg.startswith("'") and arg.endswith("'"):
                    command[i] = arg[1:-1]  # Remove outer quotes
            
            # Handle filter_complex specially
            filter_complex_index = -1
            for i, arg in enumerate(command):
                if arg == '-filter_complex':
                    filter_complex_index = i
                    break
            
            if filter_complex_index != -1:
                # Get the filter complex parts
                filter_parts = []
                i = filter_complex_index + 1
                while i < len(command) and not command[i].startswith('-'):
                    filter_parts.append(command[i])
                    command.pop(i)
                
                # Join all parts into a single string
                filter_complex = ''.join(filter_parts)
                
                # Clean up the filter complex
                filter_complex = filter_complex.replace('"', '').replace("'", '')
                
                # Fix common formatting issues
                # Ensure segments are properly separated by semicolons
                import re
                
                # Fix video segment patterns
                video_segments = re.findall(r'\[0:v\]trim=start=\d+:end=\d+,setpts=PTS-STARTPTS\[?v?\d*\]?', filter_complex)
                for segment in video_segments:
                    if not segment.endswith(';'):
                        fixed_segment = segment
                        if not re.search(r'\[v\d+\]$', fixed_segment):
                            # Extract the segment number or add one
                            segment_num = re.search(r'trim=start=(\d+)', segment)
                            segment_id = segment_num.group(1) if segment_num else '1'
                            fixed_segment = re.sub(r'setpts=PTS-STARTPTS(?:\[?v?\d*\]?)?$', f'setpts=PTS-STARTPTS[v{segment_id}]', fixed_segment)
                        filter_complex = filter_complex.replace(segment, fixed_segment + ';')
                
                # Fix audio segment patterns
                audio_segments = re.findall(r'\[0:a\]atrim=start=\d+:end=\d+,asetpts=PTS-STARTPTS\[?a?\d*\]?', filter_complex)
                for segment in audio_segments:
                    if not segment.endswith(';'):
                        fixed_segment = segment
                        if not re.search(r'\[a\d+\]$', fixed_segment):
                            # Extract the segment number or add one
                            segment_num = re.search(r'atrim=start=(\d+)', segment)
                            segment_id = segment_num.group(1) if segment_num else '1'
                            fixed_segment = re.sub(r'asetpts=PTS-STARTPTS(?:\[?a?\d*\]?)?$', f'asetpts=PTS-STARTPTS[a{segment_id}]', fixed_segment)
                        filter_complex = filter_complex.replace(segment, fixed_segment + ';')
                
                # Fix the concat filter if needed
                if 'concat=' in filter_complex and not filter_complex.endswith('[out]'):
                    filter_complex = filter_complex.replace('concat=n', ';concat=n')
                    filter_complex = re.sub(r'concat=n=\d+:v=1:a=1(?:\[out\])?$', r'concat=n=\1:v=1:a=1[out]', filter_complex)
                
                # Remove any double semicolons
                filter_complex = filter_complex.replace(';;', ';')
                
                # Find how many segments we have
                segment_count = len(re.findall(r'\[v\d+\]', filter_complex))
                
                # Fix the concat input part if needed
                concat_pattern = r'\[v1\]\[a1\](?:\[v2\]\[a2\])?(?:\[v3\]\[a3\])?concat=n=\d+:v=1:a=1\[out\]'
                if not re.search(concat_pattern, filter_complex):
                    # Build proper concat inputs
                    concat_inputs = ''.join([f'[v{i+1}][a{i+1}]' for i in range(segment_count)])
                    concat_filter = f'{concat_inputs}concat=n={segment_count}:v=1:a=1[out]'
                    
                    # Replace existing concat filter or append if not found
                    if 'concat=n=' in filter_complex:
                        filter_complex = re.sub(r'(?:;)?(?:\[v\d+\]\[a\d+\])*concat=n=\d+:v=1:a=1(?:\[out\])?', ';' + concat_filter, filter_complex)
                    else:
                        filter_complex += ';' + concat_filter
                
                # Insert the fixed filter_complex back into the command
                command.insert(filter_complex_index + 1, filter_complex)
            
            # Ensure proper stream mapping
            map_index = -1
            for i, arg in enumerate(command):
                if arg == '-map':
                    map_index = i
                    break
            
            if map_index == -1:
                command.append('-map')
                command.append('[out]')
            elif map_index + 1 < len(command) and command[map_index + 1] == '':
                command[map_index + 1] = '[out]'
            
            # Print the command for debugging
            print("Executing FFmpeg command:", " ".join(command))
            
            # Execute FFmpeg command
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True  # This will raise CalledProcessError if command fails
            )
            progress.update(edit_task, completed=80)
            
            if result.returncode != 0:
                print("FFmpeg error output:", result.stderr)
                raise subprocess.CalledProcessError(
                    result.returncode,
                    command,
                    result.stderr
                )
            
            progress.update(edit_task, completed=100)
            print(art("cute_face"), "[bold purple]Video edited successfully![/bold purple]", (art("cute_face")))
            print(art("yessir"), f"Video saved to: {output_path}", (art("yessir")))
            return output_path
            
        except Exception as e:
            print(f"Error editing video: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                print("FFmpeg error output:", e.stderr)
            raise


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
        video_task = asyncio.create_task(index_video(video_path))
        audio_task = asyncio.create_task(extract_audio(video_path))

        # Wait for both tasks to complete
        await asyncio.gather(video_task, audio_task)

        # with yaspin.yaspin(text="Processing", color="cyan") as spinner:
        #         time.sleep(2)
        #         spinner.ok("✅")
                
        print("Processing complete!")
        print("Find your summary in the `outputs/summary` directory")
        print("Find your transcript in the `outputs/transcript` directory")
        print("[bold green]What do you want to do next?[/bold green]")
        print("[bold green]1. Edit Video[/bold green]")
        print("[bold green]2. Index Another Video[/bold green]")
        print("[bold green]3. Exit[/bold green]")
        choice = input("Enter your choice: ")
        if choice == "1":
            prompt = input("What do you want to do with the video? ")
            print(art("wizard"), "[bold purple]These wizards are working on your masterpiece...[/bold purple]", (art("wizard")))
            await edit_video(prompt, video_path)
            
        elif choice == "2":
            print('option 2')
        elif choice == "3":
            print('Exiting...')
        else: 
            print('invalid option')
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
