import tkinter as tk
from threading import Thread
from config import MODEL_PATH
from utils import audio, speech, llm_parser, os_actions
from transformers import pipeline
import torch
import sys
import os

# Ensure UTF-8 encoding for stdout
if sys.platform.startswith('win'):
    # For Windows, set console to UTF-8
    os.system('chcp 65001 > nul')

asr = pipeline(
    "automatic-speech-recognition",
    model=MODEL_PATH,
    device=0 if torch.cuda.is_available() else -1,
)

def safe_print(message):
    """Safely print messages, handling encoding issues"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe printing
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        print(safe_message)

def transcribe_audio(path):
    safe_print("🧠 Transcribing...")
    result = asr(path)
    transcript = result["text"]
    safe_print(f"📜 Transcript: {transcript}")
    return transcript

def handle_voice():
    try:
        audio_path = audio.record_until_silence()
        user_text = transcribe_audio(audio_path)
        
        # Update GUI safely
        safe_user_text = f"🧑 You: {user_text}"
        output_text.set(safe_user_text)

        # Generate response
        parsed = llm_parser.generate_response(user_text)
        
        if not parsed or not isinstance(parsed, dict):
            safe_print("❌ Invalid response from LLM parser")
            output_text.set("❌ Sorry, I couldn't process that request.")
            speech.speak("Sorry, I couldn't process that request.")
            return

        response_type = parsed.get("type", "assistant")
        message = parsed.get("message", "No response generated.")

        if response_type == "assistant":
            safe_message = f"🤖 Spark: {message}"
            output_text.set(safe_message)
            speech.speak(message)

        elif response_type == "os":
            speech.speak(message)
            action = parsed.get("action")
            
            if not action:
                output_text.set("❌ No OS action specified")
                speech.speak("No action was specified.")
                return
                
            try:
                if action == "copy_file":
                    result = os_actions.perform_os_action(
                        action, 
                        parsed.get("source"), 
                        parsed.get("destination")
                    )
                else:
                    result = os_actions.perform_os_action(
                        action, 
                        parsed.get("target")
                    )
                
                safe_result = f"🖥️ {result}"
                output_text.set(safe_result)
                speech.speak(result)
                
            except Exception as os_error:
                error_msg = f"OS action failed: {str(os_error)}"
                safe_print(f"❌ {error_msg}")
                output_text.set(f"❌ {error_msg}")
                speech.speak("The OS action failed.")

        elif response_type == "code":
            speech.speak(message)
            target_file = parsed.get("target", "generated_code.py")
            code = parsed.get("code", "")
            
            if not code:
                output_text.set("❌ No code was generated")
                speech.speak("No code was generated.")
                return
                
            try:
                with open(target_file, "w", encoding='utf-8') as f:
                    f.write(code)
                success_msg = f"🖥️ Code written to {target_file}"
                output_text.set(success_msg)
                safe_print(success_msg)
            except Exception as write_error:
                error_msg = f"❌ Failed to write code: {write_error}"
                output_text.set(error_msg)
                speech.speak("Failed to write the code.")
                safe_print(error_msg)
        else:
            # Unknown type, treat as assistant response
            safe_message = f"🤖 Spark: {message}"
            output_text.set(safe_message)
            speech.speak(message)
            
    except Exception as e:
        error_msg = f"❌ An error occurred: {str(e)}"
        safe_print(error_msg)
        output_text.set("❌ An error occurred while processing your request.")
        speech.speak("An error occurred while processing your request.")

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
    # Disable button during recording to prevent multiple simultaneous recordings
    record_button.config(state="disabled")
    output_text.set("🎤 Recording... Please speak clearly.")
    
    def recording_thread():
        try:
            handle_voice()
        finally:
            # Re-enable button
            record_button.config(state="normal")
            
    Thread(target=recording_thread, daemon=True).start()

record_button = tk.Button(app, text="🎙️ Speak", font=("Helvetica", 16),
                          command=start_recording, bg="#4CAF50", fg="white", 
                          padx=20, pady=10)
record_button.pack()

# Add status label
status_label = tk.Label(app, text="Ready", fg="#888", bg="#1e1e1e",
                       font=("Helvetica", 10))
status_label.pack(side="bottom", pady=10)

if __name__ == "__main__":
    safe_print("🚀 Starting Voice Assistant - Spark")
    safe_print("Make sure Ollama is running with phi3:3.8b and codellama:13b models")
    app.mainloop()