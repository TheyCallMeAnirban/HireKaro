"""
main.py — HireKaro FastAPI v3.0

Pipeline (≤ 10 LLM calls total per request):
  Step 1: parse_jd + detect_bias           → 2 LLM calls (concurrent)
  Step 2: embed JD                          → 1 Embeddings API call
  Step 3: cosine similarity + deterministic scoring for all candidates → 0 LLM calls
  Step 4: rank candidates                   → 0 LLM calls
  Step 5: generate_fit_summary for top 8   → ≤ 8 LLM calls (Semaphore-guarded)
  ─────────────────────────────────────────────────────
  Total: ≤ 10 generate_content calls  (vs 62 in v2)
"""

import json
import io
import os
import csv
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Security, Request, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()

from config       import MAX_WORKERS, get_logger, llm_circuit_breaker
from jd_parser    import parse_jd
from matcher      import calculate_match_score
from scoring      import deterministic_interest_score
from ranking      import rank_candidates
from summarizer   import generate_fit_summary
from bias_detector import detect_bias
from database     import (init_db, save_analysis, get_history, get_analysis,
                        delete_analysis, save_feedback, get_feedback_stats)
from resume_parser import extract_text_from_pdf, parse_resume
from embedder     import get_embedding, build_candidate_text, build_jd_text
from cache        import get_cached, set_cached, stats as cache_stats
from auth         import register_user, login_user, get_current_user, require_user

log = get_logger(__name__)

# ── Optional Sentry ───────────────────────────────────────────────────────────
if dsn := os.getenv("SENTRY_DSN"):
    import sentry_sdk
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.1)
    log.info("sentry.initialized")

# ── Concurrency Controls ──────────────────────────────────────────────────────
_executor      = ThreadPoolExecutor(max_workers=MAX_WORKERS)
_LLM_SEMAPHORE = asyncio.Semaphore(5)   # max 5 concurrent LLM calls at once

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Auth ──────────────────────────────────────────────────────────────────────
_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def _verify_key(api_key: str = Security(_API_KEY_HEADER)):
    expected = os.getenv("APP_API_KEY")
    if expected and api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

