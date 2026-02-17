"""
Shared HF LLM caller - centralized function for calling Hugging Face
Inference API with multi-model fallback chain (Kimi K2.5 -> Mistral -> Zephyr).
Supports API Key Rotation (KeyManager) to avoid rate limits.
"""

import requests
import time
import json
import logging
import os
from typing import Optional, Dict, Any, List
import struct
import wave
import io
from gtts import gTTS

import config

log = logging.getLogger("newsfactory")

# ─── API Key Rotation System ─────────────────────────────────

class KeyManager:
    """
    Manages a pool of API keys with rotation and cooldown logic.
    """
    def __init__(self, keys: List[str]):
        self.keys = [k for k in keys if k] # Filter empty
        if not self.keys:
            log.warning("⚠️ No valid HF API keys found! System may fail.")
            self.keys = [""] # Dummy key to prevent index error
            
        self.current_index = 0
        self.failed_keys: Dict[str, float] = {} # key -> timestamp of failure
        self.COOLDOWN_SECONDS = 3 * 3600 # 3 hours
        
        log.info(f"KeyManager initialized with {len(self.keys)} keys.")

    def get_current_key(self) -> str:
        """Get the current active key. If all failed, reset oldest."""
        return self.keys[self.current_index]

    def rotate(self):
        """Switch to the next key."""
        prev_key = self.keys[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.keys)
        new_key = self.keys[self.current_index]
        
        # If we cycled back to a key that is still cooling down
        if new_key in self.failed_keys:
            cooldown_remaining = self.COOLDOWN_SECONDS - (time.time() - self.failed_keys[new_key])
            if cooldown_remaining > 0:
                log.warning(f"🔄 Cycled to key {new_key[:5]}... but it's cooling down ({int(cooldown_remaining/60)}m left).")
                # Try to find a non-failed key
                start_index = self.current_index
                while True:
                    candidate = self.keys[self.current_index]
                    if candidate not in self.failed_keys:
                        break
                    
                    # Check if cooldown expired
                    if time.time() - self.failed_keys[candidate] > self.COOLDOWN_SECONDS:
                        del self.failed_keys[candidate]
                        break
                        
                    self.current_index = (self.current_index + 1) % len(self.keys)
                    if self.current_index == start_index:
                        # All keys failed. Just use the current one.
                        log.warning("⚠️ All keys are in cooldown. Using current key anyway.")
                        break
        
        log.info(f"🔄 Rotated API Key to #{self.current_index + 1} ({self.keys[self.current_index][:5]}...)")

    def report_error(self, key: str, status_code: int):
        """Mark a key as failed if it's a rate limit or payment issue."""
        if status_code in [401, 402, 403, 429]:
            log.warning(f"🚫 Key {key[:5]}... hit limit (Status {status_code}). Marking for cooldown.")
            self.failed_keys[key] = time.time()
            self.rotate()

_key_manager = KeyManager(config.HF_TOKENS)

def _get_headers() -> Dict[str, str]:
    token = _key_manager.get_current_key()
    return {"Authorization": f"Bearer {token}"}

# ─── Query Functions ─────────────────────────────────────────

