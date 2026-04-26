from typing import List, Dict, Any

def rank_candidates(processed_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    1. Computes Final Score = 0.6 * Match Score + 0.4 * Interest Score
    2. Enforces diversity: 3 strong (≥70), 3 moderate (40–69), 2 weak (<40)
    3. Returns exactly 8 candidates sorted by Final Score (descending)
    """
    # Compute final score for every candidate
    for c in processed_candidates:
        match_score    = c.get("match", {}).get("score", 0.0)
        interest_score = c.get("interest", {}).get("score", 0.0)
        c["final_score"] = round(0.6 * match_score + 0.4 * interest_score, 1)

    # Sort all candidates by final score (best first)
    ranked = sorted(processed_candidates, key=lambda x: x["final_score"], reverse=True)

    # Bucket by match score for diversity
    strong   = [c for c in ranked if c["match"]["score"] >= 70]
    moderate = [c for c in ranked if 40 <= c["match"]["score"] < 70]
    weak     = [c for c in ranked if c["match"]["score"] < 40]

    selection = (
        strong[:3]
        + moderate[:3]
        + weak[:2]
    )

    # If we have fewer than 8 (buckets weren't full), fill gaps from the ranked list
    if len(selection) < 8:
        selected_ids = {id(c) for c in selection}
        for c in ranked:
            if len(selection) >= 8:
                break
            if id(c) not in selected_ids:
                selection.append(c)
                selected_ids.add(id(c))

    # Final sort of the selected 8
    return sorted(selection[:8], key=lambda x: x["final_score"], reverse=True)
