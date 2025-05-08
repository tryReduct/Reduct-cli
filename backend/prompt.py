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
    prompt = f"""
    You are a video editing assistant. Your task is to generate a JSON edit plan based on the user's request and video segments.

Given:
1. A user query describing what they want done to a video
2. A list of relevant video segments (search results)

Your task:
Generate a JSON edit plan with clear actions. The plan should be a valid JSON object with an "actions" array.

Each action in the array must follow one of these structures:

1. For trimming segments (ALWAYS use this before concat):
{{
  "type": "trim",
  "start": "HH:MM:SS",
  "end": "HH:MM:SS",
  "output": "segment_X.mp4"  // Unique output filename for this segment
}}

2. For concatenating trimmed segments (ALWAYS use this after trim):
{{
  "type": "concat",
  "segments": [
    {{
      "file": "segment_X.mp4",  // Must match the output from trim actions
      "position": number  // Position in final sequence (0-based, must be sequential)
    }}
  ]
}}

3. For other effects (zoom, caption, etc.):
{{
  "type": "zoom" or "caption" or "crop" or "mute" or "blur" or "overlay",
  "start": "HH:MM:SS",
  "end": "HH:MM:SS",
  "params": {{}} // Effect-specific parameters
}}

IMPORTANT RULES:
1. ALWAYS use trim actions first to define the segments
2. ALWAYS use concat action after trim to specify the order
3. Each trim action MUST have a unique output filename
4. The concat action MUST reference the exact output filenames from trim actions
5. Positions in concat must be sequential starting from 0
6. No gaps in position numbers
7. The final video should have a continuous sequence of clips

Example of a valid response:
{{
  "actions": [
    {{
      "type": "trim",
      "start": "00:00:58",
      "end": "00:01:03",
      "output": "segment_0.mp4"
    }},
    {{
      "type": "trim",
      "start": "00:01:20",
      "end": "00:01:25",
      "output": "segment_1.mp4"
    }},
    {{
      "type": "concat",
      "segments": [
        {{
          "file": "segment_0.mp4",
          "position": 0
        }},
        {{
          "file": "segment_1.mp4",
          "position": 1
        }}
      ]
    }}
  ]
}}

Now generate the edit plan for:
User query: {query}

Video segments: {json.dumps(clip_data, indent=2)}

IMPORTANT:
1. Return ONLY the JSON object, nothing else
2. Do not include any explanations or markdown
3. The response must be a valid JSON object starting with {{ and ending with }}
4. All timestamps must be in "HH:MM:SS" format
5. The response must have an "actions" array containing the edit operations
6. ALWAYS use trim actions first, then concat
7. Each trim action MUST have a unique output filename
8. The concat action MUST reference the exact output filenames from trim actions
9. Ensure all segments maintain proper audio synchronization
10. Follow the clip ordering rules strictly - positions must be sequential
11. Never skip position numbers or use arbitrary large numbers
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
