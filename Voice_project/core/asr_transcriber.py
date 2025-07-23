from transformers import pipeline
import torch
import os

class ASRTranscriber:
    def __init__(self, model_path):
        print("🔧 Loading Whisper model...")
        try:
            self.asr = pipeline(
                "automatic-speech-recognition",
                model=model_path,
                device=0 if torch.cuda.is_available() else -1,
                return_timestamps=True,
            )
            print("✅ Whisper model loaded successfully")
        except Exception as model_error:
            print(f"❌ Error loading Whisper model: {model_error}")
            raise

    def transcribe_audio(self, path):
        if not path or not os.path.exists(path):
            print(f"❌ Audio file not found: {path}")
            return None
        print("🧠 Transcribing...")
        try:
            file_size = os.path.getsize(path)
            print(f"📁 Audio file size: {file_size} bytes")
            if file_size < 1000:
                print("⚠️ Audio file too small, likely empty")
                return None
            result = self.asr(path)
            transcript = result.get("text", "") if isinstance(result, dict) else str(result)
            transcript = transcript.strip()
            if not transcript or len(transcript) > 500 and transcript.count('.') / len(transcript) > 0.8 or transcript.lower() in ['', ' ', 'you', 'thank you', '.']:
                print("⚠️ Transcription invalid or empty")
                return None
            print(f"📜 Transcript: {transcript}")
            return transcript
        except Exception as transcribe_error:
            print(f"❌ Transcription error: {transcribe_error}")
            return None
        finally:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception as cleanup_error:
                print(f"⚠️ Could not clean up temp file: {cleanup_error}")

def transcribe_audio(path):
    transcriber = ASRTranscriber(model_path=r"C:\Users\Parth Dhengle\Desktop\Projects\Gen Ai\Ai-extension\Voice_project\models\models--openai--whisper-medium")
    return transcriber.transcribe_audio(path)