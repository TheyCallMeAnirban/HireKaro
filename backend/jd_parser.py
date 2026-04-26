import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from google import genai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
from config import GEMINI_MODEL, is_retryable, get_logger

log = get_logger(__name__)

class ParsedJD(BaseModel):
    role:             str       = Field(description="The formal title of the role, e.g. 'Senior Backend Engineer'")
    seniority:        str       = Field(description="Seniority level: Junior, Mid, Senior, Lead, or Principal")
    domain:           str       = Field(description="Technical domain: Backend, Frontend, Fullstack, Data, ML, Product, Design, DevOps, Security, etc.")
    required_skills:  List[str] = Field(description="Mandatory technical skills or tools explicitly required in the JD")
    secondary_skills: List[str] = Field(description="Nice-to-have or secondary skills mentioned in the JD")

@retry(
    retry=retry_if_exception(is_retryable),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(2),
    reraise=True,
)
def _call_gemini(client, prompt: str):
    return client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": ParsedJD, "temperature": 0.1},
    )

def parse_jd(jd_text: str) -> Dict[str, Any]:
    """Uses Gemini to parse a JD into structured data. Falls back to heuristic if unavailable."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return fallback_parse_jd(jd_text)
    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            "You are a senior technical recruiter. Carefully analyze the following job description "
            "and extract structured information about the role.\n\n"
            f"Job Description:\n{jd_text}"
        )
        response = _call_gemini(client, prompt)
        log.info("jd_parser.success")
        return response.parsed.model_dump()
    except Exception as e:
        log.error("jd_parser.llm_failed", extra={"error": str(e)})
        return fallback_parse_jd(jd_text)

def fallback_parse_jd(jd_text: str) -> Dict[str, Any]:
    jd_lower = jd_text.lower()
    seniority = "Mid"
    if any(k in jd_lower for k in ["senior", "lead", "principal", "staff"]):
        seniority = "Senior"
    elif any(k in jd_lower for k in ["junior", "entry", "intern", "graduate"]):
        seniority = "Junior"

    domain = "General"
    if any(k in jd_lower for k in ["backend", "server", "api", "database"]):
        domain = "Backend"
    elif any(k in jd_lower for k in ["frontend", "ui", "ux"]):
        domain = "Frontend"
    elif any(k in jd_lower for k in ["fullstack", "full stack", "full-stack"]):
        domain = "Fullstack"
    elif any(k in jd_lower for k in ["machine learning", "ml", " ai ", "deep learning"]):
        domain = "ML"
    elif any(k in jd_lower for k in ["data engineer", "etl", "pipeline", "spark"]):
        domain = "Data"
    elif any(k in jd_lower for k in ["product manager", "product owner", "agile"]):
        domain = "Product"
    elif any(k in jd_lower for k in ["devops", "sre", "infrastructure", "terraform"]):
        domain = "DevOps"

    role = f"{seniority} {domain} Engineer"
    tech_keywords = [
        "python", "java", "c++", "go", "rust", "javascript", "typescript",
        "react", "angular", "vue", "node.js", "fastapi", "django", "flask",
        "spring boot", "sql", "postgresql", "mysql", "mongodb", "redis",
        "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
        "machine learning", "pandas", "pytorch", "tensorflow", "spark",
        "kafka", "graphql", "grpc",
    ]
    found = [skill for skill in tech_keywords if skill in jd_lower]
    split = max(1, len(found) // 2 + 1)
    return {
        "role": role, "seniority": seniority, "domain": domain,
        "required_skills": found[:split] if found else ["python", "sql"],
        "secondary_skills": found[split:],
    }
