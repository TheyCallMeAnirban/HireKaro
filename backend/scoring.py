import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from google import genai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
from config import GEMINI_MODEL, is_retryable, get_logger

log = get_logger(__name__)

# ── Deterministic Interest Score (NO LLM) ─────────────────────────────────────
_INTEREST_MAP = {
    "High":   {"score": 82.0, "level": "High",
               "reason": "Candidate profile indicates strong openness to new opportunities."},
    "Medium": {"score": 60.0, "level": "Medium",
               "reason": "Candidate would consider the right opportunity."},
    "Low":    {"score": 22.0, "level": "Low",
               "reason": "Candidate appears settled in current role."},
}

def deterministic_interest_score(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Zero-LLM interest estimation from candidate profile data.
    This is what the main pipeline calls instead of conversation simulation.
    """
    level = candidate.get("interest_level", "Medium")
    return dict(_INTEREST_MAP.get(level, _INTEREST_MAP["Medium"]))


# ── LLM-based Interest Score (optional, kept for audit/testing) ───────────────
class InterestScoreOutput(BaseModel):
    enthusiasm_score: float = Field(description="Score 0-40: candidate's enthusiasm and positive tone")
    clarity_score:    float = Field(description="Score 0-30: how specifically and clearly the candidate answered")
    engagement_score: float = Field(description="Score 0-30: depth of response and follow-up questions asked")
    reason: str             = Field(description="One sentence explaining the overall interest assessment")

@retry(
    retry=retry_if_exception(is_retryable),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    stop=stop_after_attempt(2),
    reraise=True,
)
def _call_gemini(client, prompt: str):
    return client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json",
                "response_schema": InterestScoreOutput, "temperature": 0.1},
    )

def calculate_interest_score(
    candidate: Dict[str, Any],
    conversation: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    LLM-based conversation scoring. NOT in the main pipeline.
    Kept for optional audit use only.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return deterministic_interest_score(candidate)

    convo_text = "\n".join(f"[{m['role'].upper()}]: {m['text']}" for m in conversation)
    try:
        client   = genai.Client(api_key=api_key)
        prompt   = f"Score only the CANDIDATE's responses:\n\n{convo_text}"
        response = _call_gemini(client, prompt)
        result   = response.parsed
        total    = min(100.0, max(0.0,
                       result.enthusiasm_score + result.clarity_score + result.engagement_score))
        level    = "High" if total >= 70 else ("Medium" if total >= 40 else "Low")
        return {"score": round(total, 1), "level": level, "reason": result.reason}
    except Exception as e:
        log.error("scoring.llm_failed", extra={"error": str(e)})
        return deterministic_interest_score(candidate)
