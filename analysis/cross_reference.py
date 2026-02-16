"""
Cross-Reference Engine — compares multiple sources on the same topic
to find consensus facts, disputed claims, and exaggerations.
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
    
    # Try primary model, then fallback
    models = [config.LLM_MODEL, config.LLM_FALLBACK]
    
    for model in models:
        url = f"{config.HF_API_BASE}/{model}"
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": 0.3,
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
                    # Model loading, wait and retry
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
        
        log.warning(f"All retries failed for {model}, trying fallback...")
    
    log.error("All LLM models failed")
    return None


def cross_reference_articles(articles: list[dict]) -> Optional[dict]:
    """
    Cross-reference multiple articles on the same topic.
    
    Returns a dict with:
      - topic_summary: one-line summary of the topic
      - consensus_facts: list of facts agreed upon by multiple sources
      - disputed_claims: claims only in some sources or conflicting
      - exaggerations: sensationalized language or unverified claims
      - key_details: important context or details
      - sources_used: list of source names
    """
    if not articles:
        return None
    
    # Build source summaries for the prompt
    source_texts = []
    for i, article in enumerate(articles[:8]):  # Cap at 8 to fit context
        source_name = article.get("source_name", f"Source {i+1}")
        title = article.get("title", "")
        text = article.get("full_text", article.get("summary", ""))
        # Truncate long articles
        if len(text) > 1500:
            text = text[:1500] + "..."
        source_texts.append(f"[{source_name}] {title}\n{text}")
    
    all_sources = "\n\n---\n\n".join(source_texts)
    source_names = [a.get("source_name", "Unknown") for a in articles[:8]]
    
    prompt = f"""<s>[INST] You are a meticulous fact-checking journalist. Analyze these {len(source_texts)} news articles covering the SAME story from different sources. Your job is to find the TRUTH.

ARTICLES:
{all_sources}

Respond in EXACTLY this JSON format, nothing else:
{{
  "topic_summary": "One clear sentence describing what happened",
  "consensus_facts": ["Fact agreed by 3+ sources", "Another agreed fact"],
  "disputed_claims": ["Claim only in 1-2 sources or conflicting info"],
  "exaggerations": ["Sensationalized or unverified claims"],
  "key_details": ["Important context some sources omit"],
  "severity": "high/medium/low"
}}

Rules:
- consensus_facts: ONLY include things stated by AT LEAST 2 different sources
- disputed_claims: things where sources DISAGREE or only ONE source mentions
- exaggerations: language that's clearly sensationalized vs neutral reporting
- Be specific, cite which sources when noting disputes
- severity: how newsworthy is this? high=breaking, medium=notable, low=minor
[/INST]"""

    log.info(f"Cross-referencing {len(source_texts)} sources...")
    response = _call_hf_llm(prompt, max_tokens=1500)
    
    if not response:
        log.error("Failed to get cross-reference analysis")
        return None
    
    # Parse JSON from response
    try:
        # Try to extract JSON from the response
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            analysis = json.loads(response[json_start:json_end])
            analysis["sources_used"] = source_names
            log.info(f"Analysis complete: {len(analysis.get('consensus_facts', []))} consensus facts, "
                     f"{len(analysis.get('disputed_claims', []))} disputes")
            return analysis
    except json.JSONDecodeError:
        log.warning("Failed to parse JSON from LLM response, using raw text")
    
    # Fallback: return raw text as analysis
    return {
        "topic_summary": articles[0].get("title", "Unknown topic"),
        "consensus_facts": [response[:500]],
        "disputed_claims": [],
        "exaggerations": [],
        "key_details": [],
        "sources_used": source_names,
        "severity": "medium",
        "raw_analysis": response,
    }
