import json
from pathlib import Path
import os
from rich import print
from rich.progress import Progress
import subprocess
from google import genai 
from google.genai import types
from dotenv import load_dotenv
import asyncio
import re


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")



gemini_client = genai.Client(api_key=GEMINI_API_KEY)

async def compress_video(input_path: str, for_gemini: bool = False) -> str:
    try:
        # Create outputs/compressed directory if it doesn't exist
        os.makedirs("outputs/compressed", exist_ok=True)
        
        # Generate output path with appropriate suffix
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        suffix = "_gemini.mp4" if for_gemini else "_compressed.mp4"
        output_path = os.path.join("outputs", "compressed", f"{base_name}{suffix}")
        
        # Check if input file exists
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input video not found at: {input_path}")
        
        """Compress video to reduce size while maintaining reasonable quality."""
        
        # Different compression settings for Gemini vs final output
        if for_gemini:
            # More aggressive compression for Gemini analysis
            command = [
                "ffmpeg",
                "-i",
                input_path,
                "-vf",
                "scale=640:-1",  # Lower resolution for Gemini
                "-c:v",
                "libx264",
                "-crf",
                "35",  # More aggressive compression
                "-preset",
                "ultrafast",  # Fastest compression
                "-r",
                "15",  # Lower frame rate
                "-y",
                output_path,
            ]
        else:
            # Standard compression for final output
            command = [
                "ffmpeg",
                "-i",
                input_path,
                "-vf",
                "scale=1280:-1",  # Standard resolution
                "-c:v",
                "libx264",
                "-crf",
                "23",  # Good quality compression
                "-preset",
                "fast",
                "-y",
                output_path,
            ]
            
        result = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to compress video: {result.stderr}")
        
        # Check file size and existence
        if not os.path.exists(output_path):
            raise Exception(f"Compressed video was not created at: {output_path}")
            
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Compressed video saved to: {output_path} (Size: {file_size:.2f}MB)")
        
        # If still too large for Gemini, try even more aggressive compression
        if for_gemini and file_size > 20:
            command = [
                "ffmpeg",
                "-i",
                input_path,
                "-vf",
                "scale=320:-1",  # Very low resolution
                "-c:v",
                "libx264",
                "-crf",
                "40",  # Very aggressive compression
                "-preset",
                "ultrafast",
                "-r",
                "10",  # Very low frame rate
                "-y",
                output_path,
            ]
            result = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to recompress video: {result.stderr}")
            
            if not os.path.exists(output_path):
                raise Exception(f"Recompressed video was not created at: {output_path}")
                
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"Recompressed video saved to: {output_path} (Size: {file_size:.2f}MB)")
            
            if file_size > 20:
                raise Exception("Unable to compress video to a size suitable for Gemini analysis")
        
        return output_path
    except Exception as e:
        raise Exception(f"Failed to compress video: {str(e)}")


