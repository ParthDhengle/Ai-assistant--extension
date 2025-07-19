import tkinter as tk
from threading import Thread
from config import MODEL_PATH
from utils import audio, speech, llm_parser, os_actions
from transformers import pipeline
import torch

asr = pipeline(
    "automatic-speech-recognition",
    model=MODEL_PATH,
    device=0 if torch.cuda.is_available() else -1,
)

def transcribe_audio(path):
    print("🧠 Transcribing...")
    result = asr(path)
    print("📜 Transcript:", result["text"])
    return result["text"]

def handle_voice():
    audio_path = audio.record_audio()
    user_text = transcribe_audio(audio_path)
    output_text.set(f"🧑 You: {user_text}")

    parsed = llm_parser.generate_response(user_text)

    if parsed["type"] == "assistant":
        output_text.set(f"🤖 Spark: {parsed['message']}")
        speech.speak(parsed['message'])

    elif parsed["type"] == "os":
        speech.speak(parsed["message"])
        action = parsed["action"]
        if action == "copy_file":
            result = os_actions.perform_os_action(action, parsed.get("source"), parsed.get("destination"))
        else:
            result = os_actions.perform_os_action(action, parsed.get("target"))
        output_text.set(f"🖥️ {result}")
        speech.speak(result)

    elif parsed["type"] == "code":
        speech.speak(parsed["message"])
        try:
            with open(parsed["target"], "w") as f:
                f.write(parsed["code"])
            output_text.set(f"🖥️ Code written to {parsed['target']}")
        except Exception as e:
            output_text.set(f"❌ Failed to write code: {e}")
            speech.speak("Failed to write the code.")

# GUI Setup
app = tk.Tk()
app.title("Voice Assistant - Spark")
app.geometry("550x300")
app.configure(bg="#1e1e1e")

output_text = tk.StringVar()
output_text.set("Press 🎙️ to speak...")

label = tk.Label(app, textvariable=output_text, fg="white", bg="#1e1e1e",
                 font=("Helvetica", 14), wraplength=480, justify="center")
label.pack(pady=60)

def start_recording():
    Thread(target=handle_voice).start()

record_button = tk.Button(app, text="🎙️ Speak", font=("Helvetica", 16),
                          command=start_recording, bg="#4CAF50", fg="white", padx=20, pady=10)
record_button.pack()

app.mainloop()
