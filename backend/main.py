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
from edit_generator import generate_ffmpeg_from_plan
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
db_client = MongoClient(os.getenv("MONGO_URI"))
db = db_client["videos"]  # Changed database name to "videos"
print(f"Connected to MongoDB database: {db.name}")  # Debug log


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
        self.output_dir = Path("edited/videos")
        self.temp_dir = Path("temp")
        self.clips_dir = self.temp_dir / "clips"
        self.video_metadata: Dict[str, VideoMetadata] = {}
        self.video_id_to_path: Dict[str, str] = {}  # Map video_id to original file path
        self.metadata_collection = db["metadata"]  # MongoDB collection for video metadata
        print(f"Using collection: {self.metadata_collection.name}")  # Debug log

        # Create necessary directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def list_uploaded_videos(self) -> List[Dict]:
        """List all videos that have been uploaded."""
        return list(self.metadata_collection.find({}, {"_id": 0}))

    def check_video_exists(self, video_id: str) -> bool:
        """Check if a video exists in our database."""
        return self.metadata_collection.find_one({"video_id": video_id}) is not None

    def save_video_metadata(self, video_id: str, original_path: str) -> None:
        """Save video metadata to MongoDB."""
        try:
            metadata = {
                "video_id": video_id,
                "original_path": original_path,
                "uploaded_at": datetime.utcnow()
            }
            print(f"\nSaving metadata to MongoDB:")  # Debug log
            print(f"Video ID: {video_id}")
            print(f"Original Path: {original_path}")
            
            result = self.metadata_collection.update_one(
                {"video_id": video_id},
                {"$set": metadata},
                upsert=True
            )
            
            if result.upserted_id:
                print(f"New document created with ID: {result.upserted_id}")
            elif result.modified_count > 0:
                print(f"Existing document updated")
            else:
                print(f"No changes made to document")
                
            # Verify the save
            saved_doc = self.metadata_collection.find_one({"video_id": video_id})
            if saved_doc:
                print("Successfully verified metadata in database")
            else:
                print("Warning: Could not verify metadata in database")
                
        except Exception as e:
            print(f"Error saving metadata to MongoDB: {str(e)}")
            raise

    def get_video_metadata(self, video_id: str) -> Optional[Dict]:
        """Retrieve video metadata from MongoDB."""
        try:
            metadata = self.metadata_collection.find_one({"video_id": video_id})
            if metadata:
                print(f"Found metadata for video ID {video_id}")  # Debug log
            else:
                print(f"No metadata found for video ID {video_id}")  # Debug log
            return metadata
        except Exception as e:
            print(f"Error retrieving metadata from MongoDB: {str(e)}")
            return None

    async def upload_video_async(self, path: str) -> None:
        """Asynchronously upload and index a video."""
        try:
            print(f"\nUploading video: {path}")
            self.video_metadata[path] = VideoMetadata(path=path, task_id=None, status=VideoStatus.UPLOADING)
            task_id = await upload_video(path)
            self.video_metadata[path].task_id = task_id
            self.video_metadata[path].status = VideoStatus.INDEXING
            
            # Wait for indexing to complete
            while True:
                status = await client.task.get(task_id)
                if status.status == "completed":
                    self.video_metadata[path].status = VideoStatus.READY
                    # Store the mapping of video_id to original path
                    self.video_id_to_path[status.video_id] = path
                    # Save metadata to MongoDB
                    print(f"\nVideo indexing completed. Saving metadata...")  # Debug log
                    self.save_video_metadata(status.video_id, path)
                    print(f"Video uploaded successfully. ID: {status.video_id} -> Path: {path}")
                    break
                elif status.status == "failed":
                    self.video_metadata[path].status = VideoStatus.ERROR
                    self.video_metadata[path].error = status.error
                    break
                await asyncio.sleep(5)
        except Exception as e:
            self.video_metadata[path].status = VideoStatus.ERROR
            self.video_metadata[path].error = str(e)
            print(f"Error during upload: {str(e)}")  # Debug log

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

        # Check if all clips are from videos we have in our database
        missing_videos = []
        for clip in clips:
            if not self.check_video_exists(clip['video_id']):
                missing_videos.append(clip['video_id'])

        if missing_videos:
            print("\nWarning: Some videos referenced in the search results have not been uploaded:")
            for video_id in missing_videos:
                print(f"- Video ID: {video_id}")
            print("\nPlease upload these videos first using option 1.")
            return

        print("\nFound clips:")
        for i, clip in enumerate(clips):
            print(f"\nClip {i+1}:")
            print(f"Video ID: {clip['video_id']}")
            print(f"Time range: {clip['start_time']} - {clip['end_time']}")
            print(f"Score: {clip['score']}")
            print(f"Thumbnail URL: {clip['thumbnail_url']}")

        # 4. Generate edit plan using the prompt generator
        print("\nGenerating edit plan...")
        try:
            edit_plan_json = generate_prompt(prompt, clips)
            edit_plan = json.loads(edit_plan_json)
            print("\nGenerated edit plan:")
            print(json.dumps(edit_plan, indent=2))
        except Exception as e:
            print(f"Error generating edit plan: {str(e)}")
            return

        # 5. Ask user if they want to proceed with the edit
        print("\nWould you like to proceed with the edit?")
        print("1. Yes, generate and execute FFmpeg command")
        print("2. No, exit")
        
        choice = input("\nSelect an option (1-2): ").strip()
        
        if choice == "1":
            try:
                # Get the video path from the first clip
                if not clips:
                    print("No clips found to edit.")
                    return
                
                # Try to get the original file path from our mapping or MongoDB
                video_id = clips[0]['video_id']
                print(f"\nLooking up original file for video ID: {video_id}")
                
                # First try in-memory mapping
                if video_id in self.video_id_to_path:
                    input_path = self.video_id_to_path[video_id]
                else:
                    # If not in memory, try MongoDB
                    metadata = self.get_video_metadata(video_id)
                    if metadata:
                        input_path = metadata['original_path']
                        # Update in-memory mapping
                        self.video_id_to_path[video_id] = input_path
                    else:
                        print(f"\nOriginal file not found for video ID: {video_id}")
                        print("Please upload the video first using option 1.")
                        return
                
                print(f"Found original file: {input_path}")
                
                if not os.path.exists(input_path):
                    print(f"Error: Original file not found at {input_path}")
                    return
                
                output_path = str(self.output_dir / f"edited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
                
                print(f"\nGenerating FFmpeg command and executing...")
                print(f"Input: {input_path}")
                print(f"Output: {output_path}")
                
                # Generate and execute FFmpeg command
                final_path = generate_ffmpeg_from_plan(edit_plan, input_path, output_path)
                print(f"\nEdit completed successfully! Output saved to: {final_path}")
                
            except Exception as e:
                print(f"\nError during FFmpeg execution: {str(e)}")
                print("Full error details:", e)
        else:
            print("\nExiting without generating edit.")

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

    def add_existing_video(self, video_id: str, original_path: str) -> None:
        """Manually add metadata for an already uploaded video."""
        try:
            print(f"\nAdding existing video metadata:")
            print(f"Video ID: {video_id}")
            print(f"Original Path: {original_path}")
            
            # Save to MongoDB
            self.save_video_metadata(video_id, original_path)
            
            # Update in-memory mapping
            self.video_id_to_path[video_id] = original_path
            
            print("Successfully added existing video metadata")
        except Exception as e:
            print(f"Error adding existing video: {str(e)}")


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
        print("3. List Uploaded Videos")
        print("4. Add Existing Video Metadata")
        print("5. Exit")

        choice = input("\nSelect an option (1-5): ").strip()

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
            # First check if we have any uploaded videos
            uploaded_videos = editor.list_uploaded_videos()
            if not uploaded_videos:
                print("\nNo videos have been uploaded yet. Please use option 1 to upload videos first.")
                input("\nPress Enter to continue...")
                continue

            prompt = get_edit_prompt()
            if not prompt:
                print("\nNo prompt provided. Press Enter to continue...")
                input()
                continue

            asyncio.run(editor.process_edit(prompt, [], skip_upload=True))

        elif choice == "3":
            # List uploaded videos
            uploaded_videos = editor.list_uploaded_videos()
            if not uploaded_videos:
                print("\nNo videos have been uploaded yet.")
            else:
                print("\nUploaded Videos:")
                for video in uploaded_videos:
                    print(f"\nVideo ID: {video['video_id']}")
                    print(f"Original Path: {video['original_path']}")
                    print(f"Uploaded At: {video['uploaded_at']}")
            input("\nPress Enter to continue...")

        elif choice == "4":
            # Add existing video metadata
            print("\nEnter the video ID from your previous upload:")
            video_id = input("Video ID: ").strip()
            
            print("\nEnter the original file path:")
            original_path = input("Path: ").strip()
            original_path = os.path.abspath(original_path)
            
            if not os.path.exists(original_path):
                print(f"\nWarning: File not found at {original_path}")
                print("Please make sure the path is correct.")
                input("\nPress Enter to continue...")
                continue
                
            editor.add_existing_video(video_id, original_path)
            input("\nPress Enter to continue...")

        elif choice == "5":
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
