from google import genai 
import os 
from dotenv import load_dotenv
from typing import List, Dict
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)



def generate_prompt(query: str, clip_data: List[Dict]) -> str:
    prompt = f"""
    You are a helpful assistant that generates a prompt for a video editing tool that uses LLMs to create an ffmpeg commnd that is then ran to edit a video.
    The user has provided a query and a list of clips.
    Your task is to generate a prompt that will be used to edit the video.
    The prompt should be a valid ffmpeg command that can be run to edit the video.
    The prompt should be in the format of a ffmpeg command.

    Query: {query}
    Clip Data: {clip_data}
    """
    
    response = gemini_client.models.generate_content(
        model = "gemini-2.0-flash",
        prompt = prompt,
    )
    return response.text
    
    
