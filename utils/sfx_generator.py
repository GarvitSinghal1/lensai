
import os
import wave
import math
import struct
import random
from pathlib import Path

def generate_tone(filename, duration=0.5, freq=440, amp=0.5, waveform="sine"):
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1) # mono
        obj.setsampwidth(2)
        obj.setframerate(sample_rate)
        
        for i in range(n_samples):
            t = i / sample_rate
            
            if waveform == "sine":
                val = math.sin(2 * math.pi * freq * t)
            elif waveform == "noise":
                val = random.uniform(-1, 1) * ((n_samples - i) / n_samples) # Fade out noise
            elif whoosh := (waveform == "whoosh"):
                # Sweep frequency down
                f = freq * (1 - (i / n_samples))
                val = math.sin(2 * math.pi * f * t) * ((n_samples - i) / n_samples)
            elif boom := (waveform == "boom"):
                # Low freq decay
                val = math.sin(2 * math.pi * 60 * t) * math.exp(-i / (sample_rate * 0.1))
            else:
                val = 0
            
            # Scale and pack
            data = struct.pack('<h', int(val * 32767 * amp))
            obj.writeframesraw(data)
            
    print(f"Generated {filename}")

def main():
    base_dir = Path("media/sfx")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    generate_tone(str(base_dir / "whoosh.wav"), duration=0.3, freq=800, waveform="whoosh")
    generate_tone(str(base_dir / "boom.wav"), duration=0.6, freq=60, waveform="boom")
    generate_tone(str(base_dir / "ding.wav"), duration=0.3, freq=1200, waveform="sine")
    generate_tone(str(base_dir / "camera_shutter.wav"), duration=0.1, freq=2000, waveform="sine") # Just a high blip
    generate_tone(str(base_dir / "glitch.wav"), duration=0.2, freq=0, waveform="noise")
    
    print("SFX generation complete.")

if __name__ == "__main__":
    main()
