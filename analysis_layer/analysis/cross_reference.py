"""
Cross-Reference Engine v2 — uses Kimi K2.5 (with fallbacks) to analyze
articles from multiple sources on the same topic. Identifies consensus facts,
disputed claims, exaggerations, and key data points.
"""

import json
import re
from typing import Optional

import config
from utils.logger import log
from utils.hf_client import call_hf_llm


# ─── System Prompt ─────────────────────────────────────────
SYSTEM_PROMPT = """You are Lens AI, an elite investigative journalist AI. Your job is to cross-reference multiple news articles about the same story and produce a rigorous factual analysis.

RULES:
1. ONLY state facts that appear in 2+ independent sources
2. Flag claims that appear in only 1 source as "unverified"  
3. Identify sensationalized language and rate its severity
4. Note contradictions between sources explicitly
5. Assign an overall severity: "low" (lifestyle/entertainment), "medium" (politics/economy), "high" (crisis/conflict/disaster)
6. Be specific with numbers, names, dates — never vague generalizations
7. Always output valid JSON, nothing else"""


def _build_analysis_prompt(articles: list[dict]) -> str:
    """Build the analysis prompt from a list of articles."""
    articles_text = ""
    for i, article in enumerate(articles[:8]):  # Cap at 8 articles
        source = article.get("source", "Unknown")
        title = article.get("title", "No title")
        text = article.get("text", article.get("summary", ""))[:2000]
        articles_text += f"\n--- SOURCE {i+1}: {source} ---\nTitle: {title}\n{text}\n"
    
    prompt = f"""Analyze these {len(articles)} news articles about the same topic. Cross-reference them for accuracy.

{articles_text}

Respond with ONLY this JSON structure:
{{
  "topic_summary": "One clear sentence describing what happened",
  "severity": "low|medium|high",
  "consensus_facts": [
    "Fact confirmed by multiple sources (cite which sources agree)"
  ],
  "disputed_claims": [
    {{"claim": "What was claimed", "source": "Who said it", "issue": "Why it's disputed"}}
  ],
  "exaggerations": [
    {{"original": "The sensationalized claim", "reality": "What the evidence actually shows", "severity": "mild|moderate|severe"}}
  ],
  "key_data": {{
    "who": ["Key people/organizations involved"],
    "what": "Core event in one sentence",
    "where": "Location(s)",
    "when": "Time/date",
    "impact": "Who is affected and how"
  }},
  "source_reliability_notes": "Any notable differences in how sources covered this"
}}"""
    
    return prompt


def cross_reference_articles(articles: list[dict]) -> Optional[dict]:
    """
    Cross-reference multiple articles about the same topic.
    
    Returns a structured analysis dict, or None on failure.
    """
    if not articles:
        log.warning("No articles to cross-reference")
        return None
    
    if len(articles) == 1:
        log.warning("Only 1 article — limited cross-referencing possible")
    
    prompt = _build_analysis_prompt(articles)
    
    log.info(f"Cross-referencing {len(articles)} articles...")
    response = call_hf_llm(prompt, max_tokens=2000, temperature=0.1, 
                           system_prompt=SYSTEM_PROMPT)
    
    if not response:
        log.error("LLM returned no response for cross-reference")
        return _fallback_analysis(articles)
    
    # Parse JSON from response
    analysis = _parse_json_response(response)
    
    if analysis:
        # Enrich with metadata
        analysis["article_count"] = len(articles)
        analysis["sources"] = list(set(a.get("source", "Unknown") for a in articles))
        log.info(f"Analysis complete: severity={analysis.get('severity', '?')}, "
                 f"{len(analysis.get('consensus_facts', []))} facts, "
                 f"{len(analysis.get('disputed_claims', []))} disputes")
        return analysis
    
    log.warning("Could not parse LLM response, using fallback analysis")
    return _fallback_analysis(articles)


def _parse_json_response(response: str) -> Optional[dict]:
    """Extract and parse JSON from LLM response, handling common issues."""
    # Try direct parse first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON from markdown code blocks
    patterns = [
        r'```json\s*\n?(.*?)\n?```',
        r'```\s*\n?(.*?)\n?```',
        r'\{[\s\S]*\}',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    return None


def _fallback_analysis(articles: list[dict]) -> dict:
    """Generate a basic analysis when LLM fails."""
    titles = [a.get("title", "") for a in articles]
    sources = list(set(a.get("source", "Unknown") for a in articles))
    main_title = max(titles, key=len) if titles else "Unknown topic"
    
    # Extract common words from titles for topic summary
    all_words = " ".join(titles).lower().split()
    word_freq = {}
    for w in all_words:
        if len(w) > 3:
            word_freq[w] = word_freq.get(w, 0) + 1
    common_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "topic_summary": main_title,
        "severity": "medium",
        "consensus_facts": [
            f"Multiple sources ({', '.join(sources[:3])}) are reporting on this story",
            f"The story involves: {', '.join(w[0] for w in common_words[:3])}",
        ],
        "disputed_claims": [],
        "exaggerations": [],
        "key_data": {
            "who": sources,
            "what": main_title,
            "where": "Not specified",
            "when": "Recent",
            "impact": "Under investigation",
        },
        "source_reliability_notes": "Fallback analysis — LLM unavailable",
        "article_count": len(articles),
        "sources": sources,
    }
