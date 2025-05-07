from google import genai
import os
from dotenv import load_dotenv
from typing import List, Dict
import ffmpeg
import json

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def generate_prompt(query: str, clip_data: List[Dict]) -> str:
    # Define the example JSON structure separately
    example_json = {
        "actions": [
            {
                "type": "trim",
                "start": "00:00:58",
                "end": "00:01:25"
            },
            {
                "type": "zoom",
                "start": "00:01:00",
                "end": "00:01:20",
                "params": {
                    "scale": 1.3
                }
            },
            {
                "type": "caption",
                "start": "00:01:10",
                "end": "00:01:20",
                "params": {
                    "text": "intense moment",
                    "position": "bottom"
                }
            }
        ]
    }

    prompt = f"""
    You are a video editing assistant. Your task is to generate a JSON edit plan based on the user's request and video segments.

Given:
1. A user query describing what they want done to a video
2. A list of relevant video segments (search results)

Your task:
Generate a JSON edit plan with clear actions. The plan should be a valid JSON object with an "actions" array.

Each action in the array must follow this structure:
{{
  "type": "trim" or "caption" or "zoom" or "crop" or "mute" or "blur" or "overlay",
  "start": "HH:MM:SS",
  "end": "HH:MM:SS",
  "params": {{}} // Optional parameters like "text", "scale", "position", etc.
}}

Example of a valid response:
{json.dumps(example_json, indent=2)}

Now generate the edit plan for:
User query: {query}

Video segments: {json.dumps(clip_data, indent=2)}

IMPORTANT:
1. Return ONLY the JSON object, nothing else
2. Do not include any explanations or markdown
3. The response must be a valid JSON object starting with {{ and ending with }}
4. All timestamps must be in "HH:MM:SS" format
5. The response must have an "actions" array containing the edit operations
"""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt],
        )
        
        # Clean up the response text
        response_text = response.text.strip()
        
        # Remove any markdown code block markers if present
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        # Try to parse the response as JSON to validate it
        json.loads(response_text)
        
        return response_text
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON response from model: {str(e)}")
        print("Raw response:", response_text)
        raise
    except Exception as e:
        print(f"Error generating edit plan: {str(e)}")
        raise
