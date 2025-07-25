import tkinter as tk
from tkinter import scrolledtext, ttk
from threading import Thread
from config import MODEL_PATH
from core.asr_transcriber import transcribe_audio
from core.nlp_parser import generate_response
from memory.memory_manager import MemoryManager
from core.task_executor import execute_os_action
from utils.audio_utils import record_until_silence
from utils.speech import speak
from utils.text_utils import estimate_tokens
import torch
import sys
import os
import numpy as np
if sys.platform.startswith('win'):
    os.system('chcp 65001 > nul')

# Initialize memory manager
memory_manager = MemoryManager()

pending_os_action = None
actions_requiring_confirmation = ["delete_file", "delete_folder", "system_command"]
is_text_input = False  # Track input mode

def safe_print(message):
    try:
        print(message)
    except UnicodeEncodeError:
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        print(safe_message)

def add_to_conversation(sender, message, message_type="normal"):
    """Add message to conversation display"""
    conversation_display.config(state=tk.NORMAL)
    
    # Color coding based on sender and type
    if sender == "You":
        conversation_display.insert(tk.END, f"🧑 {sender}: ", "user")
    elif sender == "Spark":
        if message_type == "confirmation":
            conversation_display.insert(tk.END, f"🤔 {sender}: ", "confirmation")
        elif message_type == "action":
            conversation_display.insert(tk.END, f"🖥️ {sender}: ", "action")
        elif message_type == "error":
            conversation_display.insert(tk.END, f"❌ {sender}: ", "error")
        else:
            conversation_display.insert(tk.END, f"🤖 {sender}: ", "assistant")
    else:
        conversation_display.insert(tk.END, f"{sender}: ", "system")
    
    conversation_display.insert(tk.END, f"{message}\n\n", "message")
    conversation_display.config(state=tk.DISABLED)
    conversation_display.see(tk.END)

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

def handle_confirmation_response(user_text):
    global pending_os_action
    user_text_lower = user_text.lower().strip()
    positive_responses = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'go ahead', 'proceed', 'do it']
    negative_responses = ['no', 'nope', 'cancel', 'stop', 'don\'t', 'abort']
    is_positive = any(pos in user_text_lower for pos in positive_responses)
    is_negative = any(neg in user_text_lower for neg in negative_responses)
    
    if is_positive and not is_negative:
        add_to_conversation("Spark", "Executing action...", "action")
        result = execute_os_action(pending_os_action)
        add_to_conversation("Spark", result, "action")
        memory_manager.add_message(user_text, "Action executed.")
        pending_os_action = None
        return True
    elif is_negative:
        add_to_conversation("Spark", "Action cancelled.", "normal")
        if not is_text_input:
            speak("Action cancelled. What else can I help you with?")
        memory_manager.add_message(user_text, "Action cancelled.")
        pending_os_action = None
        return True
    else:
        add_to_conversation("Spark", "Please say 'yes' to confirm or 'no' to cancel.", "confirmation")
        if not is_text_input:
            speak("I didn't understand. Please say yes to confirm or no to cancel.")
        return False