ALLOWED_ORIGINS = [
    o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

# ── Startup ───────────────────────────────────────────────────────────────────
CANDIDATES: list = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global CANDIDATES
    path = os.path.join(os.path.dirname(__file__), "data", "candidates.json")
    with open(path) as f:
        CANDIDATES = json.load(f)

    # Precompute embeddings for all candidates at startup (once, then cached in-memory)
    log.info("startup.precomputing_embeddings", extra={"count": len(CANDIDATES)})
    loop = asyncio.get_event_loop()
    embeddings = await asyncio.gather(*[
        loop.run_in_executor(_executor, get_embedding, build_candidate_text(c), "RETRIEVAL_DOCUMENT")
        for c in CANDIDATES
    ])
    for c, emb in zip(CANDIDATES, embeddings):
        c["embedding"] = emb

    init_db()
    log.info("startup.complete", extra={"candidates": len(CANDIDATES)})
    yield
    _executor.shutdown(wait=False)

app = FastAPI(title="HireKaro AI Talent API", version="3.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=90.0)
        except asyncio.TimeoutError:
            log.error("request.timeout", extra={"path": str(request.url.path)})
            return JSONResponse({"detail": "Request timed out."}, status_code=504)

app.add_middleware(TimeoutMiddleware)

# ── Models ────────────────────────────────────────────────────────────────────
class JDInput(BaseModel):
    jd_text: str = Field(..., min_length=20, max_length=8000)

# ── Pipeline ──────────────────────────────────────────────────────────────────

async def _summarize_guarded(candidate: dict, parsed_jd: dict, match: dict, loop) -> dict:
    """Rate-limited LLM summary — Semaphore ensures ≤ 5 concurrent Gemini calls."""
    async with _LLM_SEMAPHORE:
        return await loop.run_in_executor(
            _executor, generate_fit_summary, candidate, parsed_jd, match
        )

async def _run_pipeline(candidates: list, parsed_jd: dict, jd_embedding: list) -> list:
    """
    Clean pipeline:
      1. Deterministic scoring for all candidates   (0 LLM calls)
      2. Rank                                        (0 LLM calls)
      3. Summarise ranked results                   (≤ 8 LLM calls, semaphore-guarded)
    """
    loop = asyncio.get_event_loop()

    # Step 1 & 2: Score + rank all candidates deterministically (instant)
    processed = []
    for c in candidates:
        match    = calculate_match_score(c, parsed_jd, jd_embedding)
        interest = deterministic_interest_score(c)
        processed.append({
            "name":             c["name"],
            "current_role":     c["current_role"],
            "years_experience": c["years_experience"],
            "project":          c["project"],
            "skills":           c["skills"],
            "match":            match,
            "interest":         interest,
            "conversation":     [],   # no simulation in v3 pipeline
            "fit_summary":      {},   # filled in step 3
        })

    ranked = rank_candidates(processed)

    # Step 3: LLM summaries only for the ranked output (≤ 8 calls, semaphored)
    summaries = await asyncio.gather(*[
        _summarize_guarded(candidates[i], parsed_jd, ranked[i]["match"], loop)
        for i in range(len(ranked))
    ])
    for item, summary in zip(ranked, summaries):
        item["fit_summary"] = summary

    return ranked


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":          "ok",
        "version":         "3.0.0",
        "circuit_breaker": llm_circuit_breaker.state,
        "cache":           cache_stats(),
    }


# ── Auth Routes ────────────────────────────────────────────────────────────────
class RegisterInput(BaseModel):
    email:    str = Field(..., min_length=5,  max_length=120)
    password: str = Field(..., min_length=8,  max_length=128)
    role:     str = Field(default="recruiter")

class LoginInput(BaseModel):
    email:    str
    password: str

@app.post("/auth/register")
async def register(payload: RegisterInput):
    return register_user(payload.email, payload.password, payload.role)

@app.post("/auth/login")
async def login(payload: LoginInput):
    return login_user(payload.email, payload.password)

@app.get("/auth/me")
async def me(user: dict = Depends(require_user)):
    return {"id": user["sub"], "email": user["email"], "role": user["role"]}


@app.post("/analyze-jd", dependencies=[Security(_verify_key)])
@limiter.limit("10/minute")
async def analyze_job_description(request: Request, payload: JDInput):
    """
    v3 pipeline: check cache first → parse+bias (2 LLM) → embed → score → rank → summarise (≤8 LLM).
    Cache hit = instant response, $0 LLM cost.
    """
    if cached := get_cached(payload.jd_text):
        log.info("analyze_jd.cache_hit")
        return {**cached, "cached": True}

    log.info("analyze_jd.start", extra={"jd_len": len(payload.jd_text)})
    loop = asyncio.get_event_loop()

    # Step 1: Parse JD + detect bias concurrently (2 LLM calls)
    parsed_jd, bias_report = await asyncio.gather(
        loop.run_in_executor(_executor, parse_jd,    payload.jd_text),
        loop.run_in_executor(_executor, detect_bias, payload.jd_text),
    )

    # Step 2: Embed JD (1 embedding API call)
    jd_embedding = await loop.run_in_executor(
        _executor, get_embedding,
        build_jd_text(parsed_jd, payload.jd_text),
        "RETRIEVAL_QUERY",
    )

    # Step 3–5: Score all candidates deterministically → rank → summarise top 8
    final_candidates = await _run_pipeline(CANDIDATES, parsed_jd, jd_embedding)

    analysis_id = save_analysis(payload.jd_text, parsed_jd, final_candidates, bias_report)
    log.info("analyze_jd.complete", extra={"analysis_id": analysis_id})

    result = {
        "analysis_id": analysis_id,
        "parsed_jd":   parsed_jd,
        "bias_report": bias_report,
        "candidates":  final_candidates,
        "cached":      False,
    }
    set_cached(payload.jd_text, result)
    return result


@app.post("/upload-resume", dependencies=[Security(_verify_key)])
@limiter.limit("20/minute")
async def upload_resume(request: Request, file: UploadFile = File(...), jd_text: str = ""):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    loop = asyncio.get_event_loop()
    file_bytes = await file.read()

    if jd_text.strip():
        resume_text, parsed_jd = await asyncio.gather(
            loop.run_in_executor(_executor, extract_text_from_pdf, file_bytes),
            loop.run_in_executor(_executor, parse_jd, jd_text),
        )
    else:
        resume_text = await loop.run_in_executor(_executor, extract_text_from_pdf, file_bytes)
        parsed_jd = {"role": "General Engineer", "seniority": "Mid", "domain": "General",
                     "required_skills": [], "secondary_skills": []}

    candidate = await loop.run_in_executor(_executor, parse_resume, resume_text)

    # Embed candidate + JD concurrently
    cand_emb, jd_emb = await asyncio.gather(
        loop.run_in_executor(_executor, get_embedding, build_candidate_text(candidate), "RETRIEVAL_DOCUMENT"),
        loop.run_in_executor(_executor, get_embedding, build_jd_text(parsed_jd, jd_text), "RETRIEVAL_QUERY"),
    )
    candidate["embedding"] = cand_emb

    match_result = calculate_match_score(candidate, parsed_jd, jd_emb)
    interest     = deterministic_interest_score(candidate)

    async with _LLM_SEMAPHORE:
        fit_summary = await loop.run_in_executor(
            _executor, generate_fit_summary, candidate, parsed_jd, match_result
        )

    final_score = round(0.6 * match_result["score"] + 0.4 * interest["score"], 1)

    return {
        "parsed_jd": parsed_jd,
        "candidate": {
            "name": candidate["name"], "current_role": candidate["current_role"],
            "years_experience": candidate["years_experience"], "project": candidate["project"],
            "skills": candidate["skills"], "match": match_result, "conversation": [],
            "interest": interest, "fit_summary": fit_summary, "final_score": final_score,
        }
    }


@app.get("/history", dependencies=[Security(_verify_key)])
def list_history(
    page:  int = Query(default=1,  ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    return get_history(page=page, limit=limit)


@app.get("/history/{analysis_id}", dependencies=[Security(_verify_key)])
def get_history_item(analysis_id: int):
    item = get_analysis(analysis_id)
    if not item:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return item


@app.delete("/history/{analysis_id}", dependencies=[Security(_verify_key)])
def remove_history_item(analysis_id: int):
    if not delete_analysis(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {"deleted": True, "analysis_id": analysis_id}


# ── Feedback Routes ───────────────────────────────────────────────────────────────────
class FeedbackInput(BaseModel):
    analysis_id:    int
    candidate_name: str
    action:         str = Field(..., pattern="^(shortlist|reject|hire)$")

@app.post("/feedback", dependencies=[Security(_verify_key)])
async def submit_feedback(
    payload: FeedbackInput,
    user: dict | None = Depends(get_current_user),
):
    """Record recruiter feedback (shortlist/reject/hire) on a candidate."""
    uid = str(user["sub"]) if user else None
    fb_id = save_feedback(
        analysis_id    = payload.analysis_id,
        candidate_name = payload.candidate_name,
        action         = payload.action,
        user_id        = uid,
    )
    return {"feedback_id": fb_id, "action": payload.action,
            "candidate": payload.candidate_name}

@app.get("/feedback/stats", dependencies=[Security(_verify_key)])
def feedback_stats(analysis_id: int | None = None):
    """Aggregated shortlist/reject/hire counts + precision@k metric."""
    return get_feedback_stats(analysis_id)


@app.get("/export-csv/{analysis_id}", dependencies=[Security(_verify_key)])
def export_csv(analysis_id: int):
    item = get_analysis(analysis_id)
    if not item:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Rank", "Name", "Current Role", "YOE",
                     "Match Score", "Interest Score", "Final Score",
                     "Recommendation", "Matched Skills", "Missing Skills",
                     "Key Strength", "Key Gap", "Score Breakdown"])
    for i, c in enumerate(item["candidates"], 1):
        fs  = c.get("fit_summary", {})
        comp = c.get("match", {}).get("components", {})
        writer.writerow([
            i, c["name"], c["current_role"], c["years_experience"],
            c["match"]["score"], c["interest"]["score"], c.get("final_score", ""),
            fs.get("recommendation", ""),
            "; ".join(c["match"]["matched_skills"]),
            "; ".join(c["match"]["missing_skills"]),
            fs.get("key_strength", ""), fs.get("key_gap", ""),
            f"emb:{comp.get('embedding',0)} skl:{comp.get('skills',0)} "
            f"exp:{comp.get('experience',0)} prj:{comp.get('project',0)}",
        ])

    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition":
                                      f"attachment; filename=analysis_{analysis_id}.csv"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
