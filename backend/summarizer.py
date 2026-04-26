import os
from typing import Dict, Any, List
from typing import Literal
from pydantic import BaseModel, Field
from google import genai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
from config import GEMINI_MODEL, is_retryable, get_logger, llm_circuit_breaker

log = get_logger(__name__)

class FitSummary(BaseModel):
    summary:        str                                  = Field(description="A 2-3 sentence recruiter brief about this candidate's fit for the role. Be specific and mention their actual skills and project.")
    recommendation: Literal["Fast Track", "Consider", "Pass"] = Field(description="Exactly one of: 'Fast Track', 'Consider', 'Pass'")
    key_strength:   str                                  = Field(description="The single biggest strength this candidate brings to the role in one short sentence.")
    key_gap:        str                                  = Field(description="The single biggest gap or concern in one short sentence. Write 'None identified' if no significant gap.")

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
        config={"response_mime_type": "application/json", "response_schema": FitSummary, "temperature": 0.3},
    )

def generate_fit_summary(candidate: Dict[str, Any], parsed_jd: Dict[str, Any], match: Dict[str, Any]) -> Dict[str, Any]:
    # Circuit breaker: skip LLM if Gemini is repeatedly failing
    if llm_circuit_breaker.is_open:
        log.warning("summarizer.circuit_open")
        return _fallback(candidate, match)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return _fallback(candidate, match)
    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            f"You are a senior technical recruiter writing a hiring-manager brief.\n\n"
            f"Role: {parsed_jd.get('role')} ({parsed_jd.get('seniority')}, {parsed_jd.get('domain')} domain)\n"
            f"Required Skills: {', '.join(parsed_jd.get('required_skills', []))}\n\n"
            f"Candidate: {candidate['name']}\n"
            f"Current Role: {candidate['current_role']}\n"
            f"YOE: {candidate['years_experience']}\n"
            f"Skills: {', '.join(candidate['skills'])}\n"
            f"Key Project: {candidate['project']}\n"
            f"Match Score: {match['score']}/100\n"
            f"Matched Skills: {', '.join(match['matched_skills'])}\n"
            f"Missing Skills: {', '.join(match['missing_skills'])}\n\n"
            "Write a concise, honest recruiter brief. Reference actual skills and project."
        )
        response = _call_gemini(client, prompt)
        llm_circuit_breaker.record_success()
        log.info("summarizer.success", extra={"candidate": candidate["name"]})
        return response.parsed.model_dump()
    except Exception as e:
        llm_circuit_breaker.record_failure()
        log.error("summarizer.llm_failed", extra={"error": str(e)})
        return _fallback(candidate, match)

def _fallback(candidate: Dict[str, Any], match: Dict[str, Any]) -> Dict[str, Any]:
    score   = match["score"]
    matched = match["matched_skills"]
    missing = match["missing_skills"]
    name    = candidate["name"]

    if score >= 70:
        return {
            "summary": (f"{name} is a strong match. They cover {len(matched)} of the required skills "
                        f"({', '.join(matched[:2])}) and their project experience directly aligns with the role's core needs. "
                        "Recommend fast-tracking to a technical screen."),
            "recommendation": "Fast Track",
            "key_strength": f"Direct skill coverage in {matched[0] if matched else 'core requirements'}",
            "key_gap": f"Missing: {', '.join(missing[:2])}" if missing else "None identified",
        }
    elif score >= 40:
        return {
            "summary": (f"{name} is a moderate match. They bring solid experience in "
                        f"{', '.join(matched[:2]) if matched else 'adjacent areas'} but have gaps in "
                        f"{', '.join(missing[:2]) if missing else 'some requirements'}. Worth an exploratory call."),
            "recommendation": "Consider",
            "key_strength": f"Experience in {matched[0] if matched else 'related technologies'}",
            "key_gap": f"Needs upskilling in {missing[0] if missing else 'some areas'}",
        }
    else:
        # ── Diagnose WHY the score is low, not just how many skills are missing ──
        comp       = match.get("components", {})
        exp_score  = comp.get("experience",  10)
        emb_score  = comp.get("embedding",   20)
        name_lower = name.lower()

        if "uploaded candidate" in name_lower or not candidate.get("skills"):
            # Resume parsing failed or returned empty data
            gap_reason = "the resume could not be fully parsed — skills and experience data is incomplete"
            key_gap    = "Resume parsing incomplete. Re-upload a text-selectable PDF for accurate scoring."

        elif missing:
            # Genuine skill gaps
            gap_reason = f"gaps in {len(missing)} required skill(s): {', '.join(missing[:3])}"
            key_gap    = f"Missing: {', '.join(missing[:3])}"

        elif exp_score < 10:
            # Skill coverage is fine but experience is too low
            gap_reason = (
                f"insufficient experience — {candidate.get('years_experience', 0)} year(s) "
                f"for a {match.get('explanation', '').split('vs')[1].split('yr')[0].strip() if 'vs' in match.get('explanation','') else 'senior'}-level role"
            )
            key_gap = "Below the minimum experience threshold for this seniority level"

        elif emb_score < 15:
            # Embeddings show semantic mismatch even if surface skills look okay
            gap_reason = "an overall domain mismatch with the role's focus area"
            key_gap    = "Candidate's background is in a different technical domain"

        else:
            gap_reason = "a combination of experience, domain, and project alignment factors"
            key_gap    = "Overall profile alignment with the role needs improvement"

        return {
            "summary": (
                f"{name} is not a strong fit for this role, primarily due to {gap_reason}. "
                "Consider for adjacent or more junior openings."
            ),
            "recommendation": "Pass",
            "key_strength": (
                f"Experience in {matched[0]}" if matched
                else "Potential for growth with relevant upskilling"
            ),
            "key_gap": key_gap,
        }
