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


def _call_hf_tts(text: str, model: str) -> Optional[bytes]:
    """Call HF Inference API for text-to-speech. Returns raw audio bytes."""
    headers = {"Authorization": f"Bearer {config.HF_API_KEY}"}
    url = f"{config.HF_API_BASE}/{model}"
    
    payload = {"inputs": text}
    
    for attempt in range(config.HF_MAX_RETRIES):
        try:
            resp = requests.post(
                url, headers=headers, json=payload,
                timeout=config.HF_API_TIMEOUT
            )
            
            if resp.status_code == 503:
                wait_time = 30
                try:
                    wait_time = resp.json().get("estimated_time", 30)
                except Exception:
                    pass
                log.warning(f"TTS model {model} loading, waiting {wait_time:.0f}s...")
                time.sleep(min(wait_time, 60))
                continue
            
            resp.raise_for_status()
            
            content_type = resp.headers.get("content-type", "")
            if "audio" in content_type or len(resp.content) > 1000:
                return resp.content
            
            log.warning(f"TTS returned non-audio content: {content_type}")
            return None
            
        except requests.exceptions.Timeout:
            log.warning(f"TTS timeout (attempt {attempt + 1})")
            continue
        except Exception as e:
            log.warning(f"TTS error with {model}: {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            continue
    
    return None


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
    
    # Try primary model (Kokoro-82M)
    audio_bytes = _call_hf_tts(text, config.TTS_MODEL)
    
    # Try fallback 1 (MiniMax Speech-02-Turbo)
    if not audio_bytes:
        log.warning(f"Primary TTS ({config.TTS_MODEL}) failed, trying MiniMax...")
        audio_bytes = _call_hf_tts(text, config.TTS_FALLBACK)
    
    # Try fallback 2 (MMS-TTS)
    if not audio_bytes:
        log.warning(f"MiniMax TTS failed, trying MMS-TTS...")
        audio_bytes = _call_hf_tts(text, config.TTS_FALLBACK_2)
    
    if not audio_bytes:
        log.error("All TTS models failed")
        return None
    
    # Save audio file
    output_path = Path(output_path).with_suffix('.wav')
    if not _save_audio(audio_bytes, output_path):
        return None
    
    # Get duration
    duration = _get_audio_duration(output_path)
    
    log.info(f"TTS generated: {output_path.name} ({duration:.1f}s)")
    
    return {
        "audio_path": str(output_path),
        "duration_seconds": duration,
    }


def generate_tts_for_scenes(scenes: list[dict], temp_dir: Path) -> list[dict]:
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
        
        audio_file = temp_dir / f"scene_{i:02d}.wav"
        result = generate_tts(narration, audio_file)
        
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
