"""
Topic History — tracks past topics and their analyses for follow-up video generation.
Enables the system to create "update" or "follow-up" videos on developing stories.
"""

import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import config
from utils.logger import log


class TopicHistory:
    """Manages historical topic tracking for follow-up video generation."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DB_PATH
        self._init_tables()
    
    def _init_tables(self):
        """Create history tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topic_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_title TEXT NOT NULL,
                    topic_summary TEXT DEFAULT '',
                    consensus_facts TEXT DEFAULT '[]',
                    disputed_claims TEXT DEFAULT '[]',
                    centroid_embedding TEXT NOT NULL,
                    article_count INTEGER DEFAULT 0,
                    source_names TEXT DEFAULT '',
                    video_count INTEGER DEFAULT 1,
                    severity TEXT DEFAULT 'medium',
                    first_covered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_developing INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS followup_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_history_id INTEGER NOT NULL,
                    video_path TEXT DEFAULT '',
                    new_developments TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (topic_history_id) REFERENCES topic_history(id)
                )
            """)
            conn.commit()
    
    def save_topic(self, topic_title: str, analysis: dict,
                   centroid_embedding: np.ndarray, article_count: int = 0,
                   source_names: str = "") -> int:
        """
        Save a newly covered topic to history.
        Returns the topic history ID.
        """
        centroid_json = json.dumps(centroid_embedding.tolist())
        consensus = json.dumps(analysis.get("consensus_facts", []))
        disputed = json.dumps(analysis.get("disputed_claims", []))
        summary = analysis.get("topic_summary", "")
        severity = analysis.get("severity", "medium")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO topic_history 
                   (topic_title, topic_summary, consensus_facts, disputed_claims,
                    centroid_embedding, article_count, source_names, severity, is_developing)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (topic_title, summary, consensus, disputed, centroid_json,
                 article_count, source_names, severity,
                 1 if severity == "high" else 0)
            )
            conn.commit()
            topic_id = cursor.lastrowid
        
        # Also save the analysis JSON to disk for rich context
        history_file = config.HISTORY_DIR / f"topic_{topic_id}.json"
        with open(history_file, "w") as f:
            json.dump({
                "id": topic_id,
                "title": topic_title,
                "analysis": analysis,
                "article_count": article_count,
                "source_names": source_names,
                "covered_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
        
        log.info(f"Saved topic to history: #{topic_id} '{topic_title[:60]}'")
        return topic_id
    
    def find_followup_candidates(self, current_clusters: list[dict]) -> list[dict]:
        """
        Find topics from history that have new developments worth a follow-up video.
        
        Compares current news clusters against historical topics.
        A follow-up is triggered when:
          1. A current cluster is similar to a past topic (but not exact duplicate)
          2. The past topic was covered >6 hours ago but <72 hours ago
          3. The new cluster contains articles not yet processed
        
        Returns list of dicts with 'historical_topic', 'new_cluster', 'similarity'.
        """
        if not config.ENABLE_FOLLOWUPS:
            return []
        
        now = datetime.now(timezone.utc)
        min_age = now - timedelta(hours=config.FOLLOWUP_MIN_AGE_HOURS)
        max_age = now - timedelta(hours=config.FOLLOWUP_MAX_AGE_HOURS)
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, topic_title, topic_summary, consensus_facts,
                          disputed_claims, centroid_embedding, last_updated_at,
                          video_count, severity
                   FROM topic_history
                   WHERE last_updated_at < ? AND last_updated_at > ?
                   ORDER BY last_updated_at DESC""",
                (min_age.isoformat(), max_age.isoformat())
            ).fetchall()
        
        if not rows:
            return []
        
        candidates = []
        
        for row in rows:
            hist_id, title, summary, consensus_json, disputed_json, \
                centroid_json, last_updated, video_count, severity = row
            
            historical_embedding = np.array(json.loads(centroid_json))
            
            for cluster in current_clusters:
                cluster_centroid = cluster.get("centroid")
                if cluster_centroid is None:
                    continue
                
                similarity = self._cosine_similarity(historical_embedding, cluster_centroid)
                
                # Check if it's related but NOT identical
                if (config.FOLLOWUP_SIMILARITY_THRESHOLD <= similarity < 
                    config.DEDUP_SIMILARITY_THRESHOLD):
                    
                    candidates.append({
                        "historical_topic": {
                            "id": hist_id,
                            "title": title,
                            "summary": summary,
                            "consensus_facts": json.loads(consensus_json),
                            "disputed_claims": json.loads(disputed_json),
                            "video_count": video_count,
                            "severity": severity,
                            "last_updated": last_updated,
                        },
                        "new_cluster": cluster,
                        "similarity": similarity,
                    })
        
        # Sort by similarity (most related first), cap at max
        candidates.sort(key=lambda c: c["similarity"], reverse=True)
        candidates = candidates[:config.MAX_FOLLOWUPS_PER_CYCLE]
        
        if candidates:
            log.info(f"Found {len(candidates)} follow-up candidates:")
            for c in candidates:
                log.info(f"  📰 '{c['historical_topic']['title'][:50]}' "
                         f"(sim={c['similarity']:.3f}, "
                         f"prev videos={c['historical_topic']['video_count']})")
        
        return candidates
    
    def record_followup(self, topic_history_id: int, video_path: str,
                        new_developments: str = "") -> None:
        """Record a follow-up video for a historical topic."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO followup_log (topic_history_id, video_path, new_developments)
                   VALUES (?, ?, ?)""",
                (topic_history_id, video_path, new_developments)
            )
            conn.execute(
                """UPDATE topic_history 
                   SET video_count = video_count + 1, 
                       last_updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (topic_history_id,)
            )
            conn.commit()
        
        log.info(f"Recorded follow-up for topic #{topic_history_id}")
    
    def get_topic_context(self, topic_history_id: int) -> Optional[dict]:
        """Get full context for a historical topic (for follow-up script generation)."""
        # Try loading from disk first (richer context)
        history_file = config.HISTORY_DIR / f"topic_{topic_history_id}.json"
        if history_file.exists():
            with open(history_file) as f:
                return json.load(f)
        
        # Fallback to DB
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT topic_title, topic_summary, consensus_facts, disputed_claims
                   FROM topic_history WHERE id = ?""",
                (topic_history_id,)
            ).fetchone()
        
        if row:
            return {
                "title": row[0],
                "summary": row[1],
                "consensus_facts": json.loads(row[2]),
                "disputed_claims": json.loads(row[3]),
            }
        
        return None
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
