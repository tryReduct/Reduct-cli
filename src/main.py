import os
import json
import argparse
from datetime import datetime
from typing import List, Dict, Tuple
import subprocess
from pathlib import Path
import shutil

from twelve import upload_video, client, INDEX_ID, search_video
from process_results import ClipProcessor
from prompt import generate_prompt
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

class VideoEditor:
    def __init__(self):
        self.processor = ClipProcessor()
        self.output_dir = Path("src/edited/videos")
        self.temp_dir = Path("src/temp")
        self.clips_dir = self.temp_dir / "clips"
        
        # Create necessary directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def _create_clip(self, video_id: str, start_time: float, end_time: float, clip_index: int) -> str:
        """Create a clip from the original video file using FFmpeg."""
        try:
            # Get video info using SDK
            video = client.video.get(video_id)
            if not video or not video.url:
                print(f"Warning: Could not get video info for {video_id}")
                return None

            output_path = self.clips_dir / f"clip_{clip_index}.mp4"
            
            # FFmpeg command to cut the clip
            command = f'ffmpeg -y -ss {start_time} -to {end_time} -i "{video.url}" -c copy "{output_path}"'
            
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Error creating clip: {result.stderr}")
                    return None
                return str(output_path)
            except Exception as e:
                print(f"Error creating clip: {str(e)}")
                return None
        except Exception as e:
            print(f"Error creating clip: {str(e)}")
            return None

    def _create_concat_file(self, clip_paths: List[str]) -> str:
        """Create a file listing clips for FFmpeg concatenation."""
        concat_file = self.temp_dir / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")
        return str(concat_file)

    def analyze_prompt(self, prompt: str) -> Tuple[str, str]:
        """First Gemini call to analyze prompt and extract search terms and edit type."""
        analysis_prompt = f"""
        Analyze the following video editing prompt and extract:
        1. Search terms to find relevant video clips
        2. Type of edit the user wants to perform (e.g., cut, merge, add transition)

        Prompt: {prompt}

        Return the response in JSON format with keys 'search_terms' and 'edit_type'.
        """
        
        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[analysis_prompt],
        )
        try:
            analysis = json.loads(response.text)
            return analysis['search_terms'], analysis['edit_type']
        except:
            # Fallback to simple extraction if JSON parsing fails
            return prompt, "cut"  # Default to cut if analysis fails

    def generate_ffmpeg_command(self, prompt: str, clips: List[Dict], edit_type: str) -> Tuple[str, List[str]]:
        """Generate FFmpeg command using Gemini and create necessary clips."""
        # First, create all the clips
        clip_paths = []
        for i, clip in enumerate(clips):
            clip_path = self._create_clip(
                clip['video_id'],
                clip['start_time'],
                clip['end_time'],
                i
            )
            if clip_path:
                clip_paths.append(clip_path)
        
        if not clip_paths:
            raise ValueError("Failed to create any clips")

        # Create concat file
        concat_file = self._create_concat_file(clip_paths)
        
        # Generate final FFmpeg command
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"edited_{timestamp}.mp4"
        
        # Generate a simple concat command
        command = f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" -c copy "{output_path}"'
        
        return command, clip_paths

    def execute_ffmpeg(self, command: str, output_path: str) -> bool:
        """Execute FFmpeg command with error handling."""
        try:
            # Validate command for safety
            if not command.startswith('ffmpeg'):
                raise ValueError("Invalid FFmpeg command")
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                return False
                
            return True
            
        except Exception as e:
            print(f"Error executing FFmpeg command: {str(e)}")
            return False

    def cleanup(self, clip_paths: List[str]):
        """Clean up temporary files."""
        try:
            # Remove individual clips
            for path in clip_paths:
                if os.path.exists(path):
                    os.remove(path)
            
            # Remove concat file
            concat_file = self.temp_dir / "concat_list.txt"
            if concat_file.exists():
                os.remove(concat_file)
                
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

    def process_edit(self, prompt: str, video_paths: List[str], skip_upload: bool = False):
        """Main function to process the video edit request."""
        clip_paths = []  # Initialize clip_paths at the start
        
        if not skip_upload:
            # 1. Upload videos
            print("Uploading videos...")
            for path in video_paths:
                try:
                    print(f"\nUploading {path}...")
                    upload_video(path)
                except Exception as e:
                    print(f"Error uploading {path}: {str(e)}")
                    continue

        # 2. Analyze prompt
        print("\nAnalyzing prompt...")
        search_terms, edit_type = self.analyze_prompt(prompt)
        print(f"Search terms: {search_terms}")
        print(f"Edit type: {edit_type}")

        # 3. Search for clips
        print("\nSearching for relevant clips...")
        clips = self.processor.get_highest_scored_clips(search_terms)
        if not clips:
            print("No relevant clips found.")
            return

        print("\nFound clips:")
        for i, clip in enumerate(clips):
            print(f"\nClip {i+1}:")
            print(f"Video ID: {clip['video_id']}")
            print(f"Time range: {clip['start_time']} - {clip['end_time']}")
            print(f"Score: {clip['score']}")

        try:
            # 4. Generate FFmpeg command and create clips
            print("\nGenerating FFmpeg command and creating clips...")
            ffmpeg_command, clip_paths = self.generate_ffmpeg_command(prompt, clips, edit_type)
            print(f"Generated command: {ffmpeg_command}")

            # 5. Execute FFmpeg command
            print("\nExecuting FFmpeg command...")
            if self.execute_ffmpeg(ffmpeg_command, str(self.output_dir)):
                print(f"Successfully created edited video")
            else:
                print("Failed to execute FFmpeg command.")
                
        except Exception as e:
            print(f"Error during processing: {str(e)}")
        finally:
            # Clean up temporary files
            if clip_paths:  # Only clean up if we have clip paths
                self.cleanup(clip_paths)

def main():
    parser = argparse.ArgumentParser(description="Video Editor CLI Tool")
    parser.add_argument("--prompt", required=True, help="Natural language prompt for video editing")
    parser.add_argument("--videos", nargs="+", help="Paths to video files to process")
    parser.add_argument("--skip-upload", action="store_true", help="Skip video upload and use already indexed videos")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.skip_upload and not args.videos:
        parser.error("--videos is required when not using --skip-upload")
    
    editor = VideoEditor()
    editor.process_edit(args.prompt, args.videos if args.videos else [], args.skip_upload)

if __name__ == "__main__":
    main()