async def analyze_video(video_path: str) -> str:
    """Analyze video using Gemini and return the analysis result."""
    try:
        # First compress the video specifically for Gemini analysis
        gemini_video_path = await compress_video(video_path, for_gemini=True)
        
        # Read the compressed video file
        with open(gemini_video_path, 'rb') as f:
            video_bytes = f.read()
        
        # Read the index prompt
        INDEX_PROMPT = Path('prompts/index_prompt.txt').read_text(encoding='utf-8')
        
        # Create the content for Gemini
        content = types.Content(
            parts=[
                types.Part(
                    inline_data=types.Blob(data=video_bytes, mime_type='video/mp4')
                ),
                types.Part(text=INDEX_PROMPT)
            ]
        )
        
        # Generate content with Gemini
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model='models/gemini-2.0-flash',
            contents=content
        )
        
        # Ensure the metadata directory exists
        os.makedirs('outputs/metadata', exist_ok=True)
        
        # Clean the response text to ensure it's valid JSON
        response_text = response.text.strip()
        
        # Remove markdown code block markers if present
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Try to parse the JSON
        try:
            # First attempt to parse as is
            json_data = json.loads(response_text)
        except json.JSONDecodeError:
            # If that fails, try to clean up common issues
            # Remove any trailing commas
            response_text = re.sub(r',(\s*[}\]])', r'\1', response_text)
            # Fix any missing quotes around keys
            response_text = re.sub(r'(\w+):', r'"\1":', response_text)
            # Try parsing again
            try:
                json_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                # If still fails, try to extract just the JSON part
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        json_data = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        raise Exception(f"Could not parse JSON response: {str(e)}\nResponse text: {response_text}")
                else:
                    raise Exception(f"Could not find valid JSON in response: {str(e)}\nResponse text: {response_text}")
        
        # Write the response to the metadata file with proper formatting
        with open('outputs/metadata/VIDEO_METADATA.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        return "Video metadata saved to outputs/metadata/VIDEO_METADATA.json"
    except Exception as e:
        raise Exception(f"Failed to analyze video: {str(e)}")


# def analyze_with_gemini(frames_dir: str):
#     # Get all frame files and sort them to ensure correct order
#     frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".jpg")])
    
#     if len(frame_files) < 2:
#         raise ValueError("Need at least 2 frames to analyze changes")
    
#     all_analyses = []
#     with Progress() as progress:
#         task = progress.add_task("[cyan]Analyzing frames with Gemini...", total=len(frame_files))
        
#         # Process all frames together
#         frame_parts = []
#         for i, frame_file in enumerate(frame_files):
#             frame_path = os.path.join(frames_dir, frame_file)
            
#             if i == 0:
#                 # Upload first frame
#                 uploaded_file = gemini_client.files.upload(file=frame_path)
#                 frame_parts.append(uploaded_file)
#             else:
#                 # Prepare subsequent frames as inline data
#                 with open(frame_path, 'rb') as f:
#                     img_bytes = f.read()
#                 frame_parts.append(types.Part.from_bytes(
#                     data=img_bytes,
#                     mime_type='image/jpg'
#                 ))
            
#             progress.update(task, advance=1)
        
#         # Create the prompt with text and all images
#         response = gemini_client.models.generate_content(
#             model="gemini-2.0-flash",
#             contents=[
#                 "Analyze the following sequence of images and provide a detailed description of the changes and progression throughout the sequence. Pay attention to both subtle and significant changes between frames.",
#                 *frame_parts
#             ]
#         )
        
#         all_analyses.append({
#             "frames": " -> ".join(frame_files),
#             "analysis": response.text
#         })
    
#     # Write analysis to file
#     with open(os.path.join(frames_dir, "gemini_analysis.txt"), "w") as f:
#         f.write(f"Analysis of complete sequence ({len(frame_files)} frames):\n")
#         f.write(all_analyses[0]['analysis'])
        
#     return all_analyses

if __name__ == "__main__":
    async def main():
        try:
            # Get video path from user
            video_path = input("Enter the path to the video: ")
            
            # First compress the video
            print("[cyan]Compressing video...[/cyan]")
            compressed_video_path = await compress_video(video_path)
            print(f"[green]Video compressed successfully to: {compressed_video_path}[/green]")
            
            # Then analyze the compressed video
            print("[cyan]Analyzing video...[/cyan]")
            analysis = await analyze_video(video_path)
            
            # Print the analysis results
            print("\n[bold]Video Analysis Results:[/bold]")
            print(analysis)
            
        except Exception as e:
            print(f"[red]Error: {str(e)}[/red]")
            print("Please make sure:")
            print("1. The video path is correct")
            print("2. The video file exists")
            print("3. You have write permissions in the outputs directory")
            print("4. FFmpeg is installed and available in your system PATH")

    asyncio.run(main())




# if __name__ == "__main__":
#     video_path = input("Enter the path to the video: ")
#     frames_dir = extract_frames(video_path, "outputs/frames")
#     if frames_dir:
#         print(f"[green]Frames extracted successfully to: {frames_dir}[/green]")
#         results = analyze_with_gemini(frames_dir)
#         print('done')



# if __name__ == "__main__":
#     # Example usage
#     video_path = "C:/Users/amaan/OneDrive/Documents/coding/Reduct/reduct-cli/broll_sample.mp4"
#     frames_dir = extract_frames(video_path, "outputs/frames")
    
#     if frames_dir:
#         print(f"[green]Frames extracted successfully to: {frames_dir}[/green]")
#         results = analyze_with_gemini(frames_dir)
        
#         if results:
#             print("\n[bold]Analysis Results:[/bold]")
#             for analysis in results:
#                 print(f"\nFrames: {analysis['frames']}")
#                 print(f"Analysis: {analysis['analysis']}")

