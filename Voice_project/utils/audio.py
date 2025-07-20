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

def record_until_silence(threshold=2.0, fs=16000, min_recording_time=1.0, max_silence_time=2.0):
    """
    Record audio until silence is detected
    
    Args:
        threshold: Silence threshold in seconds
        fs: Sampling rate (16kHz for Whisper)
        min_recording_time: Minimum recording duration before checking for silence
        max_silence_time: Maximum silence time before stopping
    """
    print("🎙️ Speak now... (auto stops after silence)")
    
    q = queue.Queue()
    recording_started = False
    
    def callback(indata, frames, time, status):
        if status:
            print(f"Audio callback status: {status}")
        # Convert to the right format and add to queue
        audio_data = indata.copy().flatten()
        q.put(audio_data)

    audio_chunks = []
    silence_time = 0.0
    total_time = 0.0
    chunk_duration = 0.1  # Smaller chunks for better responsiveness
    speech_detected = False

    # Get default input device info for debugging
    try:
        device_info = sd.query_devices(kind='input')
        print(f"Using input device: {device_info['name']}")
        print(f"Max input channels: {device_info['max_input_channels']}")
    except Exception as e:
        print(f"Warning: Could not query audio device: {e}")

    try:
        with sd.InputStream(
            callback=callback, 
            samplerate=fs, 
            channels=1, 
            dtype=np.float32,  # Use float32 for better precision
            blocksize=int(fs * chunk_duration)
        ):
            print("🎤 Recording started...")
            
            while True:
                try:
                    # Get audio chunk with timeout
                    chunk = q.get(timeout=1.0)
                    audio_chunks.append(chunk)
                    total_time += chunk_duration
                    
                    # Check audio level to ensure we're getting input
                    audio_level = np.abs(chunk).mean()
                    if audio_level > 0.001:  # Threshold for detecting any audio input
                        if not recording_started:
                            print("🎤 Audio input detected")
                            recording_started = True
                    
                    # Only start VAD analysis after minimum recording time
                    if total_time >= min_recording_time and len(audio_chunks) > 10:
                        # Concatenate all audio so far
                        audio_np = np.concatenate(audio_chunks, axis=0)
                        
                        # Ensure audio is in the right format for VAD (float32, range roughly -1 to 1)
                        if audio_np.dtype != np.float32:
                            audio_np = audio_np.astype(np.float32)
                        
                        # Normalize if needed
                        if np.abs(audio_np).max() > 1.0:
                            audio_np = audio_np / np.abs(audio_np).max()
                        
                        # Run VAD
                        try:
                            timestamps = get_speech_timestamps(
                                audio_np, 
                                model, 
                                sampling_rate=fs,
                                min_speech_duration_ms=100,  # Minimum speech duration
                                min_silence_duration_ms=500  # Minimum silence duration
                            )
                            
                            if timestamps:
                                speech_detected = True
                                last_speech_end = timestamps[-1]['end']
                                current_sample = len(audio_np)
                                
                                # Calculate silence duration in seconds
                                silence_samples = current_sample - last_speech_end
                                current_silence_time = silence_samples / fs
                                
                                if current_silence_time > max_silence_time:
                                    print(f"🛑 Silence detected ({current_silence_time:.1f}s), stopping.")
                                    break
                                else:
                                    silence_time = 0.0  # Reset if speech continues
                            elif speech_detected:
                                # If we had speech before but none now, increment silence time
                                silence_time += chunk_duration
                                if silence_time > max_silence_time:
                                    print("🛑 Silence after speech detected, stopping.")
                                    break
                                    
                        except Exception as vad_error:
                            print(f"VAD error: {vad_error}")
                            # Fallback: stop after a reasonable time without VAD
                            if total_time > 10.0:  # Max 10 seconds
                                print("🛑 Maximum recording time reached.")
                                break
                    
                    # Safety net: maximum recording time
                    if total_time > 30.0:  # 30 second maximum
                        print("🛑 Maximum recording time reached (30s).")
                        break
                        
                except queue.Empty:
                    print("⚠️ Audio queue timeout")
                    break
                    
    except Exception as stream_error:
        print(f"❌ Audio stream error: {stream_error}")
        return None

    if not audio_chunks:
        print("❌ No audio recorded")
        return None

    # Convert to the format expected by Whisper
    final_audio = np.concatenate(audio_chunks, axis=0)
    
    # Ensure we have some audio content
    if len(final_audio) < fs * 0.5:  # Less than 0.5 seconds
        print("⚠️ Recording too short")
        return None
    
    # Check if audio has actual content (not just silence)
    audio_level = np.abs(final_audio).mean()
    if audio_level < 0.001:
        print("⚠️ Audio appears to be silent or very quiet")
        print(f"Audio level: {audio_level}")
        return None
    
    # Convert to int16 for wav file (Whisper expects this format)
    # Ensure proper scaling
    if final_audio.dtype == np.float32:
        # Scale float32 audio to int16 range
        final_audio = np.clip(final_audio, -1.0, 1.0)
        final_audio_int16 = (final_audio * 32767).astype(np.int16)
    else:
        final_audio_int16 = final_audio.astype(np.int16)
    
    # Save to temporary WAV file
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        scipy.io.wavfile.write(temp_file.name, fs, final_audio_int16)
        print(f"✅ Audio saved: {temp_file.name}")
        print(f"📊 Audio stats: {len(final_audio_int16)/fs:.1f}s, level: {audio_level:.4f}")
        return temp_file.name
    except Exception as save_error:
        print(f"❌ Error saving audio file: {save_error}")
        return None