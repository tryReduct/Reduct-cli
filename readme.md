# Reduct CLI - AI-Powered Video Editing Tool

Reduct CLI is a powerful command-line tool that uses AI to help you edit videos based on natural language prompts. It combines the capabilities of Gemini AI, Twelvelabs video search, and FFmpeg to create an intelligent video editing pipeline.

## Features

- **Natural Language Video Editing**: Describe your desired edits in plain English
- **Semantic Video Search**: Find relevant clips using AI-powered search
- **Intelligent Clip Selection**: Automatically identify and extract the most relevant segments
- **Automated Editing**: Generate and execute FFmpeg commands based on AI analysis
- **MongoDB Integration**: Track video metadata and editing history
- **Asynchronous Processing**: Handle multiple video uploads and processing tasks efficiently

## Prerequisites

- Python 3.8+
- MongoDB
- FFmpeg
- Twelvelabs API key
- Google Gemini API key

## Installation

### Using UV (Recommended)

1. Install UV if you haven't already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Create and activate a virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

### Using pip

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Environment Variables

Create a `.env` file in the project root with the following variables:

```
GEMINI_API_KEY=your_gemini_api_key
MONGO_URI=your_mongodb_connection_string
```

## Project Structure

```
backend/
├── main.py           # Main application logic
├── prompt.py         # AI prompt generation
├── edit_generator.py # FFmpeg command generation
├── process_results.py # Video clip processing
├── twelve.py         # Twelvelabs API integration
├── edited/          # Output directory for edited videos
├── temp/            # Temporary files
└── uploads/         # Uploaded video storage
```

## Usage

1. **Upload Videos**:
   - Place your videos in the `uploads` directory
   - The system will automatically process and index them

2. **Edit Videos**:
   - Use natural language to describe your desired edits
   - Example: "Create a highlight reel of all the action scenes"

3. **Process Edits**:
   - The system will:
     1. Analyze your request using Gemini AI
     2. Search for relevant clips using Twelvelabs
     3. Generate an edit plan
     4. Execute the edits using FFmpeg
     5. Save the final video in the `edited` directory

## Editing Capabilities

The system supports various editing operations:
- Trimming segments
- Concatenating clips
- Adding effects (zoom, captions, crop, mute, blur, overlay)
- Maintaining audio synchronization
- Sequential clip ordering

## Dependencies

- `pymongo`: MongoDB integration
- `google-generativeai`: Gemini AI integration
- `ffmpeg-python`: Video processing
- `python-dotenv`: Environment variable management
- `asyncio`: Asynchronous operations

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
