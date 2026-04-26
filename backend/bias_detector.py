import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from google import genai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception

MODEL = "gemini-2.0-flash"

KNOWN_BIASED_TERMS: Dict[str, str] = {
    "rockstar":       "Exceptional engineer or top performer",
    "ninja":          "Skilled developer",
    "wizard":         "Expert engineer",
    "guru":           "Subject matter expert",
    "superhero":      "High performer",
    "hacker":         "Creative problem-solver",
    "young":          "Early-career professional",
    "recent grad":    "Entry-level candidate",
    "digital native": "Proficient with modern digital tools",
    "he/she":         "they/them",
    "manpower":       "workforce or staffing",
    "aggressive":     "results-driven",
    "dominate":       "excel or lead",
    "killer instinct":"competitive drive",
}

# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class BiasFlagItem(BaseModel):
    phrase:     str = Field(description="The exact biased word or phrase found in the JD")
    reason:     str = Field(description="One sentence explaining why this may discourage diverse applicants")
    suggestion: str = Field(description="A specific, inclusive replacement phrase")

class BiasReport(BaseModel):
    has_bias:     bool            = Field(description="True if any biased or exclusionary language was found")
    flags:        List[BiasFlagItem] = Field(description="Each biased phrase with a reason and inclusive suggestion")
    overall_risk: str             = Field(description="Risk level: 'low', 'medium', or 'high'")

# ── Retry Helper ──────────────────────────────────────────────────────────────

def _is_retryable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "429" not in msg and "403" not in msg

@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(min=2, max=8),
    stop=stop_after_attempt(2),
    reraise=True,
)
def _call_gemini(client, prompt: str):
    return client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema":    BiasReport,
            "temperature":        0.1,
        },
    )

# ── Public API ────────────────────────────────────────────────────────────────

def detect_bias(jd_text: str) -> Dict[str, Any]:
    """Detects biased/exclusionary language in a JD. Falls back to keyword matching."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return _fallback(jd_text)
    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            "Analyze the following job description for biased or exclusionary language.\n\n"
            "For EACH issue found, return a structured flag with:\n"
            "  - phrase: the exact problematic word or phrase\n"
            "  - reason: one sentence on why it may discourage diverse applicants\n"
            "  - suggestion: a specific, inclusive replacement phrase\n\n"
            "Look for:\n"
            "  - Gendered / coded language (e.g. 'rockstar', 'ninja', 'manpower')\n"
            "  - Age bias ('young', 'recent grad', 'digital native')\n"
            "  - Aggressive culture language ('killer instinct', 'dominate')\n"
            "  - Vague culture-fit phrasing that may exclude minorities\n\n"
            "Set overall_risk to 'high' (3+ issues), 'medium' (1-2), 'low' (none).\n"
            "Only flag genuine issues — neutral technical terms are fine.\n\n"
            f"Job Description:\n{jd_text}"
        )
        response = _call_gemini(client, prompt)
        return response.parsed.model_dump()
    except Exception as e:
        print(f"[bias_detector] LLM failed: {e}. Using fallback.")
        return _fallback(jd_text)


def _fallback(jd_text: str) -> Dict[str, Any]:
    """Keyword-based fallback — produces the same BiasFlag shape as the LLM path."""
    jd_lower = jd_text.lower()
    flags = [
        {
            "phrase":     term,
            "reason":     "Known exclusionary or gender-coded term that may discourage diverse applicants.",
            "suggestion": replacement,
        }
        for term, replacement in KNOWN_BIASED_TERMS.items()
        if term in jd_lower
    ]
    return {
        "has_bias":     len(flags) > 0,
        "flags":        flags,
        "overall_risk": "high" if len(flags) >= 2 else ("medium" if flags else "low"),
    }
