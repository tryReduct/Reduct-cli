from transformers import pipeline
import os
from rich import print
from rich.progress import Progress
import subprocess
from google import genai 
from google.genai import types

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def compress_video(input_path: str) -> str:
    # Create outputs/compressed directory if it doesn't exist
    os.makedirs("outputs/compressed", exist_ok=True)
    
    # Generate output path with _compressed.mp4 suffix
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join("outputs", "compressed", f"{base_name}_compressed.mp4")
    
    """Compress video to reduce size while maintaining reasonable quality and ensure size is under 20MB."""
    
    # First pass: Compress with standard settings
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
    
    # Check file size and recompress if needed
    file_size = os.path.getsize(output_path) / (1024 * 1024)  # Size in MB
    if file_size > 20:
        # If still too large, use more aggressive compression
        command = [
            "ffmpeg",
            "-i",
            input_path,
            "-vf",
            "scale=854:-1",  # Reduce width further
            "-c:v",
            "libx264",
            "-crf",
            "28",  # More aggressive compression
            "-preset",
            "fast",
            "-y",
            output_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to recompress video: {result.stderr}")
        
        # Final size check
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        if file_size > 20:
            raise Exception("Unable to compress video below 20MB while maintaining acceptable quality")
    
    print(f"Compressed video saved to: {output_path} (Size: {file_size:.2f}MB)")
    return output_path


def analyze_video(video_path: str):
    # The video_path is already the compressed video path, so we can use it directly
    video_bytes = open(video_path, 'rb').read()

    response = gemini_client.models.generate_content(
    model='models/gemini-2.0-flash',
    contents=types.Content(
        parts=[
            types.Part(
                inline_data=types.Blob(data=video_bytes, mime_type='video/mp4')
            ),
            types.Part(text='Every time there is a change in the video, please describe it in detail. This would be used as metadata/context to edit the video.')
        ]
        )
    )
    os.makedirs('outputs/metadata', exist_ok=True)
    with open('outputs/metadata/gemini_analysis.txt', 'w') as f:
        f.write(response.text)
    return response.text



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
    try:
        # Get video path from user
        video_path = input("Enter the path to the video: ")
        
        # First compress the video
        print("[cyan]Compressing video...[/cyan]")
        compressed_video_path = compress_video(video_path)
        print(f"[green]Video compressed successfully to: {compressed_video_path}[/green]")
        
        # Then analyze the compressed video
        print("[cyan]Analyzing video...[/cyan]")
        analysis = analyze_video(compressed_video_path)
        
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

