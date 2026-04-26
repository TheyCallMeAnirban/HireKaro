"""
auth.py — JWT authentication for HireKaro.

Flow:
  POST /auth/register → creates user in SQLite → returns token
  POST /auth/login    → verifies password      → returns token
  GET  /auth/me       → decodes Bearer token   → returns user info

JWT secret is read from JWT_SECRET env var (falls back to a dev default).
In dev mode (no JWT_SECRET set), anonymous access is still allowed for all
existing API key-protected routes.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import bcrypt
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import pymongo
from bson.objectid import ObjectId

from config import get_logger

log = get_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["hirekaro"]
users_collection = db["users"]
users_collection.create_index("email", unique=True)

SECRET_KEY         = os.getenv("JWT_SECRET", "hirekaro-dev-secret-CHANGE-IN-PROD")
ALGORITHM          = "HS256"
TOKEN_EXPIRE_HOURS = 24

_bearer = HTTPBearer(auto_error=False)

# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

# ── Token helpers ─────────────────────────────────────────────────────────────

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub":   str(user_id),
        "email": email,
        "role":  role,
        "exp":   datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
) -> Optional[dict]:
    """Returns user dict if a valid Bearer token is present, else None."""
    if not creds:
        return None
    return _decode(creds.credentials)

async def require_user(
    creds: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
) -> dict:
    """Raises 401 if no valid Bearer token is present."""
    if not creds:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return _decode(creds.credentials)

# ── User management ───────────────────────────────────────────────────────────

def register_user(email: str, password: str, role: str = "recruiter") -> dict:
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
        
    existing = users_collection.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")
        
    user_doc = {
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.utcnow().isoformat()
    }
    result = users_collection.insert_one(user_doc)
    uid = str(result.inserted_id)
    
    log.info("auth.registered", extra={"user_id": uid, "role": role})
    token = create_token(uid, email, role)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": uid, "email": email, "role": role}}

def login_user(email: str, password: str) -> dict:
    user_doc = users_collection.find_one({"email": email})
    if not user_doc or not verify_password(password, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
        
    # Update login tracking in MongoDB
    users_collection.update_one(
        {"_id": user_doc["_id"]},
        {
            "$set": {"last_login_at": datetime.utcnow().isoformat()},
            "$inc": {"login_count": 1}
        }
    )
        
    uid = str(user_doc["_id"])
    token = create_token(uid, user_doc["email"], user_doc["role"])
    log.info("auth.login", extra={"user_id": uid})
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": uid, "email": user_doc["email"], "role": user_doc["role"]}}
