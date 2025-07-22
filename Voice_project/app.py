import tkinter as tk
from threading import Thread
from config import MODEL_PATH
from utils import audio, speech, llm_parser, os_actions
from transformers import pipeline
import torch
import sys
import os
import numpy as np

if sys.platform.startswith('win'):
    os.system('chcp 65001 > nul')

try:
    print("🔧 Loading Whisper model...")
    asr = pipeline(
        "automatic-speech-recognition",
        model=MODEL_PATH,
        device=0 if torch.cuda.is_available() else -1,
        return_timestamps=True,
    )
    print("✅ Whisper model loaded successfully")
except Exception as model_error:
    print(f"❌ Error loading Whisper model: {model_error}")
    sys.exit(1)

pending_os_action = None
actions_requiring_confirmation = ["delete_file", "delete_folder", "system_command"]

def safe_print(message):
    try:
        print(message)
    except UnicodeEncodeError:
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        print(safe_message)

def transcribe_audio(path):
    if not path or not os.path.exists(path):
        safe_print(f"❌ Audio file not found: {path}")
        return None
    safe_print("🧠 Transcribing...")
    try:
        file_size = os.path.getsize(path)
        safe_print(f"📁 Audio file size: {file_size} bytes")
        if file_size < 1000:
            safe_print("⚠️ Audio file too small, likely empty")
            return None
        result = asr(path)
        transcript = result.get("text", "") if isinstance(result, dict) else str(result)
        transcript = transcript.strip()
        if not transcript or len(transcript) > 500 and transcript.count('.') / len(transcript) > 0.8 or transcript.lower() in ['', ' ', 'you', 'thank you', '.']:
            safe_print("⚠️ Transcription invalid or empty")
            return None
        safe_print(f"📜 Transcript: {transcript}")
        return transcript
    except Exception as transcribe_error:
        safe_print(f"❌ Transcription error: {transcribe_error}")
        return None
    finally:
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception as cleanup_error:
            safe_print(f"⚠️ Could not clean up temp file: {cleanup_error}")

def get_confirmation_message(parsed_action):
    action = parsed_action.get("action")
    target = parsed_action.get("target")
    source = parsed_action.get("source")
    destination = parsed_action.get("destination")
    if action == "create_file":
        return f"Do you want to create the file '{target}'?"
    elif action == "delete_file":
        return f"Do you want to delete the file '{target}'?"
    elif action == "create_folder":
        return f"Do you want to create the folder '{target}'?"
    elif action == "delete_folder":
        return f"Do you want to delete the folder '{target}'?"
    elif action == "copy_file":
        return f"Do you want to copy '{source}' to '{destination}'?"
    elif action == "move_file":
        return f"Do you want to move '{source}' to '{destination}'?"
    elif action == "system_command":
        command = parsed_action.get("command")
        if command == "shutdown":
            return "Are you sure you want to shut down the computer?"
        elif command == "restart":
            return "Are you sure you want to restart the computer?"
        else:
            return f"Do you want to execute the system command: {command}?"
    else:
        return f"Do you want to perform the action: {action}?"

def execute_os_action(parsed_action):
    global pending_os_action
    try:
        result = os_actions.perform_os_action(parsed_action)
        safe_result = f"🖥️ {result}"
        output_text.set(safe_result)
        speech.speak(result)
    except Exception as os_error:
        error_msg = f"OS action failed: {str(os_error)}"
        safe_print(f"❌ {error_msg}")
        output_text.set(f"❌ {error_msg}")
        speech.speak("The OS action failed.")
    pending_os_action = None

def handle_confirmation_response(user_text):
    global pending_os_action
    user_text_lower = user_text.lower().strip()
    positive_responses = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'go ahead', 'proceed', 'do it']
    negative_responses = ['no', 'nope', 'cancel', 'stop', 'don\'t', 'abort']
    is_positive = any(pos in user_text_lower for pos in positive_responses)
    is_negative = any(neg in user_text_lower for neg in negative_responses)
    if is_positive and not is_negative:
        output_text.set("🖥️ Executing action...")
        app.update()
        execute_os_action(pending_os_action)
        return True
    elif is_negative:
        output_text.set("❌ Action cancelled.")
        speech.speak("Action cancelled. What else can I help you with?")
        pending_os_action = None
        return True
    else:
        output_text.set("🤔 Please say 'yes' to confirm or 'no' to cancel.")
        speech.speak("I didn't understand. Please say yes to confirm or no to cancel.")
        return False

