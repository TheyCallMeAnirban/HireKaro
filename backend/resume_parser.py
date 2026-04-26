import os
import io
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from google import genai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
from config import GEMINI_MODEL, is_retryable, get_logger

log = get_logger(__name__)

PDF_TEXT_LIMIT = 8000  # characters — increased from 4000 to capture longer resumes

class ParsedResume(BaseModel):
    name:             str       = Field(description="Full name of the candidate")
    current_role:     str       = Field(description="Their most recent job title")
    years_experience: int       = Field(description="Estimated total years of professional experience based on dates")
    skills:           List[str] = Field(description="All technical skills, tools, and frameworks mentioned")
    project:          str       = Field(description="Their most impressive project or achievement in one sentence")
    domain:           str       = Field(description="Primary domain: Backend, Frontend, Fullstack, Data, ML, Product, Design, DevOps, or Security")

@retry(
    retry=retry_if_exception(is_retryable),
    wait=wait_exponential(min=2, max=8),
    stop=stop_after_attempt(2),
    reraise=True,
)
def _call_gemini(client, prompt: str):
    return client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": ParsedResume, "temperature": 0.1},
    )

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            log.info("resume_parser.pdf_extracted", extra={"chars": len(text)})
            return text
    except Exception as e:
        log.error("resume_parser.pdf_extraction_failed", extra={"error": str(e)})
        return ""

def parse_resume(text: str) -> Dict[str, Any]:
    if not text.strip():
        return _empty_candidate()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return _empty_candidate()

    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            "Extract structured information from this resume. "
            "Estimate years of experience from employment dates. "
            "Pick the most impressive project/achievement and summarize in one sentence.\n\n"
            f"Resume:\n{text[:PDF_TEXT_LIMIT]}"
        )
        response = _call_gemini(client, prompt)
        result = response.parsed.model_dump()
        result["interest_level"] = "Medium"  # default for uploaded resumes
        log.info("resume_parser.success", extra={"name": result.get("name")})
        return result
    except Exception as e:
        log.error("resume_parser.llm_failed", extra={"error": str(e)})
        return _empty_candidate()

def _empty_candidate() -> Dict[str, Any]:
    return {
        "name": "Uploaded Candidate",
        "current_role": "Software Engineer",
        "years_experience": 0,
        "skills": [],
        "project": "Resume parsing failed — please check the PDF.",
        "domain": "General",
        "interest_level": "Medium",
    }
