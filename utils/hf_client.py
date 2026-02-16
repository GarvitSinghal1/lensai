"""
Shared HF LLM caller - centralized function for calling Hugging Face
Inference API with multi-model fallback chain (Kimi K2.5 -> Mistral -> Zephyr).
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

import config

log = logging.getLogger("newsfactory")

def _get_headers() -> Dict[str, str]:
    if not config.HF_API_KEY:
        log.warning("⚠️ No HF API key found (HF_TOKEN/hff_key). API calls will likely fail.")
    return {"Authorization": f"Bearer {config.HF_API_KEY}"}

def query(payload: Dict[str, Any], model: str, task_type: str = "text-generation") -> Any:
    """
    Standard HF Inference API query (legacy /models/ endpoint or provider router).
    Used for: Image Generation (Flux 1), standard TTS (MMS), and legacy models.
    """
    # Use router endpoint for standard models
    api_url = f"{config.HF_API_BASE}/{model}"
    headers = _get_headers()
    
    # Retry logic
    for attempt in range(config.HF_MAX_RETRIES):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=config.HF_API_TIMEOUT)
            
            # 503 means model loading
            if response.status_code == 503:
                wait_time = response.json().get("estimated_time", 10)
                log.info(f"⏳ Model {model} loading, waiting {wait_time:.1f}s...")
                time.sleep(min(wait_time, 30))
                continue
                
            response.raise_for_status()
            
            # Parse based on task
            if task_type == "audio-classification":
                return response.json()
            elif task_type == "text-to-image" or task_type == "text-to-speech":
                return response.content # Binary
            else:
                return response.json()
                
        except Exception as e:
            if attempt < config.HF_MAX_RETRIES - 1:
                log.warning(f"Error with {model}: {e}. Retrying...")
                time.sleep(2 * (attempt + 1))
            else:
                log.error(f"Error with {model}: {e}")
                # Return None to trigger fallback
                return None

# New Chat Completion (OpenAI format)
def query_chat_completion(model: str, messages: List[Dict[str, str]], max_tokens: int = 2048) -> Optional[str]:
    """
    Query LLM using OpenAI-compatible v1/chat/completions endpoint on Router.
    Used for: Kimi K2.5, Zephyr 7B (provider-backed models).
    """
    api_url = "https://router.huggingface.co/v1/chat/completions"
    headers = _get_headers()
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False
    }

    for attempt in range(config.HF_MAX_RETRIES):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=config.HF_API_TIMEOUT)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log.warning(f"Chat completion error with {model}: {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2)
            else:
                return None

def query_custom_endpoint(url: str, payload: Dict[str, Any]) -> Any:
    """
    Query a specific custom endpoint (e.g. Fal-ai for Kokoro).
    """
    headers = _get_headers()
    for attempt in range(config.HF_MAX_RETRIES):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=config.HF_API_TIMEOUT)
            response.raise_for_status()
            return response.json() # Expecting JSON response (audio array) for Fal
        except Exception as e:
            log.warning(f"Custom endpoint error ({url}): {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2)
            else:
                return None

# New Flux 2 (Replicate format via Router)
def query_flux_replicate(prompt: str) -> Optional[bytes]:
    """
    Query Flux 2 Dev via Replicate-style endpoint on Router.
    """
    api_url = "https://router.huggingface.co/replicate/v1/models/black-forest-labs/flux-2-dev/predictions"
    headers = _get_headers()
    # Replicate payload structure
    payload = {
        "input": {
            "prompt": prompt,
            # No image/mask inputs for T2I
            "aspect_ratio": "16:9", # Good for video
            "output_quality": 90
        }
    }

    for attempt in range(config.HF_MAX_RETRIES):
        try:
            # Step 1: Submit prediction
            response = requests.post(api_url, headers=headers, json=payload, timeout=config.HF_API_TIMEOUT)
            response.raise_for_status()
            # If standard Replicate, it returns a prediction object with 'urls' or 'output'. 
            # BUT wait, the user's code just says: return response.content.
            # And user's example was image-to-image returning bytes directly?
            # User Code: `response = requests.post(API_URL, ...); return response.content`
            # `from PIL import Image; Image.open(io.BytesIO(image_bytes))`
            # This implies the Router endpoint proxies and returns BINARY directly?
            # Or user's example was for `flux-2-dev` doing Edit which returns bytes?
            # Let's assume binary return for ease, if it fails we check JSON.
            
            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type or len(response.content) > 1000:
                 return response.content
            
            # If JSON, maybe it contains URL?
            try:
                data = response.json()
                # Check for output url if present
                pass
            except:
                pass
                
            return response.content

        except Exception as e:
            log.warning(f"Flux 2 Replicate error: {e}")
            if attempt < config.HF_MAX_RETRIES - 1:
                time.sleep(2)
            else:
                return None
    return None

def generate_text(prompt: str, system_prompt: str = "", max_new_tokens: int = 2048) -> str:
    """
    Generate text using the configured LLM fallbacks (Kimi -> Zephyr).
    """
    models = [config.LLM_MODEL, config.LLM_FALLBACK]
    if hasattr(config, "LLM_FALLBACK_2"):
        models.append(config.LLM_FALLBACK_2)
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for model in models:
        # Check if model has provider suffix (indicates Router v1/chat usage)
        if ":" in model or "kimi" in model.lower() or "zephyr" in model.lower():
            log.info(f"Generating text with {model} (Chat)...")
            result = query_chat_completion(model, messages, max_tokens=max_new_tokens)
            if result:
                return result
        else:
            # Fallback to legacy inference (if any model doesn't support chat)
            # But we are migrating all to Chat for now.
             log.info(f"Generating text with {model} (Legacy)...")
             formatted_prompt = _format_prompt_for_model(model, prompt, system_prompt)
             payload = {
                "inputs": formatted_prompt,
                "parameters": {
                    "max_new_tokens": max_new_tokens,
                    "return_full_text": False
                }
             }
             result = query(payload, model)
             if isinstance(result, list) and len(result) > 0:
                 return result[0].get("generated_text", "").strip()
        
        log.warning(f"LLM {model} failed, trying next...")
            
    log.error("All LLM models failed")
    return ""

def call_hf_llm(prompt: str, max_tokens: int = 1500, temperature: float = 0.3, system_prompt: str = "") -> Optional[str]:
    """
    Backward compatibility wrapper for call_hf_llm.
    Redirects to new generate_text function.
    """
    return generate_text(prompt, system_prompt=system_prompt, max_new_tokens=max_tokens)

def generate_image(prompt: str) -> Optional[bytes]:
    """
    Generate image using configured model (Flux 2 -> Flux 1 -> SDXL).
    """
    full_prompt = prompt + " " + config.IMAGE_STYLE_SUFFIX
    
    # Check primary model
    if "flux-2" in config.IMAGE_MODEL.lower():
        log.info(f"Generating image with Flux 2 (Replicate)...")
        img = query_flux_replicate(full_prompt)
        if img: return img
    
    # Fallback loop
    models = [config.IMAGE_FALLBACK] 
    if hasattr(config, "IMAGE_FALLBACK_2"): models.append(config.IMAGE_FALLBACK_2)
    # Also add primary if it wasn't Flux 2 (e.g. if we changed config)
    if "flux-2" not in config.IMAGE_MODEL.lower():
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
    """
    Convert float list (-1.0 to 1.0) to 16-bit PCM WAV bytes.
    """
    # Clamp and convert to int16
    pcm_data = bytearray()
    for sample in audio_floats:
        sample = max(-1.0, min(1.0, sample))
        int_sample = int(sample * 32767)
        pcm_data.extend(struct.pack("<h", int_sample))
        
    # Write to WAV in-memory
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
    # 1. Try Primary (Kokoro via Replicate)
    if config.TTS_MODEL == "kokoro-replicate":
        log.info(f"Generating audio with Kokoro (Replicate)...")
        # Direct query to Replicate endpoint
        try:
            url = config.TTS_API_URL
            payload = {"text": text}
            # Expecting JSON list: [audio_floats, sampling_rate] based on user snippet
            result = query_custom_endpoint(url, payload)
            
            if isinstance(result, list) and len(result) >= 2:
                audio_data = result[0]
                sampling_rate = result[1]
                log.info(f"Kokoro returned {len(audio_data)} samples at {sampling_rate}Hz")
                return _fal_to_wav_bytes(audio_data, sampling_rate)
            elif isinstance(result, dict) and "audio" in result and "sampling_rate" in result:
                # Fallback check for dict format just in case
                return _fal_to_wav_bytes(result["audio"], result["sampling_rate"])
            else:
                 log.warning(f"Unexpected Replicate TTS response format: {type(result)}")
                 
        except Exception as e:
            log.warning(f"Kokoro generation failed: {e}")

    # Fallback to standard HF Inference (MMS-TTS)
    # ... legacy logic ...
    payload = {"inputs": text}
    
    models = [config.TTS_FALLBACK]
    if hasattr(config, "TTS_FALLBACK_2"):
        # Ensure fallback 2 is not the same as primary
        if config.TTS_FALLBACK_2 != config.TTS_MODEL:
            models.append(config.TTS_FALLBACK_2)
        
    for model in models:
        log.info(f"Generating audio with {model}...")
        audio_bytes = query(payload, model, task_type="text-to-speech")
        if audio_bytes:
            return audio_bytes
            
    return None
