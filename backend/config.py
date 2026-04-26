"""
config.py — Single source of truth for HireKaro backend.
All modules import from here. No more 6-way duplication.
"""
import os
import time
import threading
import logging
import json

# ── LLM Settings ──────────────────────────────────────────────────────────────
GEMINI_MODEL   = "gemini-2.0-flash"
GEMINI_TIMEOUT = 20.0  # hard wall-clock limit per LLM call (seconds)
MAX_WORKERS    = 15    # ThreadPoolExecutor size

# ── Structured JSON Logger ────────────────────────────────────────────────────
class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts":     self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)

def get_logger(name: str) -> logging.Logger:
    """Return a structured JSON logger. Idempotent — safe to call multiple times."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
        logger.propagate = False
    return logger

# ── Retry Helper ──────────────────────────────────────────────────────────────
def is_retryable(exc: BaseException) -> bool:
    """Retry transient network errors; give up immediately on quota/auth errors."""
    msg = str(exc).lower()
    return "429" not in msg and "403" not in msg and "invalid" not in msg


# ── Circuit Breaker ─────────────────────────────────────────────────────────────
class CircuitBreaker:
    """
    Three-state circuit breaker: CLOSED → OPEN → HALF-OPEN → CLOSED.
    Protects downstream LLM calls from cascading failures.
    """
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self._threshold   = failure_threshold
        self._timeout     = recovery_timeout
        self._failures    = 0
        self._last_fail   = 0.0
        self._state       = "CLOSED"
        self._lock        = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._state == "OPEN":
                if time.time() - self._last_fail > self._timeout:
                    self._state = "HALF-OPEN"
                    return False
                return True
            return False

    def record_success(self):
        with self._lock:
            self._failures = 0
            self._state    = "CLOSED"

    def record_failure(self):
        with self._lock:
            self._failures  += 1
            self._last_fail  = time.time()
            if self._failures >= self._threshold:
                self._state = "OPEN"
                _log = get_logger("circuit_breaker")
                _log.error("circuit_breaker.opened",
                           extra={"failures": self._failures})

    @property
    def state(self) -> str:
        return self._state


# Shared singleton — import this in every LLM module
llm_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
