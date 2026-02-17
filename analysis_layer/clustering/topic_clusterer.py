"""
Topic Clusterer — groups articles about the same story using sentence embeddings.
"""

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sentence_transformers import SentenceTransformer

import config
from utils.logger import log

# Load embedding model (runs locally, no API cost)
_model = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        log.info(f"Loading embedding model: {config.EMBEDDING_MODEL}...")
        _model = SentenceTransformer(config.EMBEDDING_MODEL)
        log.info("Embedding model loaded.")
    return _model


def cluster_articles(articles: list[dict]) -> list[dict]:
    """
    Cluster articles by topic similarity.
    
    Each article should have 'title' and 'summary' fields.
    Returns a list of topic clusters, each containing:
      - 'articles': list of articles in this cluster
      - 'centroid': centroid embedding of the cluster
      - 'representative_title': title of the most central article
      - 'article_count': number of articles
      - 'source_names': comma-separated list of unique sources
    """
    if not articles:
        return []
    
    model = _get_model()
    
    # Create text representations for embedding
    texts = [
        f"{a['title']}. {a.get('summary', '')[:200]}"
        for a in articles
    ]
    
    log.info(f"Embedding {len(texts)} articles for clustering...")
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=64)
    embeddings = np.array(embeddings)
    
    if len(articles) == 1:
        return [_make_cluster(articles, embeddings, [0])]
    
    # Agglomerative clustering with distance threshold
    # Convert similarity threshold to distance threshold
    distance_threshold = 1 - config.CLUSTER_SIMILARITY_THRESHOLD
    
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage="average",
    )
    
    labels = clustering.fit_predict(embeddings)
    n_clusters = len(set(labels))
    
    log.info(f"Found {n_clusters} topic clusters from {len(articles)} articles")
    
    # Group articles by cluster
    clusters = []
    for cluster_id in range(n_clusters):
        indices = [i for i, label in enumerate(labels) if label == cluster_id]
        cluster = _make_cluster(articles, embeddings, indices)
        clusters.append(cluster)
    
    # Sort by article count (most-covered stories first)
    clusters.sort(key=lambda c: c["article_count"], reverse=True)
    
    return clusters


def _make_cluster(articles: list[dict], embeddings: np.ndarray, indices: list[int]) -> dict:
    """Create a cluster dict from articles and their indices."""
    cluster_articles = [articles[i] for i in indices]
    cluster_embeddings = embeddings[indices]
    
    # Compute centroid
    centroid = np.mean(cluster_embeddings, axis=0)
    
    # Find the article closest to centroid (most representative)
    distances = [
        np.dot(centroid, cluster_embeddings[i]) / (
            np.linalg.norm(centroid) * np.linalg.norm(cluster_embeddings[i])
        )
        for i in range(len(cluster_embeddings))
    ]
    most_central_idx = np.argmax(distances)
    
    # Get unique source names
    source_names = list(set(a["source_name"] for a in cluster_articles))
    
    return {
        "articles": cluster_articles,
        "centroid": centroid,
        "representative_title": cluster_articles[most_central_idx]["title"],
        "article_count": len(cluster_articles),
        "source_names": ", ".join(source_names),
    }


def filter_single_source_topics(clusters: list[dict]) -> list[dict]:
    """
    Filter out topics that only have articles from a single source.
    We need multiple sources to cross-reference and fact-check.
    """
    min_articles = config.MIN_ARTICLES_PER_TOPIC
    
    filtered = [
        c for c in clusters
        if c["article_count"] >= min_articles
    ]
    
    removed = len(clusters) - len(filtered)
    if removed:
        log.info(f"Filtered out {removed} single-source topics (need >= {min_articles} articles)")
    
    return filtered
