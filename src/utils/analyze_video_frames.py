import json
from google import genai 
from google.genai import types
import asyncio
import subprocess
import os 
from dotenv import load_dotenv
from rich import print

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

async def generate_video_frames_and_analyze(video_path: str) -> str:
    """Generate frames from a video every 5 seconds."""
    try:
        # Create outputs/frames directory if it doesn't exist
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_dir = os.path.join("src", "outputs", "frames", base_name)
        os.makedirs(output_dir, exist_ok=True)
        
        # Check if input file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Input video not found at: {video_path}")  
        
        # Get video duration
        duration_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        duration = float(subprocess.check_output(duration_cmd).decode().strip())
        
        # Calculate number of frames to extract (one every 5 seconds)
        num_frames = int(duration / 5)
        
        # Extract frames
        for i in range(num_frames):
            timestamp = i * 5
            output_path = os.path.join(output_dir, f"frame_{i:04d}.jpg")
            
            command = [
                "ffmpeg",
                "-ss", str(timestamp),  # Seek to timestamp
                "-i", video_path,
                "-vframes", "1",  # Extract only one frame
                "-q:v", "2",  # Quality level
                output_path
            ]
            
            result = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[yellow]Warning: Failed to extract frame at {timestamp}s: {result.stderr}[/yellow]")
            else:
                print(f"[green]Extracted frame at {timestamp}s[/green]")
        
        print(f"[green]Frames extracted successfully to: {output_dir}[/green]")
        return output_dir
    except Exception as e:
        raise Exception(f"Failed to generate video frames: {str(e)}")

async def analyze_with_gemini(frames_dir: str):
    # Get all frame files and sort them to ensure correct order
    frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".jpg")])
    
    if len(frame_files) < 2:
        raise ValueError("Need at least 2 frames to analyze changes")
    
    all_analyses = []
    
    # Process all frames together
    frame_parts = []
    for i, frame_file in enumerate(frame_files):
        frame_path = os.path.join(frames_dir, frame_file)
        
        if i == 0:
            # Upload first frame
            uploaded_file = await asyncio.to_thread(
                gemini_client.files.upload,
                file=frame_path
            )
            frame_parts.append(uploaded_file)
        else:
            # Prepare subsequent frames as inline data
            with open(frame_path, 'rb') as f:
                img_bytes = f.read()
            frame_parts.append(types.Part.from_bytes(
                data=img_bytes,
                mime_type='image/jpg'
            ))
        
    # Create the prompt with text and all images
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                gemini_client.models.generate_content,
                model="gemini-2.0-flash",
                contents=[
                    "Analyze the following sequence of images and provide a detailed description of the changes and progression throughout the sequence. Pay attention to both subtle and significant changes between frames.",
                    *frame_parts
                ]
            ),
            timeout=300  # 5 minutes timeout
        )
    except asyncio.TimeoutError:
        raise Exception("Gemini API request timed out after 5 minutes")
    
    all_analyses.append({
        "frames": " -> ".join(frame_files),
        "analysis": response.text
    })
    
    # Write analysis to file
    with open(os.path.join(frames_dir, "gemini_analysis.txt"), "w") as f:
        f.write(f"Analysis of complete sequence ({len(frame_files)} frames):\n")
        f.write(all_analyses[0]['analysis'])
        
    return all_analyses

async def analyze_video_frames(video_path: str):
    try:
        frames_dir = await generate_video_frames_and_analyze(video_path)
        
        if frames_dir:
            print(f"[green]Frames extracted successfully to: {frames_dir}[/green]")
            results = await analyze_with_gemini(frames_dir)
            with open(os.path.join(frames_dir, "gemini_analysis.json"), "w") as f:
                json.dump(results, f)
            print("[green]Frame analysis completed successfully[/green]")
    except Exception as e:
        raise Exception(f"Failed to analyze video frames: {str(e)}")


