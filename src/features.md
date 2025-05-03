#  2 modes 
1. fast af -> fast 
2. max vibes -> longer but better


# new features 

preserving memory with user chats / prompts.


# better indexing

1. Extract frames at regular intervals and run them through a computer vision model to classify content types (person talking vs. app interface)
2. Analyze audio to detect human speech versus silence or other sounds
3. Create timestamped scene descriptions that the LLM can reference


#  implement a Two-Stage Prompt Approach
Rather than having the LLM make direct editing decisions from user input, consider a two-stage process:

1. Have the LLM interpret the user's intent and convert it to a more structured format
2. Then, use that structured format to guide specific editing actions

# fine tuning prompt engineering
1. Include explicit metadata about the video content
2. Add examples of correct interpretations
3. Use a consistent format for describing video segments