def process_user_input(user_text, input_mode="voice"):
    global pending_os_action, is_text_input
    is_text_input = (input_mode == "text")
    
    try:
        # Add user message to conversation
        add_to_conversation("You", user_text)
        
        if len(user_text.strip()) < 3:
            add_to_conversation("Spark", "Your input was too short or unclear. Please try again.", "error")
            if not is_text_input:
                speak("Your speech was too short or unclear. Please try again.")
            return
        
        if pending_os_action:
            if handle_confirmation_response(user_text):
                return
            else:
                return
        
        # Update status
        status_label.config(text="Processing...")
        app.update()
        
        parsed = generate_response(user_text, memory_manager)
        if not parsed or not isinstance(parsed, dict):
            safe_print("❌ Invalid response from LLM parser")
            safe_print(f"Raw response: {parsed}")
            add_to_conversation("Spark", "Sorry, I couldn't process that request.", "error")
            if not is_text_input:
                speak("Sorry, I couldn't process that request.")
            return
        
        response_type = parsed.get("type", "assistant")
        message = parsed.get("message", "No response generated.")
        
        if response_type == "assistant":
            add_to_conversation("Spark", message)
            if not is_text_input:
                speak(message)
            memory_manager.add_message(user_text, message)
        
        elif response_type == "os":
            if parsed.get("action") in actions_requiring_confirmation:
                pending_os_action = parsed
                confirmation_message = get_confirmation_message(parsed)
                add_to_conversation("Spark", confirmation_message, "confirmation")
                if not is_text_input:
                    speak(confirmation_message)
                safe_print(f"Awaiting confirmation for: {parsed}")
            else:
                result = execute_os_action(parsed)
                add_to_conversation("Spark", result, "action")
                memory_manager.add_message(user_text, f"Executed {parsed['action']}")
        
        elif response_type == "sequence":
            # Speak the overall sequence message
            overall_message = parsed.get("message", "Performing sequence of actions.")
            add_to_conversation("Spark", overall_message, "action")
            if not is_text_input:
                speak(overall_message)
            
            # Execute each action in the sequence
            for action in parsed["actions"]:
                action_message = action.get("message", "Performing action.")
                add_to_conversation("Spark", action_message, "action")
                if not is_text_input:
                    speak(action_message)
                result = execute_os_action(action)
                add_to_conversation("Spark", result, "action")
                # Check for failure
                if result.lower().startswith(("error", "failed")):
                    if not is_text_input:
                        speak(result)
                    break  # Stop sequence on failure
                else:
                    if not is_text_input:
                        speak(result)
        
        elif response_type == "code":
            add_to_conversation("Spark", message, "action")
            if not is_text_input:
                speak(message)
            target_file = parsed.get("target", "generated_code.py")
            code = parsed.get("code", "")
            if not code:
                add_to_conversation("Spark", "No code was generated", "error")
                if not is_text_input:
                    speak("No code was generated.")
                return
            try:
                if not target_file.endswith('.py'):
                    target_file += '.py'
                with open(target_file, "w", encoding='utf-8') as f:
                    f.write(code)
                success_msg = f"Code written to {target_file}"
                add_to_conversation("Spark", success_msg, "action")
                safe_print(success_msg)
                memory_manager.add_message(user_text, success_msg)
            except Exception as write_error:
                error_msg = f"Failed to write code: {write_error}"
                add_to_conversation("Spark", error_msg, "error")
                if not is_text_input:
                    speak("Failed to write the code.")
                safe_print(error_msg)
    
    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        safe_print(error_msg)
        add_to_conversation("Spark", "An error occurred while processing your request.", "error")
        if not is_text_input:
            speak("An error occurred while processing your request.")
    finally:
        status_label.config(text="Ready" if not pending_os_action else "Awaiting confirmation")

def handle_voice():
    try:
        status_label.config(text="Recording...")
        app.update()
        audio_path = record_until_silence()
        if not audio_path:
            add_to_conversation("System", "Recording failed. Please check your microphone.", "error")
            speak("Recording failed. Please check your microphone.")
            return
        
        user_text = transcribe_audio(audio_path)
        if not user_text:
            add_to_conversation("System", "Could not understand audio. Please speak more clearly.", "error")
            speak("I couldn't understand what you said. Please try speaking more clearly.")
            return
        
        process_user_input(user_text, "voice")
        
    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        safe_print(error_msg)
        add_to_conversation("System", "An error occurred while processing your voice input.", "error")
        speak("An error occurred while processing your voice input.")
    finally:
        record_button.config(state="normal", text="🎙️ Voice Input")
        status_label.config(text="Ready" if not pending_os_action else "Awaiting confirmation")

def handle_text_input(event=None):
    user_text = text_input.get().strip()
    if not user_text:
        return
    
    text_input.delete(0, tk.END)
    process_user_input(user_text, "text")

def start_recording():
    global pending_os_action
    record_button.config(state="disabled", text="🎤 Recording...")
    if pending_os_action:
        status_label.config(text="Waiting for confirmation...")
    else:
        status_label.config(text="Recording in progress...")
    
    def recording_thread():
        handle_voice()
    
    Thread(target=recording_thread, daemon=True).start()

def cancel_pending_action():
    global pending_os_action
    if pending_os_action:
        pending_os_action = None
        add_to_conversation("System", "Pending action cancelled.", "normal")
        speak("Pending action cancelled. What else can I help you with?")
        status_label.config(text="Ready")

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
                add_to_conversation("System", "Microphone seems quiet or not working", "error")
            else:
                status_label.config(text="✅ Microphone test successful")
                add_to_conversation("System", f"Microphone test successful - Audio level: {level:.6f}", "normal")
        except Exception as test_error:
            print(f"❌ Microphone test failed: {test_error}")
            status_label.config(text="❌ Microphone test failed")
            add_to_conversation("System", f"Microphone test failed: {test_error}", "error")
    Thread(target=test_thread, daemon=True).start()

def clear_conversation():
    conversation_display.config(state=tk.NORMAL)
    conversation_display.delete(1.0, tk.END)
    conversation_display.config(state=tk.DISABLED)

# Create main window
app = tk.Tk()
app.title("Voice Assistant - Spark")
app.geometry("900x700")
app.configure(bg="#1e1e1e")

# Create main frame
main_frame = tk.Frame(app, bg="#1e1e1e")
main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Conversation display frame
conv_frame = tk.Frame(main_frame, bg="#1e1e1e")
conv_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

