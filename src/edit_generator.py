import ffmpeg
import uuid

def generate_ffmpeg_from_plan(edit_plan: dict, input_path: str, output_path: str = None):
    if not output_path:
        output_path = f"output_{uuid.uuid4().hex[:8]}.mp4"

    # Start input stream
    stream = ffmpeg.input(input_path)

    # Get video duration
    probe = ffmpeg.probe(input_path)
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    duration = float(video_info['duration'])

    for action in edit_plan.get("actions", []):
        action_type = action["type"]
        start = action.get("start")
        end = action.get("end")
        params = action.get("params", {})

        if action_type == "trim":
            if start and end:
                # Convert timestamps to seconds
                def time_to_seconds(time_str):
                    h, m, s = map(float, time_str.split(':'))
                    return h * 3600 + m * 60 + s

                start_sec = time_to_seconds(start)
                end_sec = time_to_seconds(end)

                # If we're removing a section, we need to concatenate the remaining parts
                if start_sec > 0 or end_sec < duration:
                    # Create two streams for the parts we want to keep
                    if start_sec > 0:
                        first_part = ffmpeg.input(input_path).trim(start=0, end=start_sec)
                    else:
                        first_part = None

                    if end_sec < duration:
                        second_part = ffmpeg.input(input_path).trim(start=end_sec, end=duration)
                    else:
                        second_part = None

                    # Concatenate the parts with audio
                    if first_part and second_part:
                        # Ensure both parts have audio
                        first_part = first_part.audio
                        second_part = second_part.audio
                        stream = ffmpeg.concat(first_part, second_part, v=1, a=1)
                    elif first_part:
                        stream = first_part.audio
                    elif second_part:
                        stream = second_part.audio
                else:
                    # If we're keeping a section, use the original trim logic
                    stream = ffmpeg.trim(stream, start=start, end=end).setpts('PTS-STARTPTS')
                    stream = stream.audio  # Ensure audio is preserved

        elif action_type == "mute":
            stream = ffmpeg.filter(stream, 'volume', volume=0)

        elif action_type == "crop":
            w = params.get("width")
            h = params.get("height")
            x = params.get("x", 0)
            y = params.get("y", 0)
            if w and h:
                stream = ffmpeg.crop(stream, x, y, w, h)
                stream = stream.audio  # Preserve audio after crop

        elif action_type == "overlay":
            overlay_path = params.get("path")
            x = params.get("x", 0)
            y = params.get("y", 0)
            if overlay_path:
                overlay = ffmpeg.input(overlay_path)
                stream = ffmpeg.overlay(stream, overlay, x=x, y=y)
                stream = stream.audio  # Preserve audio after overlay

        elif action_type == "zoom":
            scale = params.get("scale", 1.0)
            if scale != 1.0:
                # Get video dimensions
                width = int(video_info['width'])
                height = int(video_info['height'])
                
                # Calculate new dimensions
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                # Calculate crop dimensions to maintain aspect ratio
                crop_width = width
                crop_height = height
                
                # Apply zoom effect
                stream = ffmpeg.filter(stream, 'scale', new_width, new_height)
                stream = ffmpeg.filter(stream, 'crop', crop_width, crop_height)
                stream = stream.audio  # Preserve audio after zoom

        elif action_type == "caption":
            text = params.get("text", "")
            position = params.get("position", "bottom")
            
            if text:
                # Create text overlay
                stream = ffmpeg.filter(stream, 'drawtext',
                    text=text,
                    fontsize=24,
                    fontcolor='white',
                    box=1,
                    boxcolor='black@0.5',
                    x='(w-text_w)/2',  # Center horizontally
                    y='h-th-10' if position == "bottom" else '10',  # Position at bottom or top
                    escape_text=1
                )
                stream = stream.audio  # Preserve audio after adding caption

        elif action_type == "blur":
            amount = params.get("amount", 5)
            stream = ffmpeg.filter(stream, 'boxblur', amount)
            stream = stream.audio  # Preserve audio after blur

        else:
            print(f"[Warning] Unknown action type: {action_type}")

    # Output final video with audio
    stream = ffmpeg.output(stream, output_path, acodec='aac', vcodec='libx264')
    ffmpeg.run(stream, overwrite_output=True)

    return output_path
