"""
TTS Engine — generates voiceover audio using HF Inference API.
Fallback chain: Kokoro-82M → MiniMax Speech-02-Turbo → MMS-TTS
"""

import io
import time
import struct
import wave
import requests
from pathlib import Path
from typing import Optional

import config
from utils.logger import log
from utils import hf_client


def _save_audio(audio_bytes: bytes, output_path: Path) -> bool:
    """Save audio bytes to a file. Handles both WAV and FLAC formats."""
    try:
        # Check if it's already a valid WAV
        if audio_bytes[:4] == b'RIFF':
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)
            return True
        
        # Check if it's FLAC
        if audio_bytes[:4] == b'fLaC':
            flac_path = output_path.with_suffix('.flac')
            with open(flac_path, 'wb') as f:
                f.write(audio_bytes)
            # Try to convert to WAV using pydub
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(flac_path, format="flac")
                audio.export(output_path, format="wav")
                flac_path.unlink()  # Remove temp flac
                return True
            except Exception as e:
                log.warning(f"Could not convert FLAC to WAV: {e}")
                # Keep the FLAC file as fallback
                output_path = flac_path
                return True
        
        # Try saving raw and let pydub figure it out
        temp_path = output_path.with_suffix('.raw')
        with open(temp_path, 'wb') as f:
            f.write(audio_bytes)
        
        try:
            from pydub import AudioSegment
            # Try common formats
            for fmt in ['wav', 'mp3', 'flac', 'ogg']:
                try:
                    audio = AudioSegment.from_file(temp_path, format=fmt)
                    audio.export(output_path, format="wav")
                    temp_path.unlink()
                    return True
                except Exception:
                    continue
        except ImportError:
            pass
        
        # Last resort: save as-is
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        temp_path.unlink(missing_ok=True)
        return True
        
    except Exception as e:
        log.error(f"Failed to save audio: {e}")
        return False


