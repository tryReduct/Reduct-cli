from transcription import extract_audio, transcribe_audio


def main():
    extract_audio("sample.mp4", "test.mp3")
    transcribe_audio("test.mp3")

if __name__ == "__main__":
    main()
