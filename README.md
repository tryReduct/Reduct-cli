# Project setup

1. `uv` python library is used throughout for dependency management, make sure you have that installed or run `pip install uv`
2. run the command to install dependencies: 
    - Windows: 
    `cd src; uv sync` OR `cd src; uv pip install -r requirements.txt`
    - macOS & Linux:
    `cd src && uv sync` OR `cd src && uv pip install -r requirements.txt`
3. check if all dependencies are correctly installed
4. make a `.env` file (see `.env.example` for example) and add your Gemini API key. If you are unable to get one contact me vial [mail](mailto:bilwarad@mail.uc.edu) or [discord](https://discord.gg/Brg3Ex2qpK)
5. Install FFmpeg on your system:
    - Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH
    - Linux: `sudo apt-get install ffmpeg`
    - macOS: `brew install ffmpeg`

# Usage

1. Create a `temp` directory in the project root if it doesn't exist
2. Place your video file in the `temp` directory
3. Run the program:
   ```bash
   uv run main.py
   ```
   or 
   ```bash
   python main.py
   ```
4. When prompted, enter the name of your video file (e.g., `my_video.mp4`)
5. The program will index the video by:
   - Generating a scene-by-scene summary with timestamps
   - Extracting and transcribe the audio
   - Saving outputs in the following directories:
     - `outputs/summary/`: Contains video summaries
     - `outputs/transcript/`: Contains audio transcripts
     - `outputs/audio/`: Contains extracted audio files

# Output Format

- **Video Summary**: Each scene is summarized in 3 sentences with timestamps
- **Audio Transcript**: Full transcription of the audio content
- **Audio Files**: MP3 format audio extracted from the video

# Dependencies

- Python 3.x
- FFmpeg
- Google Gemini API
- Various Python packages (see requirements.txt)

# Notes

- The program temporarily compresses videos for processing but uses the original quality for final outputs
- All temporary files are automatically cleaned up after processing
- Make sure your video file is in a supported format (MP4 recommended)

# Support

For any issues or questions, please contact:
- Email: [bilwarad@mail.uc.edu](mailto:bilwarad@mail.uc.edu)
- Discord: [Join our server](https://discord.gg/Brg3Ex2qpK)
