"""
Script Generator v2 — uses Kimi K2.5 (with fallbacks) to generate
punchy short-form video scripts. Supports both fresh and follow-up videos.
"""

import json
import re
from typing import Optional

import config
from utils.logger import log
from utils.hf_client import call_hf_llm


# ─── System Prompts ────────────────────────────────────────

SYSTEM_PROMPT_FRESH = """You are Lens AI, a viral short-form news video scripter. You write scripts for 30-45 second vertical videos (YouTube Shorts / Instagram Reels). Your scripts must be:

STYLE RULES:
- **RAPID FIRE PACING**: Scenes must be SHORT (2-5 seconds). speed is key.
- Open with a HOOK that stops the scroll (question, shocking stat, bold claim)
- Every sentence must earn its place — no filler, no fluff
- Use conversational, slightly dramatic tone (like you're telling a friend something wild)
- End with a KICKER that makes viewers want to share or comment
- NO hashtags, NO "like and subscribe", NO emojis in the narration text
- Write for SPOKEN delivery — short sentences, natural pauses
- **Aim for 8-12 scenes** for a 40s video.

EFFECTS & MEDIA:
- `audio_effect`: Choose ONE from ["whoosh", "boom", "ding", "camera_shutter", "glitch", "none"] per scene. Use "whoosh" for transitions, "boom" for impact, "camera_shutter" for photos.
- `visual_effect`: Choose ONE from ["zoom_fast", "zoom_slow", "pan_left", "pan_right", "shake", "flash", "none"].
- `image_prompt`: Detailed, cinematic, vertical 9:16.

IMAGE PROMPT RULES:
- Write detailed, cinematic prompts for FLUX/Stable Diffusion AI image generation
- Describe visual composition, lighting, mood, colors specifically
- NEVER include text, words, logos, or watermarks in image prompts
- Focus on symbolic/metaphorical visuals when showing people could be inaccurate
- Always specify "photorealistic, 9:16 vertical format, cinematic" in prompts"""

SYSTEM_PROMPT_FOLLOWUP = """You are Lens AI, a viral short-form news video scripter creating a FOLLOW-UP video on a developing story. Viewers may have seen the original coverage.

FOLLOW-UP RULES:
- **RAPID FIRE PACING**: Scenes must be SHORT (2-5 seconds).
- Open with "Remember [brief recap]? Here's what just happened..."
- Highlight what CHANGED since the last video
- Compare new info vs what was previously known
- If the story evolved, explain the twist
- End with forward-looking speculation or what to watch for next
- Keep it under 45 seconds — viewers know the backstory
- **Aim for 8-12 scenes** for a 40s video.

EFFECTS & MEDIA:
- `audio_effect`: ["whoosh", "boom", "ding", "camera_shutter", "glitch", "none"].
- `visual_effect`: ["zoom_fast", "zoom_slow", "pan_left", "pan_right", "shake", "flash", "none"].

IMAGE PROMPT RULES:
- Write detailed, cinematic prompts for FLUX/Stable Diffusion AI image generation
- For follow-ups, use visual cues suggesting "update" or "progression" (e.g., timelines, split screens conceptually)
- NEVER include text, words, logos, or watermarks in image prompts
- Always specify "photorealistic, 9:16 vertical format, cinematic" in prompts"""


