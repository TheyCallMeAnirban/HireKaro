"""
embedder.py — Text embedding generation and cosine similarity.

Uses Gemini text-embedding-004 (API) with a TF-IDF keyword fallback
so the system works even without an API key.
"""
import os
import math
import numpy as np
from config import get_logger

log = get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIM   = 768

# Tech vocabulary for the keyword-frequency fallback
_VOCAB = [
    "python","java","javascript","typescript","go","rust","c++","scala",
    "react","angular","vue","node","fastapi","django","flask","spring",
    "sql","postgresql","mysql","mongodb","redis","elasticsearch","kafka",
    "aws","gcp","azure","docker","kubernetes","terraform","ci/cd","linux",
    "machine learning","pytorch","tensorflow","pandas","spark","airflow",
    "graphql","grpc","microservices","backend","frontend","fullstack",
    "devops","security","data","ml","ai","llm","senior","lead","principal",
]


def get_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Generate a text embedding.
    task_type: "RETRIEVAL_DOCUMENT" for candidates, "RETRIEVAL_QUERY" for JDs.
    Falls back to keyword-frequency vector if API is unavailable.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return _keyword_fallback(text)
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config={"task_type": task_type},
        )
        vec = list(response.embeddings[0].values)
        log.info("embedder.success", extra={"dim": len(vec), "task": task_type})
        return vec
    except Exception as e:
        log.warning("embedder.api_failed", extra={"error": str(e), "type": type(e).__name__, "fallback": True})
        return _keyword_fallback(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [0, 1]. Returns 0.5 on zero vectors (neutral)."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na < 1e-8 or nb < 1e-8:
        return 0.5
    # Map from [-1,1] → [0,1]
    return float((np.dot(va, vb) / (na * nb) + 1) / 2)


def build_candidate_text(candidate: dict) -> str:
    """Concatenate candidate fields into a single embedding input string."""
    return (
        f"{candidate.get('current_role', '')} "
        f"{candidate.get('domain', '')} "
        f"{' '.join(candidate.get('skills', []))} "
        f"{candidate.get('project', '')}"
    )


def build_jd_text(parsed_jd: dict, raw_jd: str = "") -> str:
    """Concatenate JD fields into a query embedding string."""
    return (
        f"{parsed_jd.get('role', '')} "
        f"{parsed_jd.get('seniority', '')} "
        f"{parsed_jd.get('domain', '')} "
        f"{' '.join(parsed_jd.get('required_skills', []))} "
        f"{' '.join(parsed_jd.get('secondary_skills', []))} "
        f"{raw_jd[:400]}"
    )


def _keyword_fallback(text: str) -> list[float]:
    """Sparse keyword-presence vector, L2-normalised, padded to EMBEDDING_DIM."""
    t = text.lower()
    vec = [1.0 if term in t else 0.0 for term in _VOCAB]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    normalised = [v / norm for v in vec]
    return (normalised + [0.0] * EMBEDDING_DIM)[:EMBEDDING_DIM]
