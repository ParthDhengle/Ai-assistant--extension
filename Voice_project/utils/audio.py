import torch
import numpy as np
import sounddevice as sd
import tempfile
import scipy.io.wavfile
import queue
from scipy.signal import resample

# Load Silero VAD model
model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
(get_speech_timestamps, _, _, _, _) = utils

def record_until_silence(threshold=1.5, fs=16000):
    print("🎙️ Speak now... (auto stops after silence)")
    
    q = queue.Queue()

    def callback(indata, frames, time, status):
        q.put(indata.copy())

    audio_chunks = []
    silence_time = 0.0
    chunk_duration = 0.25  # seconds

    with sd.InputStream(callback=callback, samplerate=fs, channels=1, blocksize=int(fs * chunk_duration)):
        while True:
            chunk = q.get()
            audio_chunks.append(chunk)
            audio_np = np.concatenate(audio_chunks, axis=0).flatten()

            # Run VAD
            timestamps = get_speech_timestamps(audio_np, model, sampling_rate=fs)
            if not timestamps or timestamps[-1]['end'] < len(audio_np) - int(fs * threshold):
                silence_time += chunk_duration
            else:
                silence_time = 0.0

            if silence_time > threshold:
                print("🛑 Silence detected, stopping.")
                break

    # Convert to NumPy and save to WAV
    final_audio = np.concatenate(audio_chunks, axis=0).astype(np.int16)
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    scipy.io.wavfile.write(temp_file.name, fs, final_audio)
    print(f"✅ Audio saved: {temp_file.name}")
    return temp_file.name
