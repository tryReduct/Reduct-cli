import os
from twelvelabs import TwelveLabs
from glob import glob
from twelvelabs.models.task import Task
from twelvelabs.models.search import SearchData, GroupByVideoSearchData
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

INDEX_ID = os.getenv("INDEX_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = TwelveLabs(api_key=os.getenv("TL_API_KEY"))


def validate_video_path(video_path):
    video_path = video_path.strip()
    video_path = os.path.abspath(video_path)
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"The path {video_path} does not exist.")
    if not glob(video_path):
        raise FileNotFoundError(f"No videos found in the path {video_path}.")
    return video_path

def upload_video(video_path):
    validated_path = validate_video_path(video_path)
    task = client.task.create(index_id=INDEX_ID, file=validated_path)
    print(f"Task id={task.id}")
    # (Optional) Monitor the video indexing process
    # Utility function to print the status of a video indexing task
    def on_task_update(task: Task):
        print(f"  Status={task.status}")

    task.wait_for_done(callback=on_task_update)
    if task.status != "ready":
        raise RuntimeError(f"Indexing failed with status {task.status}")
    print(
        f"Uploaded {validated_path}. The unique identifer of your video is {task.video_id}."
    )
    video_id = task.video_id
    return video_id

def print_search_data(data: SearchData):
    return {
        'score': data.score,
        'start_time': data.start,
        'end_time': data.end,
        'video_id': data.video_id,
        'thumbnail_url': data.thumbnail_url
    }

def search_video(user_query):
    user_query = user_query.strip()
    user_query = user_query.lower()
    result = client.search.query(
        index_id=INDEX_ID,
        options=["visual", "audio"],
        query_text=user_query,
        group_by="clip",
        operator="or",
        page_limit=5,
        sort_option="score",
    )
    
    all_clips = []
    highest_score = 0
    
    # Collect all clips and find highest score
    for item in result.data:
        if isinstance(item, GroupByVideoSearchData):
            if item.clips:
                for clip in item.clips:
                    clip_data = print_search_data(clip)
                    all_clips.append(clip_data)
                    highest_score = max(highest_score, clip_data['score'])
        else:
            clip_data = print_search_data(item)
            all_clips.append(clip_data)
            highest_score = max(highest_score, clip_data['score'])
    
    # Filter clips based on score
    if highest_score > 0.7:  # Consider scores above 0.7 as "high"
        high_scored_clips = [clip for clip in all_clips if clip['score'] >= 0.7]
        if high_scored_clips:
            all_clips = high_scored_clips
    
    # Print results
    for clip in all_clips:
        print(f"\nClip Details:")
        print(f"  Timestamp: {clip['start_time']} - {clip['end_time']}")
        print(f"  Score: {clip['score']}")
        print(f"  Thumbnail URL: {clip['thumbnail_url']}")
        print(f"  Video ID: {clip['video_id']}")
    
    return all_clips