conv_label = tk.Label(conv_frame, text="Conversation History", fg="white", bg="#1e1e1e",
                     font=("Helvetica", 12, "bold"))
conv_label.pack(anchor="w")

# Scrolled text widget for conversation
conversation_display = scrolledtext.ScrolledText(
    conv_frame, 
    height=20, 
    bg="#2d2d2d", 
    fg="white", 
    font=("Helvetica", 10),
    wrap=tk.WORD,
    state=tk.DISABLED
)
conversation_display.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

# Configure text tags for different message types
conversation_display.tag_config("user", foreground="#4CAF50", font=("Helvetica", 10, "bold"))
conversation_display.tag_config("assistant", foreground="#2196F3", font=("Helvetica", 10, "bold"))
conversation_display.tag_config("confirmation", foreground="#FF9800", font=("Helvetica", 10, "bold"))
conversation_display.tag_config("action", foreground="#9C27B0", font=("Helvetica", 10, "bold"))
conversation_display.tag_config("error", foreground="#f44336", font=("Helvetica", 10, "bold"))
conversation_display.tag_config("system", foreground="#607D8B", font=("Helvetica", 10, "bold"))
conversation_display.tag_config("message", foreground="white")

# Text input frame
input_frame = tk.Frame(main_frame, bg="#1e1e1e")
input_frame.pack(fill=tk.X, pady=(0, 10))

text_input_label = tk.Label(input_frame, text="Text Input:", fg="white", bg="#1e1e1e",
                           font=("Helvetica", 10))
text_input_label.pack(anchor="w")

# Text input with button
text_input_container = tk.Frame(input_frame, bg="#1e1e1e")
text_input_container.pack(fill=tk.X, pady=(5, 0))

text_input = tk.Entry(text_input_container, font=("Helvetica", 11), bg="#2d2d2d", fg="white",
                     insertbackground="white", relief=tk.FLAT, bd=5)
text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
text_input.bind("<Return>", handle_text_input)

send_button = tk.Button(text_input_container, text="Send", font=("Helvetica", 10),
                       command=handle_text_input, bg="#4CAF50", fg="white",
                       padx=20, pady=5)
send_button.pack(side=tk.RIGHT)

# Button frame
button_frame = tk.Frame(main_frame, bg="#1e1e1e")
button_frame.pack(fill=tk.X, pady=(0, 10))

# Voice input button
record_button = tk.Button(button_frame, text="🎙️ Voice Input", font=("Helvetica", 12),
                         command=start_recording, bg="#4CAF50", fg="white", 
                         padx=20, pady=10)
record_button.pack(side=tk.LEFT, padx=(0, 5))

# Cancel button
cancel_button = tk.Button(button_frame, text="❌ Cancel", font=("Helvetica", 10),
                         command=cancel_pending_action, bg="#f44336", fg="white",
                         padx=15, pady=10)
cancel_button.pack(side=tk.LEFT, padx=5)

# Test microphone button
test_button = tk.Button(button_frame, text="🔧 Test Mic", font=("Helvetica", 10),
                       command=test_microphone, bg="#2196F3", fg="white",
                       padx=15, pady=10)
test_button.pack(side=tk.LEFT, padx=5)

# Clear conversation button
clear_button = tk.Button(button_frame, text="🗑️ Clear", font=("Helvetica", 10),
                        command=clear_conversation, bg="#607D8B", fg="white",
                        padx=15, pady=10)
clear_button.pack(side=tk.LEFT, padx=5)

# Status and instructions frame
bottom_frame = tk.Frame(main_frame, bg="#1e1e1e")
bottom_frame.pack(fill=tk.X)

status_label = tk.Label(bottom_frame, text="Ready", fg="#4CAF50", bg="#1e1e1e",
                       font=("Helvetica", 11, "bold"))
status_label.pack(pady=(0, 5))

instructions_text = "💡 Tips: Use text input for silent operation, voice input for hands-free operation. Confirm OS actions with 'yes' or 'no'"
instructions_label = tk.Label(bottom_frame, text=instructions_text, fg="#666", bg="#1e1e1e",
                            font=("Helvetica", 9), wraplength=850)
instructions_label.pack()

# Initialize conversation
add_to_conversation("System", "Voice Assistant - Spark initialized. You can use text input or voice input.", "normal")

if __name__ == "__main__":
    safe_print("🚀 Starting Voice Assistant - Spark")
    safe_print("Make sure Ollama is running with phi3:3.8b and codellama:13b models")
    if torch.cuda.is_available():
        safe_print(f"✅ CUDA available - using GPU: {torch.cuda.get_device_name()}")
    else:
        safe_print("⚠️ CUDA not available - using CPU")
    app.mainloop()