def handle_voice():
    global pending_os_action
    try:
        output_text.set("🎤 Recording... Please speak clearly and wait for silence detection.")
        app.update()
        audio_path = audio.record_until_silence()
        if not audio_path:
            output_text.set("❌ Recording failed. Please check your microphone.")
            speech.speak("Recording failed. Please check your microphone.")
            return
        user_text = transcribe_audio(audio_path)
        if not user_text:
            output_text.set("❌ Could not understand audio. Please speak more clearly.")
            speech.speak("I couldn't understand what you said. Please try speaking more clearly.")
            return
        safe_user_text = f"🧑 You: {user_text}"
        output_text.set(safe_user_text)
        app.update()
        if len(user_text.strip()) < 3:
            output_text.set("❌ Speech too short or unclear.")
            speech.speak("Your speech was too short or unclear. Please try again.")
            return
        if pending_os_action:
            if handle_confirmation_response(user_text):
                return
            else:
                return
        output_text.set("🤖 Processing your request...")
        app.update()
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
            if parsed.get("action") in actions_requiring_confirmation:
                pending_os_action = parsed
                confirmation_message = get_confirmation_message(parsed)
                output_text.set(f"🤔 {confirmation_message}")
                speech.speak(confirmation_message)
                safe_print(f"Awaiting confirmation for: {parsed}")
            else:
                execute_os_action(parsed)
        elif response_type == "code":
            speech.speak(message)
            target_file = parsed.get("target", "generated_code.py")
            code = parsed.get("code", "")
            if not code:
                output_text.set("❌ No code was generated")
                speech.speak("No code was generated.")
                return
            try:
                if not target_file.endswith('.py'):
                    target_file += '.py'
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
    except Exception as e:
        error_msg = f"❌ An error occurred: {str(e)}"
        safe_print(error_msg)
        output_text.set("❌ An error occurred while processing your request.")
        speech.speak("An error occurred while processing your request.")

app = tk.Tk()
app.title("Voice Assistant - Spark")
app.geometry("600x350")
app.configure(bg="#1e1e1e")

output_text = tk.StringVar()
output_text.set("Press 🎙️ to speak...")

label = tk.Label(app, textvariable=output_text, fg="white", bg="#1e1e1e",
                 font=("Helvetica", 12), wraplength=550, justify="center")
label.pack(pady=40)

def start_recording():
    global pending_os_action
    record_button.config(state="disabled", text="🎤 Recording...")
    if pending_os_action:
        status_label.config(text="Waiting for confirmation...")
    else:
        status_label.config(text="Recording in progress...")
    def recording_thread():
        try:
            handle_voice()
        finally:
            record_button.config(state="normal", text="🎙️ Speak")
            if pending_os_action:
                status_label.config(text="Awaiting confirmation")
            else:
                status_label.config(text="Ready")
    Thread(target=recording_thread, daemon=True).start()

record_button = tk.Button(app, text="🎙️ Speak", font=("Helvetica", 16),
                          command=start_recording, bg="#4CAF50", fg="white", 
                          padx=30, pady=15)
record_button.pack(pady=20)

def cancel_pending_action():
    global pending_os_action
    if pending_os_action:
        pending_os_action = None
        output_text.set("❌ Pending action cancelled.")
        speech.speak("Pending action cancelled. What else can I help you with?")
        status_label.config(text="Ready")

cancel_button = tk.Button(app, text="❌ Cancel", font=("Helvetica", 12),
                         command=cancel_pending_action, bg="#f44336", fg="white",
                         padx=15, pady=8)
cancel_button.pack(pady=5)

def test_microphone():
    status_label.config(text="Testing microphone...")
    def test_thread():
        try:
            import sounddevice as sd
            print("📋 Available audio devices:")
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    print(f"  Input Device {i}: {device['name']}")
            print("🎤 Testing microphone for 2 seconds...")
            fs = 16000
            duration = 2.0
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype=np.float32)
            sd.wait()
            level = np.abs(recording).mean()
            print(f"📊 Microphone test - Audio level: {level:.6f}")
            if level < 0.001:
                status_label.config(text="⚠️ Microphone seems quiet or not working")
            else:
                status_label.config(text="✅ Microphone test successful")
        except Exception as test_error:
            print(f"❌ Microphone test failed: {test_error}")
            status_label.config(text="❌ Microphone test failed")
    Thread(target=test_thread, daemon=True).start()

test_button = tk.Button(app, text="🔧 Test Mic", font=("Helvetica", 12),
                       command=test_microphone, bg="#2196F3", fg="white",
                       padx=15, pady=8)
test_button.pack(pady=5)

status_label = tk.Label(app, text="Ready", fg="#888", bg="#1e1e1e",
                       font=("Helvetica", 10))
status_label.pack(side="bottom", pady=10)

instructions_text = "💡 Tips: Speak clearly, wait for silence detection, confirm OS actions with 'yes' or 'no'"
instructions_label = tk.Label(app, text=instructions_text, fg="#666", bg="#1e1e1e",
                            font=("Helvetica", 9), wraplength=550)
instructions_label.pack(side="bottom", pady=5)

if __name__ == "__main__":
    safe_print("🚀 Starting Voice Assistant - Spark")
    safe_print("Make sure Ollama is running with phi3:3.8b and codellama:13b models")
    if torch.cuda.is_available():
        safe_print(f"✅ CUDA available - using GPU: {torch.cuda.get_device_name()}")
    else:
        safe_print("⚠️ CUDA not available - using CPU")
    app.mainloop()