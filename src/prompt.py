from google import genai
import os
from dotenv import load_dotenv
from typing import List, Dict
import ffmpeg

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def generate_prompt(query: str, clip_data: List[Dict]) -> str:
    original_filename = clip_data[0]['filename']
    prompt = f"""You are an expert AI assistant specializing in video editing automation. Your task is to translate a user's natural language video editing request into executable Python code using the `ffmpeg-python` library.

**Context:**
The user wants to perform video editing operations based on a natural language query and a provided list of video clips.
You MUST generate Python code that uses the `ffmpeg-python` library to construct and (prepare for) execution of the FFmpeg command.

**Input Details:**
1.  **User Query:** A natural language description of the desired video edit.
    ```
    {query}
    ```
2.  **Clip Data:** A JSON-like string representing a list of available video clips. Each clip object will have at least a `filename` and may have `id`, `start_time`, `end_time` (in seconds or HH:MM:SS.mmm format) if it refers to a segment of a larger file, or relevant metadata discovered by a system like Twelvelabs.
    *   If `start_time` and `end_time` are provided for a clip, it means the user is referring to *that specific segment* of the `filename`.
    *   If only `filename` is provided, assume the whole clip is being referred to unless the query specifies a segment.
    *   Assume filenames are relative paths and valid (e.g., 'clip1.mp4', 'temp/segment_A.mp4').
    ```
    {clip_data}
    ```
    Example `clip_data` format:
    `[
      {"id": "clip_001", "filename": "video_A.mp4", "description": "scene with a cat"},
      {"id": "clip_002", "filename": "video_B.mp4", "start_time": 10.5, "end_time": 25.0, "description": "interview segment"},
      {"id": "clip_003", "filename": "video_C.mp4"}
    ]`

**Output Requirements:**
1.  **Generate Python Code:** The output MUST be a single, runnable block of Python code using the `ffmpeg-python` library.
2.  **Imports:** Start with `import ffmpeg`.
3.  **Input Handling:**
    *   The code should reference the clip filenames provided in `clip_data` to create `ffmpeg.input()` streams.
    *   If `start_time` and `end_time` (or duration `t`) are relevant based on the query or `clip_data`, use them in `ffmpeg.input(filename, ss=start, to=end)` or `ffmpeg.input(filename, ss=start, t=duration)`.
4.  **Operations:**
    *   Translate the user's query into `ffmpeg-python` operations (e.g., `trim`, `concat`, `overlay`, `scale`, `drawtext`, `afade`, `acrossfade`, etc.).
    *   **Prioritize stream copying (`.output(..., c='copy')` or `.output(..., **{{'c:v': 'copy', 'c:a': 'copy'}})`)** whenever possible (e.g., simple cuts, concatenating compatible clips) to avoid slow re-encoding. If re-encoding is necessary (e.g., due to filters, format changes, or incompatible streams for concatenation), choose sensible defaults or specify common codecs (e.g., `c:v='libx264'`, `c:a='aac'`).
    *   For concatenating multiple clips, use the `concat` filter if they need re-encoding or have different properties. If they are compatible and can be stream copied, you might generate multiple `ffmpeg.input()` and then use the `concat` filter, or consider if the user's intent implies separate commands for cutting then a concat demuxer (though `ffmpeg-python` handles this via filter generally). Aim for a single `ffmpeg-python` chain if possible.
    *   Make sure `setpts=PTS-STARTPTS` and `asetpts=PTS-STARTPTS` are used after `trim` or `atrim` filters if those segments are to be concatenated or further processed to ensure correct timestamps.
5.  **Output File:**
    *   The final operation should be an `.output()` call.
    *   Name the output file descriptively, e.g., `final_output.mp4`, or `edited_{original_filename}.mp4`. If the query implies an output name, use that.
6.  **Execution (Optional but good practice):**
    *   The generated code can end with `.run()`, or you can indicate where it would be called. Include a basic `try...except ffmpeg.Error as e:` block to show how errors (like `e.stderr`) could be caught.
7.  **No Explanation Outside Code:** Do NOT provide any explanatory text before or after the Python code block. The output should be *only* the Python code.

**Key Considerations for LLM:**
*   If the query implies operations on specific clips from `clip_data` (e.g., "take the first 5 seconds of clip_001 and join it with clip_002"), correctly identify and use those clips and their properties.
*   If the query is very general (e.g., "make a highlight reel"), you might need to make assumptions (e.g., concatenate all provided clips or segments).
*   Pay close attention to the number of input streams and map them correctly in filters like `concat` or `overlay`.
*   For `filter_complex`, ensure stream labels are used correctly (e.g., `[0:v]`, `[1:a]`, `[outv]`, `[outa]`).

**Example Task:**
User Query: "Cut the first 5 seconds from clip_001 and the segment from 10s to 15s from clip_002, then join them together. Add a 'Hello World' text overlay on the combined clip."
Clip Data: `[{"id": "clip_001", "filename": "video_A.mp4"}, {"id": "clip_002", "filename": "video_B.mp4"}]`

--- START OF TASK ---

Based on the User Query and Clip Data provided above, generate the `ffmpeg-python` code.
    """

    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash",
        prompt=prompt,
    )
    return response.text
