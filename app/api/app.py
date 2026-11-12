"""
FastAPI application for PharmaGraph Demo Phase D2.
Endpoints:
- POST /api/ask
- GET /api/health
CORS configured strictly for http://localhost:5173.
Includes request size limits, timeout, and dependency-free sliding window rate limiting.
"""

import asyncio
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.generation.config import GenerationConfig
from app.generation.contracts import AskRequest, AskResponse
from app.generation.service import AnswerService

config = GenerationConfig()
answer_service = AnswerService(config=config)

app = FastAPI(
    title="PharmaGraph API",
    description="Evidence-Grounded Pharmacogenomics Intelligence Core",
    version="0.2.0",
)

# 1. CORS allowlist strictly for frontend development origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# 2. Dependency-free in-memory rate limiter (sliding window: max 60 requests/minute per client IP)
class RateLimiter:
    """Simple thread-safe in-memory sliding window rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        # Clean older timestamps
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]
        if len(self._requests[client_ip]) >= self.max_requests:
            return False
        self._requests[client_ip].append(now)
        return True


rate_limiter = RateLimiter(max_requests=60, window_seconds=60.0)


# 3. Request Size Limit Middleware (Reject bodies > 50,000 bytes)
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app_instance, max_content_length: int = 50000):
        super().__init__(app_instance)
        self.max_content_length = max_content_length

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_content_length:
            return Response(
                content="Request entity too large (exceeds 50KB limit).",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        return await call_next(request)


app.add_middleware(RequestSizeLimitMiddleware, max_content_length=50000)


@app.get("/api/health")
def health_check() -> dict:
    """Health check endpoint indicating service status and active LLM provider/model."""
    return {
        "status": "ok",
        "service": "PharmaGraph API",
        "provider": config.llm_provider,
        "mode": config.llm_mode,
        "model": config.llm_model,
        "cors_allowed_origins": ["http://localhost:5173"],
    }


@app.get("/api/stats")
def get_stats() -> dict:
    """Return index and meaning-search coverage statistics per source_type."""
    return answer_service.get_stats_summary()


@app.post("/api/ask", response_model=AskResponse)
async def ask_question(req: AskRequest, request: Request) -> AskResponse:
    """
    Synthesize an evidence-grounded answer to a biomedical question.
    Executes input guards, hybrid retrieval, graph traversal, sufficiency checks,
    LLM generation, and citation verification.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 60 requests per minute.",
        )

    try:
        # Run synchronous service inside threadpool with timeout protection
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None, answer_service.answer_question, req.question, req.entity_hints
            ),
            timeout=config.request_timeout_seconds,
        )
        return response
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Request timed out after {config.request_timeout_seconds} seconds.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating answer: {str(e)}",
        )
