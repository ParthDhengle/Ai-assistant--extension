import sounddevice as sd
import numpy as np
import tempfile
import scipy.io.wavfile

def record_audio(duration=5, fs=16000):
    print("🎤 Recording...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    print("✅ Recording finished.")
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    scipy.io.wavfile.write(temp_file.name, fs, audio)
    return temp_file.name
