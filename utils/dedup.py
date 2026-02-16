"""
SQLite-based topic deduplication.
Stores embeddings of previously covered topics to prevent re-processing.
"""

import sqlite3
import hashlib
import json
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from utils.logger import log


class DedupDB:
    """Manages SQLite database for topic deduplication."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DB_PATH
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS covered_topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    centroid_hash TEXT NOT NULL,
                    centroid_embedding TEXT NOT NULL,
                    representative_title TEXT NOT NULL,
                    article_count INTEGER DEFAULT 0,
                    source_names TEXT DEFAULT '',
                    video_path TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_urls (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_centroid_hash 
                ON covered_topics(centroid_hash)
            """)
            conn.commit()
        log.info(f"Dedup DB initialized at {self.db_path}")
    
    def _embedding_to_json(self, embedding: np.ndarray) -> str:
        """Convert numpy embedding to JSON string for storage."""
        return json.dumps(embedding.tolist())
    
    def _json_to_embedding(self, json_str: str) -> np.ndarray:
        """Convert JSON string back to numpy embedding."""
        return np.array(json.loads(json_str))
    
    def _hash_embedding(self, embedding: np.ndarray) -> str:
        """Create a hash from an embedding for quick lookup."""
        raw = embedding.tobytes()
        return hashlib.sha256(raw).hexdigest()[:16]
    
    def is_topic_covered(self, centroid_embedding: np.ndarray, threshold: float = None) -> bool:
        """
        Check if a topic (represented by its centroid embedding) has already been covered.
        Uses cosine similarity against all stored centroids.
        """
        threshold = threshold or config.DEDUP_SIMILARITY_THRESHOLD
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT centroid_embedding FROM covered_topics"
            ).fetchall()
        
        if not rows:
            return False
        
        for row in rows:
            stored_embedding = self._json_to_embedding(row[0])
            similarity = self._cosine_similarity(centroid_embedding, stored_embedding)
            if similarity >= threshold:
                log.debug(f"Topic already covered (similarity={similarity:.3f})")
                return True
        
        return False
    
    def mark_topic_covered(
        self,
        centroid_embedding: np.ndarray,
        representative_title: str,
        article_count: int = 0,
        source_names: str = "",
        video_path: str = ""
    ):
        """Record a topic as covered."""
        centroid_hash = self._hash_embedding(centroid_embedding)
        centroid_json = self._embedding_to_json(centroid_embedding)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO covered_topics 
                   (centroid_hash, centroid_embedding, representative_title, 
                    article_count, source_names, video_path)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (centroid_hash, centroid_json, representative_title,
                 article_count, source_names, video_path)
            )
            conn.commit()
        
        log.info(f"Marked topic as covered: '{representative_title}' ({article_count} articles)")
    
    def is_url_processed(self, url: str) -> bool:
        """Check if an article URL has already been processed."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_urls WHERE url_hash = ?",
                (url_hash,)
            ).fetchone()
        
        return row is not None
    
    def mark_url_processed(self, url: str, source: str = ""):
        """Record a URL as processed."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_urls (url_hash, url, source) VALUES (?, ?, ?)",
                (url_hash, url, source)
            )
            conn.commit()
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            topic_count = conn.execute("SELECT COUNT(*) FROM covered_topics").fetchone()[0]
            url_count = conn.execute("SELECT COUNT(*) FROM processed_urls").fetchone()[0]
        
        return {"topics_covered": topic_count, "urls_processed": url_count}
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
