import ffmpeg
import uuid
from pathlib import Path
import os

def generate_ffmpeg_from_plan(edit_plan: dict, input_path: str, output_path: str = None):
    if not output_path:
        output_path = f"output_{uuid.uuid4().hex[:8]}.mp4"

    # Create temp directory for segments
    temp_dir = Path("temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Process trim actions first
    segment_files = []
    for action in edit_plan.get("actions", []):
        if action["type"] == "trim":
            start = action.get("start")
            end = action.get("end")
            output = action.get("output")
            
            if start and end and output:
                # Convert timestamps to seconds
                def time_to_seconds(time_str):
                    h, m, s = map(float, time_str.split(':'))
                    return h * 3600 + m * 60 + s

                start_sec = time_to_seconds(start)
                end_sec = time_to_seconds(end)
                
                # Create output path for this segment
                segment_path = temp_dir / output
                
                # Trim the segment with both video and audio
                stream = ffmpeg.input(input_path)
                stream = ffmpeg.trim(stream, start=start_sec, end=end_sec).setpts('PTS-STARTPTS')
                # Use appropriate codecs for filtered output
                stream = ffmpeg.output(stream, str(segment_path), 
                                     acodec='aac',  # Use AAC for audio
                                     vcodec='libx264',  # Use H.264 for video
                                     audio_bitrate='192k')  # Set reasonable audio bitrate
                ffmpeg.run(stream, overwrite_output=True)
                
                segment_files.append(str(segment_path))

    # Process concat action
    for action in edit_plan.get("actions", []):
        if action["type"] == "concat":
            segments = action.get("segments", [])
            if segments:
                # Sort segments by position
                segments.sort(key=lambda x: x["position"])
                
                # Create concat file
                concat_file = temp_dir / "concat_list.txt"
                with open(concat_file, "w") as f:
                    for segment in segments:
                        file_path = temp_dir / segment["file"]
                        if file_path.exists():
                            # Use absolute path in concat file
                            f.write(f"file '{file_path.absolute()}'\n")
                
                # Use concat demuxer to join segments with audio
                stream = ffmpeg.input(str(concat_file), format='concat', safe=0)
                # Use appropriate codecs for final output
                stream = ffmpeg.output(stream, output_path, 
                                     acodec='aac',  # Use AAC for audio
                                     vcodec='libx264',  # Use H.264 for video
                                     audio_bitrate='192k')  # Set reasonable audio bitrate
                ffmpeg.run(stream, overwrite_output=True)
                
                # Clean up concat file
                concat_file.unlink()

    # Clean up segment files
    for file_path in segment_files:
        try:
            Path(file_path).unlink()
        except Exception as e:
            print(f"Warning: Could not delete temporary file {file_path}: {str(e)}")

    return output_path