def _build_script_prompt(analysis: dict) -> str:
    """Build the script generation prompt from analysis results."""
    topic = analysis.get("topic_summary", "Breaking news story")
    facts = analysis.get("consensus_facts", [])
    disputes = analysis.get("disputed_claims", [])
    exaggerations = analysis.get("exaggerations", [])
    key_data = analysis.get("key_data", {})
    severity = analysis.get("severity", "medium")
    
    prompt = f"""Generate a script for a 30-45 second news video about:
"{topic}"

VERIFIED FACTS:
{chr(10).join(f"- {f}" for f in facts[:6]) if facts else "- Limited verified information available"}

KEY DETAILS:
- Who: {key_data.get('who', 'Unknown')}
- What: {key_data.get('what', topic)}
- Where: {key_data.get('where', 'Not specified')}
- When: {key_data.get('when', 'Recent')}
- Impact: {key_data.get('impact', 'Under investigation')}

{f"DISPUTED CLAIMS (mention cautiously):{chr(10)}" + chr(10).join(f"- {d.get('claim', d) if isinstance(d, dict) else d}" for d in disputes[:3]) if disputes else ""}

{f"EXAGGERATIONS TO AVOID:{chr(10)}" + chr(10).join(f"- {e.get('original', e) if isinstance(e, dict) else e}" for e in exaggerations[:3]) if exaggerations else ""}

Story severity: {severity}

Respond with ONLY a JSON array of 8-12 scenes:
[
  {{
    "scene_number": 1,
    "scene_type": "hook",
    "narration": "The exact words to speak (2-5 seconds worth)",
    "image_prompt": "Detailed cinematic image prompt...",
    "audio_effect": "whoosh|boom|ding|camera_shutter|glitch|none",
    "visual_effect": "zoom_fast|shake|flash|none",
    "estimated_duration": 4
  }}
]"""
    
    return prompt


def _build_followup_prompt(analysis: dict, historical_context: dict) -> str:
    """Build a follow-up script prompt with historical context."""
    topic = analysis.get("topic_summary", "Developing story")
    facts = analysis.get("consensus_facts", [])
    
    prev_title = historical_context.get("title", "")
    prev_analysis = historical_context.get("analysis", {})
    prev_facts = prev_analysis.get("consensus_facts", [])
    prev_summary = prev_analysis.get("topic_summary", prev_title)
    
    prompt = f"""Generate a FOLLOW-UP script for a developing news story.

PREVIOUS COVERAGE:
Topic: {prev_summary}
Previously known facts:
{chr(10).join(f"- {f}" for f in prev_facts[:4]) if prev_facts else "- Original story was covered earlier"}

NEW DEVELOPMENTS:
Topic: {topic}
New information:
{chr(10).join(f"- {f}" for f in facts[:6]) if facts else "- Story is still developing"}

Respond with ONLY a JSON array of 8-12 scenes:
[
  {{
    "scene_number": 1,
    "scene_type": "recap",
    "narration": "The exact words to speak (2-5 seconds worth)",
    "image_prompt": "Detailed cinematic image prompt...",
    "audio_effect": "whoosh|boom|ding|camera_shutter|glitch|none",
    "visual_effect": "zoom_fast|shake|flash|none",
    "estimated_duration": 4
  }}
]

IMPORTANT: Scene 1 must briefly recap the original story. Scene 2+ reveals what changed."""
    
    return prompt


def generate_script(analysis: dict, 
                    historical_context: Optional[dict] = None) -> Optional[list[dict]]:
    """
    Generate a video script from analysis results.
    
    Args:
        analysis: cross-reference analysis output
        historical_context: if provided, generates a follow-up script
    
    Returns:
        List of scene dicts, or None on failure.
    """
    if not analysis:
        log.error("No analysis provided for script generation")
        return None
    
    is_followup = historical_context is not None
    
    if is_followup:
        prompt = _build_followup_prompt(analysis, historical_context)
        system = SYSTEM_PROMPT_FOLLOWUP
        log.info("Generating FOLLOW-UP video script...")
    else:
        prompt = _build_script_prompt(analysis)
        system = SYSTEM_PROMPT_FRESH
        log.info("Generating fresh video script...")
    
    response = call_hf_llm(prompt, max_tokens=2000, temperature=0.4,
                           system_prompt=system)
    
    if not response:
        log.warning("LLM returned no response, using fallback script")
        return _fallback_script(analysis, is_followup)
    
    # Parse scenes from response
    scenes = _parse_scenes(response)
    
    if not scenes:
        log.warning("Could not parse scenes from LLM response, using fallback")
        return _fallback_script(analysis, is_followup)
    
    # Validate and clean scenes
    valid_scenes = _validate_scenes(scenes)
    
    if not valid_scenes:
        log.warning("No valid scenes after validation, using fallback")
        return _fallback_script(analysis, is_followup)
    
    log.info(f"Script generated: {len(valid_scenes)} scenes, "
             f"~{sum(s.get('estimated_duration', 7) for s in valid_scenes)}s total")
    
    return valid_scenes


