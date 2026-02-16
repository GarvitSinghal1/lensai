"""
Script Generator — creates punchy 30-45 second narration scripts for short-form video.
Optimized for short attention spans with hook → facts → kicker structure.
"""

import json
import time
import requests
from typing import Optional

import config
from utils.logger import log


def _call_hf_llm(prompt: str, max_tokens: int = 1500) -> Optional[str]:
    """Call HF Inference API for text generation."""
    headers = {"Authorization": f"Bearer {config.HF_API_KEY}"}
    
    models = [config.LLM_MODEL, config.LLM_FALLBACK]
    
    for model in models:
        url = f"{config.HF_API_BASE}/{model}"
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": 0.7,  # Slightly creative for engaging scripts
                "return_full_text": False,
            },
        }
        
        for attempt in range(config.HF_MAX_RETRIES):
            try:
                resp = requests.post(
                    url, headers=headers, json=payload,
                    timeout=config.HF_API_TIMEOUT
                )
                
                if resp.status_code == 503:
                    wait_time = resp.json().get("estimated_time", 30)
                    log.warning(f"Model {model} loading, waiting {wait_time:.0f}s...")
                    time.sleep(min(wait_time, 60))
                    continue
                
                resp.raise_for_status()
                result = resp.json()
                
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get("generated_text", "").strip()
                return str(result).strip()
                
            except requests.exceptions.Timeout:
                log.warning(f"Timeout on {model} (attempt {attempt + 1})")
                continue
            except Exception as e:
                log.warning(f"Error with {model}: {e}")
                if attempt < config.HF_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                continue
    
    log.error("All LLM models failed for script generation")
    return None


def generate_script(analysis: dict) -> Optional[list[dict]]:
    """
    Generate a punchy video narration script from the cross-reference analysis.
    
    Returns a list of scene dicts:
      [
        {
          "scene_type": "hook" | "context" | "facts" | "twist" | "kicker",
          "narration": "The spoken text for this scene",
          "image_prompt": "Detailed prompt for AI image generation",
          "estimated_duration": 5.0  # seconds
        },
        ...
      ]
    """
    topic_summary = analysis.get("topic_summary", "")
    consensus = analysis.get("consensus_facts", [])
    disputes = analysis.get("disputed_claims", [])
    exaggerations = analysis.get("exaggerations", [])
    key_details = analysis.get("key_details", [])
    severity = analysis.get("severity", "medium")
    
    prompt = f"""<s>[INST] You are a viral short-form video scriptwriter. Write a 30-45 second narration script for a news video about this topic.

TOPIC: {topic_summary}

VERIFIED FACTS:
{chr(10).join(f'- {f}' for f in consensus)}

DISPUTED/QUESTIONABLE CLAIMS:
{chr(10).join(f'- {d}' for d in disputes) if disputes else '- None'}

EXAGGERATIONS BY SOME SOURCES:
{chr(10).join(f'- {e}' for e in exaggerations) if exaggerations else '- None'}

KEY CONTEXT:
{chr(10).join(f'- {k}' for k in key_details) if key_details else '- None'}

SEVERITY: {severity}

Write EXACTLY 4-5 scenes in this JSON format:
[
  {{
    "scene_type": "hook",
    "narration": "Attention-grabbing 1-2 sentences. Start with something provocative. Under 15 words.",
    "image_prompt": "Detailed visual description for AI image generation. Photorealistic, dramatic, cinematic.",
    "estimated_duration": 3
  }},
  {{
    "scene_type": "context",
    "narration": "What happened in 2-3 clear sentences. Simple language.",
    "image_prompt": "Visual showing the event or situation",
    "estimated_duration": 7
  }},
  {{
    "scene_type": "facts",
    "narration": "The key verified facts. Punchy. Short sentences. Hit hard.",
    "image_prompt": "Visual supporting the key facts",
    "estimated_duration": 12
  }},
  {{
    "scene_type": "twist",
    "narration": "But here's what most outlets aren't telling you... [disputed or exaggerated stuff]",
    "image_prompt": "Dramatic visual shift",
    "estimated_duration": 10
  }},
  {{
    "scene_type": "kicker",
    "narration": "Closing thought. Make them think. Under 10 words.",
    "image_prompt": "Powerful closing visual",
    "estimated_duration": 4
  }}
]

RULES:
- Total narration must be speakable in 30-45 seconds
- Use simple, conversational language — NOT news anchor formal
- Short sentences. Punchy. Like you're telling a friend.
- The hook MUST grab attention in the first 2 seconds
- Image prompts should be detailed, photorealistic, cinematic style
- Never use emojis or hashtags in narration
- The "twist" scene should reveal what sources disagree on or exaggerate
[/INST]"""

    log.info("Generating video script...")
    response = _call_hf_llm(prompt, max_tokens=1500)
    
    if not response:
        log.error("Failed to generate script")
        return None
    
    # Parse JSON scenes from response
    try:
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            scenes = json.loads(response[json_start:json_end])
            
            # Validate and clean
            valid_scenes = []
            for scene in scenes:
                if "narration" in scene and "image_prompt" in scene:
                    scene.setdefault("scene_type", "facts")
                    scene.setdefault("estimated_duration", 8)
                    # Ensure duration is a number
                    scene["estimated_duration"] = float(scene["estimated_duration"])
                    valid_scenes.append(scene)
            
            if valid_scenes:
                total_duration = sum(s["estimated_duration"] for s in valid_scenes)
                log.info(f"Script generated: {len(valid_scenes)} scenes, "
                         f"~{total_duration:.0f}s total")
                return valid_scenes
    except json.JSONDecodeError:
        log.warning("Failed to parse JSON from script response")
    
    # Fallback: create a basic script from the analysis
    log.warning("Using fallback script generation")
    return _fallback_script(analysis)


def _fallback_script(analysis: dict) -> list[dict]:
    """Generate a basic script without LLM if the API fails."""
    topic = analysis.get("topic_summary", "Breaking news")
    facts = analysis.get("consensus_facts", ["Details are still emerging."])
    
    scenes = [
        {
            "scene_type": "hook",
            "narration": f"You need to hear about this. {topic}",
            "image_prompt": f"Dramatic cinematic photo related to: {topic}. Dark moody lighting, photorealistic, 4K",
            "estimated_duration": 4.0,
        },
        {
            "scene_type": "facts",
            "narration": ". ".join(facts[:3]) if facts else "Here are the facts.",
            "image_prompt": f"News-style photo illustrating: {facts[0] if facts else topic}. Photorealistic, cinematic",
            "estimated_duration": 15.0,
        },
        {
            "scene_type": "kicker",
            "narration": "Stay informed. The truth matters.",
            "image_prompt": "Dramatic close-up of a newspaper headline, cinematic lighting, moody atmosphere",
            "estimated_duration": 4.0,
        },
    ]
    
    log.info(f"Fallback script: {len(scenes)} scenes")
    return scenes
