import torch
import numpy as np
import sounddevice as sd
import tempfile
import scipy.io.wavfile
import queue

model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
(get_speech_timestamps, _, _, _, _) = utils

def record_until_silence(threshold=2.0, fs=16000, min_recording_time=1.0, max_silence_time=2.0):
    print("🎙️ Speak now... (auto stops after silence)")
    
    q = queue.Queue()
    recording_started = False
    
    def callback(indata, frames, time, status):
        if status:
            print(f"Audio callback status: {status}")
        audio_data = indata.copy().flatten()
        q.put(audio_data)

    audio_chunks = []
    silence_time = 0.0
    total_time = 0.0
    chunk_duration = 0.1
    speech_detected = False

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
            dtype=np.float32,
            blocksize=int(fs * chunk_duration)
        ):
            print("🎤 Recording started...")
            
            while True:
                try:
                    chunk = q.get(timeout=1.0)
                    audio_chunks.append(chunk)
                    total_time += chunk_duration
                    
                    audio_level = np.abs(chunk).mean()
                    if audio_level > 0.001:
                        if not recording_started:
                            print("🎤 Audio input detected")
                            recording_started = True
                    
                    if total_time >= min_recording_time and len(audio_chunks) > 10:
                        audio_np = np.concatenate(audio_chunks, axis=0)
                        
                        if audio_np.dtype != np.float32:
                            audio_np = audio_np.astype(np.float32)
                        
                        if np.abs(audio_np).max() > 1.0:
                            audio_np = audio_np / np.abs(audio_np).max()
                        
                        try:
                            timestamps = get_speech_timestamps(
                                audio_np, 
                                model, 
                                sampling_rate=fs,
                                min_speech_duration_ms=100,
                                min_silence_duration_ms=500
                            )
                            
                            if timestamps:
                                speech_detected = True
                                last_speech_end = timestamps[-1]['end']
                                current_sample = len(audio_np)
                                silence_samples = current_sample - last_speech_end
                                current_silence_time = silence_samples / fs
                                
                                if current_silence_time > max_silence_time:
                                    print(f"🛑 Silence detected ({current_silence_time:.1f}s), stopping.")
                                    break
                                else:
                                    silence_time = 0.0
                            elif speech_detected:
                                silence_time += chunk_duration
                                if silence_time > max_silence_time:
                                    print("🛑 Silence after speech detected, stopping.")
                                    break
                                    
                        except Exception as vad_error:
                            print(f"VAD error: {vad_error}")
                            if total_time > 10.0:
                                print("🛑 Maximum recording time reached.")
                                break
                    
                    if total_time > 30.0:
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

    final_audio = np.concatenate(audio_chunks, axis=0)
    
    if len(final_audio) < fs * 0.5:
        print("⚠️ Recording too short")
        return None
    
    audio_level = np.abs(final_audio).mean()
    if audio_level < 0.001:
        print("⚠️ Audio appears to be silent or very quiet")
        print(f"Audio level: {audio_level}")
        return None
    
    if final_audio.dtype == np.float32:
        final_audio = np.clip(final_audio, -1.0, 1.0)
        final_audio_int16 = (final_audio * 32767).astype(np.int16)
    else:
        final_audio_int16 = final_audio.astype(np.int16)
    
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        scipy.io.wavfile.write(temp_file.name, fs, final_audio_int16)
        print(f"✅ Audio saved: {temp_file.name}")
        print(f"📊 Audio stats: {len(final_audio_int16)/fs:.1f}s, level: {audio_level:.4f}")
        return temp_file.name
    except Exception as save_error:
        print(f"❌ Error saving audio file: {save_error}")
        return None