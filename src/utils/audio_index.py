import os 
import json
import asyncio
import subprocess
from google import genai 
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

async def index_audio(audio_path: str):
    """
    Index the audio file and save the results to a JSON file.

    Args:
        audio_path (str): The path to the audio file.
    """
    try:
        # Create the output directory if it doesn't exist
        os.makedirs("src/outputs/audio", exist_ok=True)

        # Get the base name of the audio file
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
    
        # Define the output file path
        output_file = os.path.join('src', "outputs/audio", f"{base_name}_audio_index.json")

        # Read the audio file
        with open(audio_path, "rb") as audio_file:
            audio_data = audio_file.read()

        # Use Gemini to index the audio
        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                'Generate a transcript of the following audio file with timestamps. Also differentiate if there are multiple speakers and return the results in a JSON format',
                types.Part.from_bytes(
                data=audio_data,
                mime_type='audio/mp3',
                )
            ]
            )
        
        # Clean the response text
        response_text = response.text
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse the JSON string into a Python object
        json_data = json.loads(response_text)
        
        # Save the JSON data properly
        with open(output_file, "w") as f:
            json.dump(json_data, f, indent=2)

        print(f"Audio indexed successfully and saved to: {output_file}")

    except Exception as e:  
        raise Exception(f"Failed to index audio: {str(e)}")

async def main():
    audio_path = input("Enter the audio path: ")
    await index_audio(audio_path)

if __name__ == "__main__":
    asyncio.run(main())