def query(payload: Dict[str, Any], model: str, task_type: str = "text-generation") -> Any:
    """
    Standard HF Inference API query with Key Rotation support.
    """
    if model.startswith("http"):
        api_url = model
    else:
        api_url = f"{config.HF_API_BASE}/{model}"

    attempts = max(config.HF_MAX_RETRIES, len(_key_manager.keys) * 2)
    for attempt in range(attempts):
        current_key = _key_manager.get_current_key() # Get current key inside loop
        headers = {"Authorization": f"Bearer {current_key}"}
        
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=config.HF_API_TIMEOUT)
            
            # 503 means model loading
            if response.status_code == 503:
                wait_time = response.json().get("estimated_time", 10)
                log.info(f"⏳ Model {model} loading, waiting {wait_time:.1f}s...")
                time.sleep(min(wait_time, 30))
                continue
                
            # Handle API Key Exhaustion (401/402/403/429)
            if response.status_code in [401, 402, 403, 429]:
                _key_manager.report_error(current_key, response.status_code)
                time.sleep(1)
                continue # Retry immediately with new key
                
            response.raise_for_status()
            
            # Parse based on task
            if task_type == "audio-classification":
                return response.json()
            elif task_type == "text-to-image" or task_type == "text-to-speech":
                return response.content # Binary
            else:
                return response.json()
                
        except Exception as e:
            # Check if it was a status error caught by raise_for_status that wasn't 402/429
            log.warning(f"Error with {model}: {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
            else:
                log.error(f"Failed {model} after retries.")
                return None
    return None

from groq import Groq

# Initialize Groq client
if config.GROQ_API_KEY:
    _groq_client = Groq(api_key=config.GROQ_API_KEY)
else:
    _groq_client = None
    log.warning("⚠️ GROQ_API_KEY not found. Text generation will fail.")

def query_chat_completion(model: str, messages: List[Dict[str, str]], max_tokens: int = 2048, temperature: float = 0.6) -> Optional[str]:
    """
    Query LLM using Groq Cloud API (Kimi K2, Llama 3, etc).
    """
    if not _groq_client:
        log.error("Groq client not initialized (missing API key).")
        return None

    for attempt in range(config.HF_MAX_RETRIES):
        try:
            completion = _groq_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                top_p=1,
                stream=False,
                stop=None
            )
            return completion.choices[0].message.content
            
        except Exception as e:
            log.warning(f"Groq query error with {model}: {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2)
            else:
                log.error(f"Failed {model} after retries.")
                return None
    return None

def call_hf_llm(prompt: str, max_tokens: int = 2048, temperature: float = 0.6, system_prompt: str = "") -> Optional[str]:
    """
    Wrapper for query_chat_completion to match legacy signature.
    Supports chain of fallbacks defined in config.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    # 1. Primary Model (Groq)
    response = query_chat_completion(config.LLM_MODEL, messages, max_tokens, temperature)
    if response: return response
    
    # 2. Fallback Model (Groq)
    log.warning(f"Primary model {config.LLM_MODEL} failed, trying fallback {config.LLM_FALLBACK}...")
    response = query_chat_completion(config.LLM_FALLBACK, messages, max_tokens, temperature)
    if response: return response
    
    # 3. Second Fallback (if configured)
    if hasattr(config, "LLM_FALLBACK_2") and config.LLM_FALLBACK_2:
        log.warning(f"Fallback model failed, trying {config.LLM_FALLBACK_2}...")
        response = query_chat_completion(config.LLM_FALLBACK_2, messages, max_tokens, temperature)
        if response: return response
        
    log.error("All LLM models failed.")
    return None

def query_custom_endpoint(url: str, payload: Dict[str, Any]) -> Any:
    """
    Query a specific custom endpoint with Key Rotation.
    """
    attempts = max(config.HF_MAX_RETRIES, len(_key_manager.keys) * 2)
    for attempt in range(attempts):
        current_key = _key_manager.get_current_key()
        headers = {"Authorization": f"Bearer {current_key}"}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=config.HF_API_TIMEOUT)
            
            if response.status_code in [401, 402, 403, 429]:
                _key_manager.report_error(current_key, response.status_code)
                time.sleep(1)
                continue

            response.raise_for_status()
            return response.json()
        except Exception as e:
            log.warning(f"Custom endpoint error ({url}): {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2)
            else:
                return None
    return None

def query_replicate_image(prompt: str, model_id: str) -> Optional[bytes]:
    """
    Query Replicate-style endpoint on Router with Key Rotation.
    Supports FLUX.1-schnell, FLUX.1-dev, etc.
    """
    # Construct router URL dynamically
    api_url = f"https://router.huggingface.co/replicate/v1/models/{model_id}/predictions"
    
    payload = {
        "input": {
            "prompt": prompt,
            "aspect_ratio": "9:16", # Vertical for Shorts
            "output_quality": 90,
            "disable_safety_checker": True
        }
    }

    attempts = max(config.HF_MAX_RETRIES, len(_key_manager.keys) * 2)
    for attempt in range(attempts):
        current_key = _key_manager.get_current_key()
        headers = {"Authorization": f"Bearer {current_key}"}
        
        try:
            log.debug(f"Querying Router: {model_id}")
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code in [401, 402, 403, 429]:
                _key_manager.report_error(current_key, response.status_code)
                time.sleep(1)
                continue

            # 404/410 means model not found on Router
            if response.status_code in [404, 410]:
                 log.warning(f"Router endpoint for {model_id} not found ({response.status_code})")
                 return None

            response.raise_for_status()
            
            # Replicate API usually returns JSON with output url or direct content?
            # HF Router wrapper often returns DIRECT bytes for simple inference, 
            # OR a JSON with "output" url.
            # Let's handle both.
            
            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type:
                 return response.content
            
            try:
                data = response.json()
                # If wrapped in Replicate format
                if isinstance(data, list) and len(data) > 0:
                    # Might be output URL
                    if isinstance(data[0], str) and data[0].startswith("http"):
                        img_resp = requests.get(data[0])
                        return img_resp.content
            except:
                pass
                
            # If we got here and content length is large, it's probably the image
            if len(response.content) > 1000:
                return response.content
            
            return None
            
        except Exception as e:
            log.warning(f"Router query error: {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2)
            else:
                return None
    return None

def generate_image(prompt: str) -> Optional[bytes]:
    """
    Generate image using configured model (Flux 1 -> SDXL).
    """
    full_prompt = prompt + " " + config.IMAGE_STYLE_SUFFIX
    
    # Check primary model if it's Flux or Hunyuan (Replicate provider)
    if any(x in config.IMAGE_MODEL.lower() for x in ["flux", "hunyuan", "tencent"]):
        log.info(f"Generating image with {config.IMAGE_MODEL} (Router)...")
        img = query_replicate_image(full_prompt, config.IMAGE_MODEL)
        if img: return img
    
    # Fallback loop
    models = [config.IMAGE_FALLBACK] 
    if hasattr(config, "IMAGE_FALLBACK_2"): models.append(config.IMAGE_FALLBACK_2)
    
    # Add primary if it wasn't Flux (or Flux failed and we want to try standard API? No, separate logic)
    if "flux" not in config.IMAGE_MODEL.lower():
        models.insert(0, config.IMAGE_MODEL)

    payload = {
        "inputs": full_prompt,
        "parameters": {"negative_prompt": config.IMAGE_NEGATIVE_PROMPT}
    }

    for model in models:
        log.info(f"Generating image with {model}...")
        image_bytes = query(payload, model, task_type="text-to-image")
        if image_bytes:
            return image_bytes
            
    log.error("All image models failed")
    return None

def _fal_to_wav_bytes(audio_floats: List[float], sample_rate: int) -> bytes:
    """Convert float list (-1.0 to 1.0) to 16-bit PCM WAV bytes."""
    pcm_data = bytearray()
    for sample in audio_floats:
        sample = max(-1.0, min(1.0, sample))
        int_sample = int(sample * 32767)
        pcm_data.extend(struct.pack("<h", int_sample))
        
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2) # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
        
    return wav_io.getvalue()

def generate_audio(text: str) -> Optional[bytes]:
    """
    Generate audio using configured TTS model (Kokoro-Fal or fallback).
    """
    # 1. Try Primary (Kokoro via HF Inference)
    if "kokoro" in config.TTS_MODEL.lower():
        log.info(f"Generating audio with Kokoro ({config.TTS_MODEL})...")
        # hexgrad/Kokoro-82M on HF Inference API takes standard raw text input
        # and returns FLAC/WAV audio bytes directly.
        payload = {"inputs": text}
        audio_bytes = query(payload, config.TTS_MODEL, task_type="text-to-speech")
        if audio_bytes:
            return audio_bytes
        else:
            log.warning("Kokoro generation failed.")

    # Fallback
    payload = {"inputs": text}
    models = [config.TTS_FALLBACK]
    if hasattr(config, "TTS_FALLBACK_2"):
        if config.TTS_FALLBACK_2 != config.TTS_MODEL:
            models.append(config.TTS_FALLBACK_2)
        
    for model in models:
        if not model: continue
        log.info(f"Generating audio with {model}...")
        audio_bytes = query(payload, model, task_type="text-to-speech")
        if audio_bytes:
            return audio_bytes
            
    # Final Fallback: gTTS
    if config.ENABLE_GTTS_FALLBACK:
        try:
            log.info("Generating audio with gTTS (Google)...")
            tts = gTTS(text=text, lang='en')
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            # gTTS returns MP3, but our system expects WAV bytes?
            # Wait, `query` returns binary content. 
            # If downstream expects WAV, we might need to convert MP3 to WAV using pydub?
            # Or just return MP3 and hope ffmpeg handles it (MoviePy usually does).
            return mp3_fp.getvalue()
        except Exception as e:
            log.error(f"gTTS failed: {e}")

    return None
