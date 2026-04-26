"""
matcher.py — Deterministic candidate scoring. Zero LLM calls.

New 4-component formula:
  40%  Embedding similarity  (semantic match via cosine similarity)
  30%  Skill overlap         (exact + substring matching)
  20%  Experience alignment  (years vs seniority requirement)
  10%  Project relevance     (keyword hits in project description)
"""
from typing import Dict, Any
from embedder import cosine_similarity

_SENIORITY_YEARS = {
    "junior":    1,
    "mid":       3,
    "senior":    5,
    "lead":      7,
    "principal": 10,
    "staff":     8,
}


def calculate_match_score(
    candidate:     Dict[str, Any],
    parsed_jd:     Dict[str, Any],
    jd_embedding:  list[float] | None = None,
) -> Dict[str, Any]:
    """
    Score a candidate against a parsed JD.

    Args:
        candidate:    Candidate dict. Must include 'embedding' for semantic scoring.
        parsed_jd:    Structured JD (role, skills, domain, seniority).
        jd_embedding: Precomputed JD embedding vector. If None, component is neutral.

    Returns dict with: score, matched_skills, secondary_matched, missing_skills,
                       explanation, components
    """

    # ── 1. Embedding Similarity (40 pts) ──────────────────────────────────────
    cand_emb = candidate.get("embedding")
    if jd_embedding and cand_emb:
        sim = cosine_similarity(jd_embedding, cand_emb)   # 0.0 → 1.0
        embedding_score = sim * 40.0
    else:
        embedding_score = 20.0   # neutral mid-point when embeddings unavailable

    # ── 2. Skill Overlap (30 pts) ─────────────────────────────────────────────
    required   = [s.lower() for s in parsed_jd.get("required_skills",  [])]
    secondary  = [s.lower() for s in parsed_jd.get("secondary_skills", [])]
    candidate_skills = [s.lower() for s in candidate.get("skills", [])]

    def _matches(cand: str, targets: list) -> bool:
        return any(cand == t or t in cand or cand in t for t in targets)

    matched_skills    = [s for s in candidate_skills if _matches(s, required)]
    missing_skills    = [r for r in required if not any(_matches(c, [r]) for c in candidate_skills)]
    secondary_matched = [s for s in candidate_skills
                         if _matches(s, secondary) and not _matches(s, required)]

    skill_score = (len(matched_skills) / len(required) * 30.0) if required else 15.0

    # ── 3. Experience Alignment (20 pts) ──────────────────────────────────────
    req_years  = _SENIORITY_YEARS.get(parsed_jd.get("seniority", "mid").lower(), 3)
    cand_years = candidate.get("years_experience", 0)

    if cand_years >= req_years:
        # Slight bonus for overqualified, capped at 20
        exp_score = min(20.0, 20.0 + (cand_years - req_years) * 0.4)
    else:
        exp_score = max(0.0, (cand_years / req_years) * 20.0)

    # ── 4. Project Relevance (10 pts) ─────────────────────────────────────────
    project = candidate.get("project", "").lower()
    keywords = required + [parsed_jd.get("domain", "").lower()]
    hits = sum(1 for k in keywords if k and k in project)
    proj_score = min(10.0, hits * 3.5) if hits else (2.0 if project else 0.0)

    # ── Total ──────────────────────────────────────────────────────────────────
    total = embedding_score + skill_score + exp_score + proj_score

    return {
        "score":             round(total, 1),
        "matched_skills":    matched_skills,
        "secondary_matched": secondary_matched,
        "missing_skills":    missing_skills,
        "explanation": (
            f"Embedding: {embedding_score:.1f}/40 | "
            f"Skills: {skill_score:.1f}/30 ({len(matched_skills)}/{len(required)}) | "
            f"Exp: {exp_score:.1f}/20 ({cand_years}yr vs {req_years}yr) | "
            f"Project: {proj_score:.1f}/10"
        ),
        "components": {
            "embedding":   round(embedding_score, 1),
            "skills":      round(skill_score, 1),
            "experience":  round(exp_score, 1),
            "project":     round(proj_score, 1),
        },
    }