def _parse_scenes(response: str) -> Optional[list[dict]]:
    """Extract scene array from LLM response."""
    # Try direct parse
    try:
        result = json.loads(response)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON array from response
    patterns = [
        r'```json\s*\n?(\[[\s\S]*?\])\n?```',
        r'```\s*\n?(\[[\s\S]*?\])\n?```',
        r'(\[[\s\S]*\])',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                continue
    
    return None


def _validate_scenes(scenes: list[dict]) -> list[dict]:
    """Validate and clean scene data."""
    valid = []
    for scene in scenes[:config.MAX_SCENES]:
        narration = scene.get("narration", "").strip()
        if not narration:
            continue
        
        # Ensure required fields
        clean_scene = {
            "scene_number": scene.get("scene_number", len(valid) + 1),
            "scene_type": scene.get("scene_type", "context"),
            "narration": narration,
            "image_prompt": scene.get("image_prompt", 
                f"Cinematic news visual depicting: {narration[:100]}. "
                "Photorealistic, dramatic lighting, 9:16 vertical, editorial quality"),
            "audio_effect": scene.get("audio_effect", "none"),
            "visual_effect": scene.get("visual_effect", "none"),
            "estimated_duration": min(max(scene.get("estimated_duration", 3), 2), 8),
        }
        valid.append(clean_scene)
    
    return valid


def _fallback_script(analysis: dict, is_followup: bool = False) -> list[dict]:
    """Generate a basic script when LLM fails."""
    topic = analysis.get("topic_summary", "Breaking news story")
    facts = analysis.get("consensus_facts", [])
    sources = analysis.get("sources", ["multiple sources"])
    severity = analysis.get("severity", "medium")
    key_data = analysis.get("key_data", {})
    
    if is_followup:
        hook = f"The story about {topic} just took a new turn."
    else:
        hook = f"Breaking: {topic}. Here's what we know so far."
    
    scenes = [
        {
            "scene_number": 1,
            "scene_type": "hook",
            "narration": hook,
            "image_prompt": (f"Dramatic breaking news scene with urgent atmosphere. "
                f"Abstract representation of {topic[:50]}. "
                "Dark moody background with spotlight, photorealistic, "
                "9:16 vertical format, cinematic lighting, editorial quality"),
            "estimated_duration": 6,
        },
        {
            "scene_number": 2,
            "scene_type": "context",
            "narration": f"According to {', '.join(sources[:2])}, {facts[0] if facts else 'this story is still developing'}.",
            "image_prompt": (f"Professional newsroom environment showing investigation and reporting. "
                "Multiple screens displaying data analysis, photorealistic, "
                "9:16 vertical format, cinematic lighting, blue-toned"),
            "estimated_duration": 8,
        },
        {
            "scene_number": 3,
            "scene_type": "facts",
            "narration": facts[1] if len(facts) > 1 else f"The impact is expected to be {severity}.",
            "image_prompt": (f"Visual metaphor for impact and consequence in context of {topic[:40]}. "
                "Dramatic composition with strong contrast, photorealistic, "
                "9:16 vertical format, golden hour lighting"),
            "estimated_duration": 7,
        },
        {
            "scene_number": 4,
            "scene_type": "kicker",
            "narration": "We'll keep tracking this story. Follow for the next update.",
            "image_prompt": ("Futuristic lens or eye symbolizing watchful journalism and truth-seeking. "
                "Clean dark background with glowing elements, photorealistic, "
                "9:16 vertical format, dramatic rim lighting"),
            "estimated_duration": 5,
        },
    ]
    
    return scenes
