from twelvelabs import TwelveLabs
from glob import glob
from twelvelabs.models.task import Task
import os
from google import genai 
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv  

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

INDEX_ID = os.getenv("INDEX_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = TwelveLabs(api_key=os.getenv("TL_API_KEY"))
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def validate_video_path(video_path):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"The path {video_path} does not exist.")
    if not glob(video_path):
        raise FileNotFoundError(f"No videos found in the path {video_path}.")

def upload_video(video_path):
    video_path = input("Enter the path to the video: ")
    video_path = validate_video_path(video_path)
    video_files = glob(video_path) # Example: "/videos/*.mp4
    for video_file in video_files:
        print(f"Uploading {video_file}")
        task = client.task.create(index_id=INDEX_ID, file=video_file, language="en")
        print(f"Task id={task.id}")
        # (Optional) Monitor the video indexing process
        # Utility function to print the status of a video indexing task
        def on_task_update(task: Task):
                print(f"  Status={task.status}")
        task.wait_for_done(callback=on_task_update)
        if task.status != "ready":
            raise RuntimeError(f"Indexing failed with status {task.status}")
        print(f"Uploaded {video_file}. The unique identifer of your video is {task.video_id}.")
        video_id = task.video_id
    return video_id

def search_video(user_query):
    search_result = client.search.query(
        index_id=INDEX_ID,
        options=["visual", "audio"],
        query_text=user_query,
        group_by="clip",
        operator="or",
        page_limit=5,
        sort_option="score",
    )
    
    print("\nSearch Results:")
    print("-" * 50)
    
    for idx, result in enumerate(search_result.data, 1):
        print(f"\nResult {idx}:")
        print(f"Score: {result.score:.2f}%")
        print(f"Time Range: {result.start:.2f}s - {result.end:.2f}s")
        print(f"Duration: {result.end - result.start:.2f}s")
        print(f"Confidence: {result.confidence}")
        if result.thumbnail_url:
            print(f"Thumbnail: {result.thumbnail_url}")
    
    print("\nSummary:")
    print(f"Total Results: {search_result.pool.total_count}")
    print(f"Total Duration: {search_result.pool.total_duration:.2f}s")
    
    return search_result

if __name__ == "__main__":
    while True:
        print("\nWelcome to Reduct")
        print("1. Upload a video")
        print("2. Search in your video library")
        print("3. Exit")
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "1":
            input_path = input("Enter the path to the video: ")
            upload_video(input_path)
        elif choice == "2":
            user_query = input("Enter your search query: ")
            search_video(user_query)
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")