
import os
import wave
import math
import struct
import random
import numpy as np
from pathlib import Path

def save_wav(filename, data, sample_rate=44100):
    """Save float data (-1 to 1) to WAV."""
    # Normalize to prevent clipping
    max_val = np.max(np.abs(data))
    if max_val > 0:
        data = data / max_val * 0.9  # Leave headroom

    # Convert to 16-bit PCM
    data_int = (data * 32767).astype(np.int16)
    
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1) # mono
        obj.setsampwidth(2)
        obj.setframerate(sample_rate)
        obj.writeframes(data_int.tobytes())
    print(f"Generated {filename}")

def generate_noise(duration, sample_rate=44100, color="white"):
    n_samples = int(sample_rate * duration)
    if color == "white":
        return np.random.uniform(-1, 1, n_samples)
    elif color == "pink":
        # Simple pink noise approximation (1/f)
        white = np.random.randn(n_samples)
        row_indices = np.arange(n_samples)
        # simplistic filter
        b = np.array([0.049922035, -0.095993537, 0.050612699, -0.004408786])
        a = np.array([1.0, -2.494956002,   2.017265875,  -0.522189400])
        # This is hard to do without scipy.signal.lfilter
        # Fallback to white noise with decay for now
        return white
    return np.zeros(n_samples)

def generate_sine(duration, freq, sample_rate=44100):
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t)

def envelope(data, attack=0.01, release=0.1, sample_rate=44100):
    n = len(data)
    att_samples = int(attack * sample_rate)
    rel_samples = int(release * sample_rate)
    
    env = np.ones(n)
    # Attack
    env[:att_samples] = np.linspace(0, 1, att_samples)
    # Release
    if rel_samples > 0:
        env[-rel_samples:] = np.linspace(1, 0, rel_samples)
        
    return data * env

def generate_whoosh(filename, duration=1.0):
    sr = 44100
    noise = generate_noise(duration, sr)
    
    # Low pass filter simulation (moving average)
    # Sweep frequency? effectively volume swell and cut
    # Simple swell
    t = np.linspace(0, 1, len(noise))
    # Shape: starts low, swells in middle, fades out
    shape = np.sin(np.pi * t) ** 2
    
    # Add some tone sweep
    tone = generate_sine(duration, 100, sr) * 0.1
    
    audio = (noise + tone) * shape
    save_wav(filename, audio, sr)

def generate_boom(filename, duration=1.5):
    sr = 44100
    # Deep sine sweep 100hz -> 30hz
    t = np.linspace(0, duration, int(sr*duration))
    # exp decay frequency
    freq = 60 * np.exp(-3 * t) 
    phase = 2 * np.pi * np.cumsum(freq) / sr
    audio = np.sin(phase)
    
    # Impact noise
    impact = generate_noise(0.1, sr)
    impact = np.pad(impact, (0, len(audio) - len(impact)))
    
    # Mix
    combined = audio + impact * 0.5
    combined = envelope(combined, 0.01, 0.8, sr)
    save_wav(filename, combined, sr)

def generate_ding(filename, duration=1.0):
    sr = 44100
    # Bell-like FM synthesis: Carrier + Modulator
    t = np.linspace(0, duration, int(sr*duration))
    
    # Carrier
    fc = 1200
    fm = 2.5 * fc
    mod_index = 2.0 * np.exp(-5 * t)
    
    audio = np.sin(2 * np.pi * fc * t + mod_index * np.sin(2 * np.pi * fm * t))
    audio = envelope(audio, 0.001, 0.9, sr)
    
    save_wav(filename, audio, sr)

def generate_glitch(filename, duration=0.3):
    sr = 44100
    # Random short bursts of tones and noise
    n_samples = int(sr * duration)
    audio = np.zeros(n_samples)
    
    for _ in range(5):
        start = random.randint(0, n_samples - 1000)
        len_burst = random.randint(500, 2000)
        end = min(start + len_burst, n_samples)
        
        snippet_type = random.choice(['noise', 'square'])
        if snippet_type == 'noise':
            audio[start:end] = np.random.uniform(-1, 1, end-start)
        else:
            freq = random.uniform(200, 2000)
            t_snip = np.linspace(0, (end-start)/sr, end-start)
            audio[start:end] = np.sign(np.sin(2*np.pi*freq*t_snip))
            
    save_wav(filename, audio, sr)

def generate_shutter(filename, duration=0.15):
    sr = 44100
    # Quick noise burst + mechanical click
    noise = generate_noise(0.05, sr)
    click = generate_sine(0.02, 1000, sr)
    
    audio = np.concatenate([noise, np.zeros(1000), click])
    # pad or crop
    if len(audio) < int(sr*duration):
        audio = np.pad(audio, (0, int(sr*duration)-len(audio)))
    else:
        audio = audio[:int(sr*duration)]
        
    save_wav(filename, audio, sr)

def generate_music_loop(filename, duration=10.0, bpm=120):
    sr = 44100
    n_samples = int(sr * duration)
    audio = np.zeros(n_samples)
    
    beat_dur = 60 / bpm
    samples_per_beat = int(beat_dur * sr)
    total_beats = int(duration / beat_dur)
    
    # Simple Kick Drum (Low sine decay)
    kick_t = np.linspace(0, 0.2, int(sr*0.2))
    kick_freq = 150 * np.exp(-20 * kick_t)
    kick = np.sin(2 * np.pi * np.cumsum(kick_freq)/sr) * np.exp(-5 * kick_t)
    
    # Simple HiHat (High noise decay)
    hat_t = np.linspace(0, 0.05, int(sr*0.05))
    hat = np.random.uniform(-0.5, 0.5, len(hat_t)) * np.exp(-40 * hat_t)
    
    # Bass Line (Sine wave)
    
    for i in range(total_beats):
        pos = i * samples_per_beat
        
        # Kick on 1 and 3
        if i % 2 == 0: # 1, 3... (0-indexed 0, 2)
            end = min(pos + len(kick), n_samples)
            audio[pos:end] += kick[:end-pos]
            
        # Hat on every beat + offbeats
        for offset in [0, 0.5]:
            hat_pos = int(pos + offset * samples_per_beat)
            end = min(hat_pos + len(hat), n_samples)
            if end > hat_pos:
                audio[hat_pos:end] += hat[:end-hat_pos] * 0.5
                
        # Bass note (Root - Fifth)
        freq = 55 if (i % 4 < 2) else 82.4 # A1 then E2
        bass_dur = 0.4
        bass_t = np.linspace(0, bass_dur, int(sr * bass_dur))
        bass = np.sin(2 * np.pi * freq * bass_t) * 0.3 * np.exp(-2 * bass_t)
        
        end = min(pos + len(bass), n_samples)
        audio[pos:end] += bass[:end-pos]

    # Add ambient drone
    t_drone = np.linspace(0, duration, n_samples)
    drone = np.sin(2 * np.pi * 110 * t_drone) * 0.05 # Low A drone
    audio += drone
    
    save_wav(filename, audio, sr)

def main():
    base_dir = Path("media/sfx")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    print("Generating High-Quality SFX...")
    generate_whoosh(str(base_dir / "whoosh.wav"))
    generate_boom(str(base_dir / "boom.wav"))
    generate_ding(str(base_dir / "ding.wav"))
    generate_glitch(str(base_dir / "glitch.wav"))
    generate_shutter(str(base_dir / "camera_shutter.wav"))
    generate_music_loop(str(base_dir / "music_loop.wav"), duration=10.0)
    
    print("SFX generation complete.")

if __name__ == "__main__":
    main()
