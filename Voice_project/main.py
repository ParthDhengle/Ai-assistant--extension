import sounddevice as sd
import numpy as np
import scipy.io.wavfile
import tempfile
import pyttsx3
import torch
import tkinter as tk
from threading import Thread
from transformers import pipeline
import requests
import json
import re
import os
import shutil
import ast
# ======================= ENVIRONMENT SETUP =======================
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# ======================= ASR SETUP =======================
model_path = r"C:\Users\Parth Dhengle\Desktop\Projects\Gen Ai\Ai-extension\models--openai--whisper-medium"

asr = pipeline(
    "automatic-speech-recognition",
    model=model_path,
    device=0 if torch.cuda.is_available() else -1,
)


# ======================= OS ACTION FUNCTION =======================
def perform_os_action(action, target,extra=None):
    try:
        if action == "create_file":
            with open(target, 'w') as f:
                f.write("")
            return f"Created file: {target}"

        elif action == "delete_file":
            if os.path.isfile(target):
                os.remove(target)
                return f"Deleted file: {target}"
            elif os.path.isdir(target):
                shutil.rmtree(target)
                return f"Deleted folder: {target}"
            else:
                return "Target not found."

        elif action == "copy_file":
            if extra is None:
                return "Missing destination path for copy_file."
            shutil.copy(target, extra)
            return f"Copied from {target} to {extra}"

        elif action == "create_folder":
            os.makedirs(target, exist_ok=True)
            return f"Created folder: {target}"
        
        elif action == "write_code":
            filepath, code = target.split("::", 1)
            with open(filepath, "w") as f:
                f.write(code)
            return f"Code written to {filepath}"


        else:
            return "Unsupported action."

    except Exception as e:
        return f"Error: {str(e)}"
    
def get_contextual_os_info():
    cwd = os.getcwd()
    folders = [f.name for f in os.scandir(cwd) if f.is_dir()]
    files = [f.name for f in os.scandir(cwd) if f.is_file()]
    return cwd, folders, files


def extract_json_from_text(text):
    # Use regex to extract the first {...} JSON-like object
    match = re.search(r"\{[\s\S]*?\}", text)
    if match:
        json_text = match.group(0)

        # Fix unescaped triple quotes in "code" field
        try:
            # Use raw string-safe parsing
            parsed = ast.literal_eval(json_text)
            if isinstance(parsed, dict) and "code" in parsed:
                # Remove extra commas and fix code formatting
                code = parsed["code"]
                if isinstance(code, tuple):
                    code = code[0]  # tuple caused by trailing comma
                parsed["code"] = str(code).strip()
            return parsed
        except Exception as e:
            print(f"[!] AST parse failed: {e}")
    return {"type": "assistant", "message": "Failed to extract JSON from response."}

# ======================= GENERATE RESPONSE =======================
def generate_response(prompt):
    print("🧠 Generating with Ollama...")

    cwd, folders, files = get_contextual_os_info()

    os_context = (
        f"Current working directory is: {cwd}\n"
        f"Folders: {folders}\n"
        f"Files: {files}\n"
        "Use these paths when deciding where to create, delete, or move files."
    )

    system_prompt = (
        "You are Spark, an intent parser.\n"
        "Analyze the user's request and determine the intent: either 'assistant' or 'os'.\n"
        "If the user wants to perform an OS-level task, return a JSON like:\n"
        "{ \"type\": \"os\", \"action\": \"create_file\", \"target\": \"path/to/file.txt\", \"message\": \"Creating the file now.\" }\n\n"
        "If the user asks you to write code to a file, return JSON like:\n"
        "{ \"type\": \"code\", \"target\": \"file.py\", \"code\": \"<insert full Python code here>\", \"message\": \"Writing code to the file.\" }\n\n"


        "Supported actions:\n"
        "- create_file → e.g., 'create a file named notes.txt'\n"
        "- delete_file → e.g., 'delete the file notes.txt'\n"
        "- create_folder → e.g., 'make a folder called projects'\n"
        "- delete_folder → e.g., 'remove the folder named projects'\n"
        "- copy_file → e.g., 'copy report.txt to backup/report.txt' → return { action: 'copy_file', source: '...', destination: '...' }\n\n"
        "- move_file → use format: source::destination (e.g., 'move data.csv to archive/data.csv')\n\n"

        "If it's a general assistant question (like greetings or queries), return JSON like:\n"
        "{ \"type\": \"assistant\", \"message\": \"Short helpful reply here.\" }\n\n"

        "Always respond with **only valid JSON**, no explanations or tags.\n\n"

        +os_context
    )


    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "phi3:3.8b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
    )

    try:
        result = response.json()
        content = result['message']['content']
        print("🔍 Phi3 Output:", content)

        return extract_json_from_text(content)
    except Exception as e:
        return {"type": "assistant", "message": f"Failed to parse response. {e}"}

# ======================= TTS SETUP =======================
def speak(text):
    print("🔊 Speaking:", text)
    engine = pyttsx3.init()
    engine.setProperty('rate', 170)
    engine.say(text)
    engine.runAndWait()
    engine.stop()

# ======================= AUDIO RECORD =======================
def record_audio(duration=5, fs=16000):
    print("🎤 Recording...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    print("✅ Recording finished.")
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    scipy.io.wavfile.write(temp_file.name, fs, audio)
    return temp_file.name

# ======================= TRANSCRIBE =======================
def transcribe_audio(path):
    print("🧠 Transcribing...")
    result = asr(path)
    print("📜 Transcript:", result["text"])
    return result["text"]

# ======================= GUI + Logic =======================
def handle_voice():
    audio_path = record_audio(5)
    user_text = transcribe_audio(audio_path)
    output_text.set(f"🧑 You: {user_text}")

    parsed = generate_response(user_text)
    if parsed.get("type") == "assistant":
        output_text.set(f"🤖 Spark: {parsed['message']}")
        speak(parsed['message'])

    elif parsed.get("type") == "os":
        speak(parsed.get("message", "Proceeding with OS operation."))
        
        action = parsed.get("action")
        
        if action == "copy_file":
            result = perform_os_action(action, parsed.get("source"), parsed.get("destination"))
        else:
            result = perform_os_action(action, parsed.get("target"))
        output_text.set(f"🖥️ System: {result}")
        speak(result)

    elif parsed.get("type") == "code":
        speak(parsed.get("message", "Writing code..."))
        try:
            with open(parsed["target"], "w") as f:
                f.write(parsed["code"])
            output_text.set(f"🖥️ Code written to {parsed['target']}")
            speak(f"Code written to {os.path.basename(parsed['target'])}")
        except Exception as e:
            output_text.set(f"❌ Failed to write code: {e}")
            speak("Something went wrong while writing the code.")

    else:
        output_text.set("❌ Could not understand the request.")
        speak("Sorry, I didn't understand that.")

# ======================= GUI =======================
app = tk.Tk()
app.title("Voice Chat with Spark")
app.geometry("550x300")
app.configure(bg="#1e1e1e")

output_text = tk.StringVar()
output_text.set("Press 🎙️ to speak...")

label = tk.Label(app, textvariable=output_text, fg="white", bg="#1e1e1e", font=("Helvetica", 14), wraplength=480, justify="center")
label.pack(pady=60)

def start_recording():
    Thread(target=handle_voice).start()

record_button = tk.Button(app, text="🎙️ Speak", font=("Helvetica", 16), command=start_recording, bg="#4CAF50", fg="white", padx=20, pady=10)
record_button.pack()

app.mainloop()
