import os
import json
import argparse
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import subprocess
from pymongo import MongoClient
from pathlib import Path
import shutil
import sys
import asyncio
from dataclasses import dataclass
from enum import Enum

from twelve import upload_video, client, INDEX_ID, search_video
from process_results import ClipProcessor
from prompt import generate_prompt
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
db_client = MongoClient(os.getenv("MONGO_URI"))
db = db_client["Reduct"]


class VideoStatus(Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


@dataclass
class VideoMetadata:
    path: str
    task_id: Optional[str]
    status: VideoStatus
    error: Optional[str] = None


class VideoEditor:
    def __init__(self):
        self.processor = ClipProcessor()
        self.output_dir = Path("src/edited/videos")
        self.temp_dir = Path("src/temp")
        self.clips_dir = self.temp_dir / "clips"
        self.video_metadata: Dict[str, VideoMetadata] = {}

        # Create necessary directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    async def upload_video_async(self, path: str) -> None:
        """Asynchronously upload and index a video."""
        try:
            self.video_metadata[path] = VideoMetadata(
                path=path, task_id=None, status=VideoStatus.UPLOADING
            )
            task_id = await upload_video(path)
            self.video_metadata[path].task_id = task_id
            self.video_metadata[path].status = VideoStatus.INDEXING

            # Wait for indexing to complete
            while True:
                status = await client.task.get(task_id)
                if status.status == "completed":
                    self.video_metadata[path].status = VideoStatus.READY
                    break
                elif status.status == "failed":
                    self.video_metadata[path].status = VideoStatus.ERROR
                    self.video_metadata[path].error = status.error
                    break
                await asyncio.sleep(5)
        except Exception as e:
            self.video_metadata[path].status = VideoStatus.ERROR
            self.video_metadata[path].error = str(e)

    def analyze_prompt(self, prompt: str) -> Dict:
        """First Gemini call to analyze prompt and extract structured information."""
        analysis_prompt = f"""
        You are an AI assistant that helps understand video editing requests.
        The user wants to edit videos. Their request is: "{prompt}"
        Based on this request, identify the core concepts, objects, actions, spoken phrases, or text-on-screen the user is looking for.
        Formulate a concise and effective search query (or multiple queries if necessary) that can be used with a semantic video search API (like Twelvelabs) to find relevant segments in the indexed videos.
        Also, identify any specific editing actions requested (e.g., cut, join, add text, speed up).
        Output: A JSON object with 'search_queries': ["query1", "query2"], 'editing_actions': ["action1", "action2"], 'target_videos': ["video1.mp4" or "all_indexed_videos"]
        """

        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[analysis_prompt],
        )
        try:
            return json.loads(response.text)
        except:
            # Fallback to simple extraction if JSON parsing fails
            return {
                "search_queries": [prompt],
                "editing_actions": ["cut"],
                "target_videos": ["all_indexed_videos"],
            }

    async def process_edit(
        self, prompt: str, video_paths: List[str], skip_upload: bool = False
    ):
        """Main function to process the video edit request."""
        if not skip_upload:
            # 1. Upload videos asynchronously
            print("Uploading videos...")
            upload_tasks = [self.upload_video_async(path) for path in video_paths]
            await asyncio.gather(*upload_tasks)

            # Check for any upload errors
            for path, metadata in self.video_metadata.items():
                if metadata.status == VideoStatus.ERROR:
                    print(f"Error uploading {path}: {metadata.error}")

        # 2. Analyze prompt
        print("\nAnalyzing prompt...")
        analysis = self.analyze_prompt(prompt)
        print(f"Search queries: {analysis['search_queries']}")
        print(f"Editing actions: {analysis['editing_actions']}")
        print(f"Target videos: {analysis['target_videos']}")

        # 3. Search for clips using Twelvelabs
        print("\nSearching for relevant clips...")
        clips = []
        for query in analysis["search_queries"]:
            # Run search_video in a thread pool since it's synchronous
            search_results = await asyncio.to_thread(search_video, query)
            clips.extend(search_results)

        if not clips:
            print("No relevant clips found.")
            return

        print("\nFound clips:")
        for i, clip in enumerate(clips):
            print(f"\nClip {i+1}:")
            print(f"Video ID: {clip['video_id']}")
            print(f"Time range: {clip['start_time']} - {clip['end_time']}")
            print(f"Score: {clip['score']}")
            print(f"Thumbnail URL: {clip['thumbnail_url']}")

            # Save clip to MongoDB
            collection = db["metadata"]
            collection.insert_one(
                {
                    "video_id": clip["video_id"],
                    "start_time": clip["start_time"],
                    "end_time": clip["end_time"],
                    "score": clip["score"],
                    "thumbnail_url": clip["thumbnail_url"],
                }
            )

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


def clear_screen():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    """Print the application header."""
    print("\n" + "=" * 50)
    print("Reduct AI Video Editor CLI Tool".center(50))
    print("=" * 50 + "\n")


def get_video_paths() -> List[str]:
    """Get video paths from user input."""
    paths = []
    print("\nEnter video paths (one per line). Press Enter twice when done:")
    print("Note: You can paste paths with spaces, no need for quotes")
    while True:
        path = input("> ").strip()
        if not path:
            break
        # Remove any surrounding quotes if present
        path = path.strip("\"'")
        # Convert to absolute path
        path = os.path.abspath(path)
        if os.path.exists(path):
            paths.append(path)
        else:
            print(f"Warning: File not found: {path}")
            print("Please check if the path is correct and try again.")
    return paths


def get_edit_prompt() -> str:
    """Get the editing prompt from user input."""
    print("\nEnter your editing prompt:")
    return input("> ").strip()


def main_menu():
    """Display the main menu and handle user interaction."""
    editor = VideoEditor()

    while True:
        clear_screen()
        print_header()
        print("1. Upload and Edit Videos")
        print("2. Edit Existing Videos")
        print("3. Exit")

        choice = input("\nSelect an option (1-3): ").strip()

        if choice == "1":
            # Upload and edit flow
            video_paths = get_video_paths()
            if not video_paths:
                print("\nNo videos selected. Press Enter to continue...")
                input()
                continue

            prompt = get_edit_prompt()
            if not prompt:
                print("\nNo prompt provided. Press Enter to continue...")
                input()
                continue

            asyncio.run(editor.process_edit(prompt, video_paths, skip_upload=False))

        elif choice == "2":
            # Edit existing videos flow
            prompt = get_edit_prompt()
            if not prompt:
                print("\nNo prompt provided. Press Enter to continue...")
                input()
                continue

            asyncio.run(editor.process_edit(prompt, [], skip_upload=True))

        elif choice == "3":
            print("\nGoodbye!")
            sys.exit(0)

        else:
            print("\nInvalid option. Press Enter to continue...")
            input()
            continue

        print("\nPress Enter to continue...")
        input()


if __name__ == "__main__":
    main_menu()
