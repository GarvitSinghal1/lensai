"""
Shared HF LLM caller - centralized function for calling Hugging Face
Inference API with multi-model fallback chain (Kimi K2.5 -> Mistral -> Zephyr).
"""

import time
import requests
from typing import Optional

import config
from utils.logger import log


def call_hf_llm(prompt: str, max_tokens: int = 1500,
                temperature: float = 0.3, system_prompt: str = "") -> Optional[str]:
    """
    Call HF Inference API for text generation with multi-model fallback.
    Tries: Kimi K2.5 -> Mistral-7B -> Zephyr-7B
    """
    headers = {"Authorization": f"Bearer {config.HF_API_KEY}"}
    models = [config.LLM_MODEL, config.LLM_FALLBACK, config.LLM_FALLBACK_2]

    for model_idx, model in enumerate(models):
        url = f"{config.HF_API_BASE}/{model}"
        formatted_prompt = _format_prompt_for_model(model, prompt, system_prompt)

        payload = {
            "inputs": formatted_prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
                "do_sample": temperature > 0,
            },
        }

        for attempt in range(config.HF_MAX_RETRIES):
            try:
                log.debug(f"LLM call: {model} (attempt {attempt + 1})")
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
                    log.warning(f"Model {model} loading, waiting {min(wait_time, 60):.0f}s...")
                    time.sleep(min(wait_time, 60))
                    continue

                if resp.status_code == 429:
                    log.warning(f"Rate limited on {model}, waiting 10s...")
                    time.sleep(10)
                    continue

                if resp.status_code == 422:
                    log.warning(f"Invalid input for {model}: {resp.text[:200]}")
                    break

                resp.raise_for_status()
                result = resp.json()

                if isinstance(result, list) and len(result) > 0:
                    text = result[0].get("generated_text", "").strip()
                    if text:
                        log.debug(f"LLM response from {model}: {len(text)} chars")
                        return text

                text = str(result).strip()
                if text:
                    return text

            except requests.exceptions.Timeout:
                log.warning(f"Timeout on {model} (attempt {attempt + 1})")
                continue
            except Exception as e:
                log.warning(f"Error with {model}: {e}")
                if attempt < config.HF_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                continue

        if model_idx < len(models) - 1:
            log.warning(f"All retries failed for {model}, trying next model...")

    log.error("All LLM models failed")
    return None


def _format_prompt_for_model(model: str, prompt: str, system_prompt: str = "") -> str:
    """Format the prompt according to the model's expected chat template."""
    model_lower = model.lower()

    # Kimi K2.5 uses ChatML / im_start format
    if "kimi" in model_lower or "k2" in model_lower:
        IM_S = "<" + "|im_start|>"
        IM_E = "<" + "|im_end|>"
        parts = []
        if system_prompt:
            parts.append(f"{IM_S}system\n{system_prompt}{IM_E}")
        parts.append(f"{IM_S}user\n{prompt}{IM_E}")
        parts.append(f"{IM_S}assistant")
        return "\n".join(parts)

    # Mistral instruct format
    elif "mistral" in model_lower:
        if system_prompt:
            return f"<s>[INST] {system_prompt}\n\n{prompt} [/INST]"
        return f"<s>[INST] {prompt} [/INST]"

    # Zephyr format
    elif "zephyr" in model_lower:
        SYS_S = "<" + "|system|>"
        USR_S = "<" + "|user|>"
        AST_S = "<" + "|assistant|>"
        END = "</s>"
        parts = []
        if system_prompt:
            parts.append(f"{SYS_S}\n{system_prompt}{END}")
        parts.append(f"{USR_S}\n{prompt}{END}")
        parts.append(f"{AST_S}")
        return "\n".join(parts)

    # Generic fallback
    else:
        if system_prompt:
            return f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        return f"User: {prompt}\n\nAssistant:"