def _get_audio_duration(file_path: Path) -> float:
    """Get duration of an audio file in seconds."""
    try:
        # Try pydub first
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception:
        pass
    
    try:
        # Try wave module for WAV files
        with wave.open(str(file_path), 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        pass
    
    # Estimate based on file size (rough: ~16KB per second for 16kHz mono)
    file_size = file_path.stat().st_size
    estimated = file_size / 16000.0
    log.warning(f"Estimated audio duration from file size: {estimated:.1f}s")
    return max(estimated, 2.0)


def _generate_local_tts(text: str) -> Optional[bytes]:
    """Fallback to local system TTS (macOS 'say')."""
    import sys
    import subprocess
    import tempfile
    import os
    
    if sys.platform != "darwin":
        return None
        
    try:
        # Create temp file for output
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            temp_path = tf.name
            
        # Run 'say' command (Linear PCM 16-bit 22kHz WAV)
        subprocess.run(["say", "-o", temp_path, "--data-format=LEI16@22050", text], check=True)
        
        # Read bytes
        with open(temp_path, "rb") as f:
            audio_bytes = f.read()
            
        # Cleanup
        os.remove(temp_path)
        
        if len(audio_bytes) > 1000:
             log.info(f"Generated local TTS with 'say' ({len(audio_bytes)} bytes)")
             return audio_bytes
             
    except Exception as e:
        log.warning(f"Local TTS failed: {e}")
        
    return None

def _generate_kokoro_tts(text: str) -> Optional[bytes]:
    """Generate TTS using Kokoro-82M model via Replicate provider on HF InferenceClient."""
    if "Kokoro" not in config.TTS_MODEL:
        return None
        
    try:
        from huggingface_hub import InferenceClient
        import os
        
        # Iterate through all available tokens
        for i, token in enumerate(config.HF_TOKENS):
            if not token:
                continue
                
            try:
                log.info(f"Calling Kokoro-82M (via Replicate) using Key #{i+1}...")
                
                client = InferenceClient(
                    provider="replicate",
                    api_key=token,
                )
                
                # Audio is returned as bytes
                audio_bytes = client.text_to_speech(
                    text,
                    model="hexgrad/Kokoro-82M",
                )
                
                if audio_bytes and len(audio_bytes) > 0:
                    log.info(f"Kokoro TTS generation successful with Key #{i+1} ({len(audio_bytes)} bytes)")
                    return audio_bytes
                else:
                    log.warning(f"Kokoro TTS returned empty bytes with Key #{i+1}.")
            
            except Exception as e:
                # Check for 402/Quota errors and continue to next key
                error_str = str(e)
                if "402" in error_str or "429" in error_str or "Payment Required" in error_str:
                    log.warning(f"Key #{i+1} depleted or rate limited (402/429). Rotating...")
                    continue
                else:
                    log.warning(f"Kokoro TTS failed with Key #{i+1}: {e}")
                    # If it's a different error (e.g. model not found), maybe don't rotate? 
                    # But for now, let's keep trying other keys just in case.
                    continue

        log.error("All HF Tokens failed for Kokoro TTS.")
        return None
            
    except ImportError:
        log.error("huggingface_hub not installed. Please install it to use Kokoro TTS.")
        return None
    except Exception as e:
        log.error(f"Kokoro TTS setup failed: {e}")
        return None

def generate_tts(text: str, output_path: Path) -> Optional[dict]:
    """
    Generate TTS audio for a given text.
    
    Returns:
        dict with 'audio_path' and 'duration_seconds', or None on failure.
    """
    if not text.strip():
        log.warning("Empty text provided to TTS")
        return None
    
    log.info(f"Generating TTS ({len(text)} chars): \"{text[:60]}...\"")
    
def _generate_gtts(text: str, lang: str = "en") -> Optional[bytes]:
    """Fallback to Google TTS (gTTS). Free and higher quality than local system TTS."""
    if not hasattr(config, "ENABLE_GTTS_FALLBACK") or not config.ENABLE_GTTS_FALLBACK:
        return None
        
    try:
        from gtts import gTTS
        import io
        
        tts = gTTS(text=text, lang=lang, slow=False)
        mp3_io = io.BytesIO()
        tts.write_to_fp(mp3_io)
        mp3_bytes = mp3_io.getvalue()
        
        if len(mp3_bytes) > 1000:
            log.info(f"Generated Google TTS ({len(mp3_bytes)} bytes)")
            # Note: gTTS outputs MP3. Our system expects bytes.
            # _save_audio just writes bytes. Check if downstream needs WAV.
            # _get_audio_duration supports pydub (mp3) or wave (wav).
            # If pydub is missing, wave will fail on MP3.
            # We should ideally convert MP3 to WAV if pydub is not guaranteed?
            # But requirements.txt has pydub.
            return mp3_bytes
            
    except Exception as e:
        log.warning(f"Google TTS failed: {e}")
        
    return None

    return {
        "audio_path": str(output_path),
        "duration_seconds": duration,
    }


def generate_tts(text: str, output_path: Path, lang: str = "en") -> Optional[dict]:
    """
    Generate TTS audio for a given text.
    
    Args:
        text: Text to speak
        output_path: Path to save audio
        lang: Language code ('en', 'hi', etc.)
        
    Returns:
        dict with 'audio_path' and 'duration_seconds', or None on failure.
    """
    if not text.strip():
        log.warning("Empty text provided to TTS")
        return None
    
    log.info(f"Generating TTS ({lang}, {len(text)} chars): \"{text[:60]}...\"")
    
    audio_bytes = None
    
    # Logic for Hindi
    if lang == "hi":
        # For Hindi, prioritize gTTS as Kokoro/HF models might not support Devanagari well yet
        log.info("Language is Hindi. Using gTTS directly.")
        audio_bytes = _generate_gtts(text, lang="hi")
        
    else:
        # Default English Logic
        # 0. Specialized High-Quality TTS (Kokoro-82M via Replicate)
        # Verify if Kokoro supports the requested lang? Currently mostly English.
        if lang == "en":
            audio_bytes = _generate_kokoro_tts(text)

        # 1. Use centralized HF client (MMS -> SpeechT5) if Kokoro fails
        if not audio_bytes:
            # Check if hf_client supports lang? It defaults to English usually.
            # Only use HF for EN for now to avoid weird accents.
            if lang == "en":
                audio_bytes = hf_client.generate_audio(text)
        
        # 2. Fallback: Google TTS (gTTS)
        if not audio_bytes:
            audio_bytes = _generate_gtts(text, lang=lang)
    
    # 3. Final fallback: Local System TTS (Mac only) - English only usually
    if not audio_bytes and lang == "en":
        log.warning("All HF/Google TTS models failed, trying local system TTS...")
        audio_bytes = _generate_local_tts(text)
    
    if not audio_bytes:
        log.error("All TTS generation methods failed")
        return None
    
    # Save audio file
    # gTTS returns MP3, others WAV.
    # If MP3, we should save as .mp3?
    # But composer might expect .wav?
    # moviepy AudioFileClip supports mp3.
    # _save_audio logic:
    
    # Check if header looks like MP3 or RIFF/WAV?
    is_mp3 = audio_bytes[:3] == b'ID3' or audio_bytes[:2] == b'\xff\xfb'
    
    if is_mp3:
        output_path = Path(output_path).with_suffix('.mp3')
    else:
        output_path = Path(output_path).with_suffix('.wav')
        
    
    if not _save_audio(audio_bytes, output_path):
        return None
    
    # Speed up audio by 1.5x using ffmpeg (atempo)
    # Only for English? Hindi might be too fast if sped up.
    # Let's speed up Hindi only 1.3x? Or keep 1.5x?
    # gTTS is slow. 1.5x is usually good.
    speed = 1.3 if lang == 'hi' else 1.5
    _speed_up_file(output_path, speed=speed)
    
    # Get duration
    duration = _get_audio_duration(output_path)
    
    log.info(f"TTS generated: {output_path.name} ({duration:.1f}s)")
    
    return {
        "audio_path": str(output_path),
        "duration_seconds": duration,
    }


def _speed_up_file(file_path: Path, speed: float = 1.5):
    """Speed up audio file using ffmpeg atempo filter (preserves pitch)."""
    if speed == 1.0:
        return

    try:
        import subprocess
        import shutil
        
        temp_path = file_path.with_suffix(f".fast{file_path.suffix}")
        
        # ffmpeg -y -i input -filter:a "atempo=1.5" output
        cmd = [
            "ffmpeg", "-y", "-i", str(file_path),
            "-filter:a", f"atempo={speed}",
            str(temp_path)
        ]
        
        # Suppress output
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        if temp_path.exists() and temp_path.stat().st_size > 0:
            shutil.move(temp_path, file_path)
            log.info(f"Sped up audio {file_path.name} by {speed}x")
        else:
            log.warning(f"Speedup failed: temp file missing or empty for {file_path.name}")
            
    except Exception as e:
        log.warning(f"Failed to speed up audio: {e}")



def generate_tts_for_scenes(scenes: list[dict], temp_dir: Path, lang: str = "en") -> list[dict]:
    """
    Generate TTS audio for all scenes in a script.
    
    Adds 'audio_path' and 'actual_duration' to each scene dict.
    Returns the updated scenes list (only scenes with successful TTS).
    """
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    successful_scenes = []
    
    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "")
        if not narration:
            continue
        
        audio_file = temp_dir / f"scene_{i:02d}_{lang}.wav"
        result = generate_tts(narration, audio_file, lang=lang)
        
        if result:
            scene_copy = scene.copy()
            scene_copy["audio_path"] = result["audio_path"]
            scene_copy["actual_duration"] = result["duration_seconds"]
            successful_scenes.append(scene_copy)
        else:
            log.warning(f"Skipping scene {i} (TTS failed): {narration[:50]}...")
        
        # Small delay between TTS calls to avoid rate limiting
        if i < len(scenes) - 1:
            time.sleep(1)
    
    log.info(f"TTS complete: {len(successful_scenes)}/{len(scenes)} scenes generated")
    return successful_scenes
