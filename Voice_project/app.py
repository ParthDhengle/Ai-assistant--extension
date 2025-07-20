import tkinter as tk
from threading import Thread
from config import MODEL_PATH
from utils import audio, speech, llm_parser, os_actions
from transformers import pipeline
import torch
import sys
import os
import numpy as np

# Ensure UTF-8 encoding for stdout
if sys.platform.startswith('win'):
    # For Windows, set console to UTF-8
    os.system('chcp 65001 > nul')

# Initialize ASR with better error handling
try:
    print("🔧 Loading Whisper model...")
    asr = pipeline(
        "automatic-speech-recognition",
        model=MODEL_PATH,
        device=0 if torch.cuda.is_available() else -1,
        return_timestamps=True,  # This can help with debugging
    )
    print("✅ Whisper model loaded successfully")
except Exception as model_error:
    print(f"❌ Error loading Whisper model: {model_error}")
    print("Please check the MODEL_PATH in config.py")
    sys.exit(1)

def safe_print(message):
    """Safely print messages, handling encoding issues"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe printing
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        print(safe_message)

def transcribe_audio(path):
    """Transcribe audio with improved error handling and debugging"""
    if not path or not os.path.exists(path):
        safe_print(f"❌ Audio file not found: {path}")
        return None
        
    safe_print("🧠 Transcribing...")
    
    try:
        # Check file size
        file_size = os.path.getsize(path)
        safe_print(f"📁 Audio file size: {file_size} bytes")
        
        if file_size < 1000:  # Less than 1KB is probably empty
            safe_print("⚠️ Audio file too small, likely empty")
            return None
            
        # Transcribe with the pipeline
        result = asr(path)
        
        if isinstance(result, dict):
            transcript = result.get("text", "")
        else:
            transcript = str(result)
            
        # Clean up the transcript
        transcript = transcript.strip()
        
        # Check for common issues
        if not transcript:
            safe_print("⚠️ Empty transcription result")
            return None
        elif len(transcript) > 500 and transcript.count('.') / len(transcript) > 0.8:
            safe_print("⚠️ Transcription appears to be mostly dots - possible audio issue")
            safe_print(f"Transcript preview: {transcript[:100]}...")
            return None
        elif transcript.lower() in ['', ' ', 'you', 'thank you', '.']:
            safe_print("⚠️ Transcription too short or generic")
            return None
            
        safe_print(f"📜 Transcript: {transcript}")
        return transcript
        
    except Exception as transcribe_error:
        safe_print(f"❌ Transcription error: {transcribe_error}")
        return None
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception as cleanup_error:
            safe_print(f"⚠️ Could not clean up temp file: {cleanup_error}")

def handle_voice():
    """Handle voice input with comprehensive error handling"""
    try:
        # Update GUI to show recording status
        output_text.set("🎤 Recording... Please speak clearly and wait for silence detection.")
        app.update()
        
        # Record audio
        audio_path = audio.record_until_silence()
        
        if not audio_path:
            output_text.set("❌ Recording failed. Please check your microphone.")
            speech.speak("Recording failed. Please check your microphone.")
            return
            
        # Transcribe audio
        user_text = transcribe_audio(audio_path)
        
        if not user_text:
            output_text.set("❌ Could not understand audio. Please speak more clearly.")
            speech.speak("I couldn't understand what you said. Please try speaking more clearly.")
            return

        # Update GUI with user input
        safe_user_text = f"🧑 You: {user_text}"
        output_text.set(safe_user_text)
        app.update()

        # Check if the transcription makes sense (basic validation)
        if len(user_text.strip()) < 3:
            output_text.set("❌ Speech too short or unclear.")
            speech.speak("Your speech was too short or unclear. Please try again.")
            return

        # Generate response
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

        # Handle different response types
        if response_type == "assistant":
            safe_message = f"🤖 Spark: {message}"
            output_text.set(safe_message)
            speech.speak(message)

        elif response_type == "os":
            # First speak the message
            speech.speak(message)
            
            action = parsed.get("action")
            
            if not action:
                output_text.set("❌ No OS action specified")
                speech.speak("No action was specified.")
                return
                
            try:
                # Perform OS action based on type
                if action == "copy_file":
                    source = parsed.get("source")
                    destination = parsed.get("destination")
                    if not source or not destination:
                        raise ValueError("Copy operation requires both source and destination")
                    result = os_actions.perform_os_action(action, source, destination)
                elif action in ["move_file"]:
                    source = parsed.get("source") 
                    destination = parsed.get("destination")
                    if not source or not destination:
                        raise ValueError("Move operation requires both source and destination")
                    result = os_actions.perform_os_action(action, source, destination)
                else:
                    target = parsed.get("target")
                    if not target:
                        raise ValueError(f"Action {action} requires a target")
                    result = os_actions.perform_os_action(action, target)
                
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
                # Ensure target file has proper extension
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
app.geometry("600x350")
app.configure(bg="#1e1e1e")

output_text = tk.StringVar()
output_text.set("Press 🎙️ to speak...")

# Main output label
label = tk.Label(app, textvariable=output_text, fg="white", bg="#1e1e1e",
                 font=("Helvetica", 12), wraplength=550, justify="center")
label.pack(pady=40)

def start_recording():
    """Start recording in a separate thread"""
    # Disable button during recording to prevent multiple simultaneous recordings
    record_button.config(state="disabled", text="🎤 Recording...")
    status_label.config(text="Recording in progress...")
    
    def recording_thread():
        try:
            handle_voice()
        finally:
            # Re-enable button
            record_button.config(state="normal", text="🎙️ Speak")
            status_label.config(text="Ready")
            
    Thread(target=recording_thread, daemon=True).start()

# Main record button
record_button = tk.Button(app, text="🎙️ Speak", font=("Helvetica", 16),
                          command=start_recording, bg="#4CAF50", fg="white", 
                          padx=30, pady=15)
record_button.pack(pady=20)

# Add microphone test button
def test_microphone():
    """Test microphone functionality"""
    status_label.config(text="Testing microphone...")
    
    def test_thread():
        try:
            import sounddevice as sd
            
            # List available devices
            print("📋 Available audio devices:")
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    print(f"  Input Device {i}: {device['name']}")
            
            # Test recording for 2 seconds
            print("🎤 Testing microphone for 2 seconds...")
            fs = 16000
            duration = 2.0
            
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype=np.float32)
            sd.wait()
            
            # Check recording level
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

# Add status label
status_label = tk.Label(app, text="Ready", fg="#888", bg="#1e1e1e",
                       font=("Helvetica", 10))
status_label.pack(side="bottom", pady=10)

# Add instructions
instructions_text = "💡 Tips: Speak clearly, wait for silence detection, ensure microphone permissions are granted"
instructions_label = tk.Label(app, text=instructions_text, fg="#666", bg="#1e1e1e",
                            font=("Helvetica", 9), wraplength=550)
instructions_label.pack(side="bottom", pady=5)

if __name__ == "__main__":
    safe_print("🚀 Starting Voice Assistant - Spark")
    safe_print("Make sure Ollama is running with phi3:3.8b and codellama:13b models")
    
    # Check if CUDA is available
    if torch.cuda.is_available():
        safe_print(f"✅ CUDA available - using GPU: {torch.cuda.get_device_name()}")
    else:
        safe_print("⚠️ CUDA not available - using CPU")
        
    app.mainloop()