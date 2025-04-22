# Interview-Evaluator

This is an application that performs a conversational interview, and then grades the vocal features and content of that interview, along with a job fit and skills match analysis.

We utilized a OpenAI whisper for text to speech, and powered our analysis and question generation with the Gemini 1.5 Flash LLM. We trained a random forests ML model to analyze voice prosody features trained on a the MIT Interview dataset.

To run this program, you must install the requirements.txt, and set the apikeys for this program by running the set_api_keys.py file. You must have your own google gemini api key and openai whisper api key to successfully run this program. 

After this you can run main.py to run the program, or create a compiled macos application by running: 
pyinstaller InterviewBotPro.spec
