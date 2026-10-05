from fastapi import Request
from fastapi.responses import JSONResponse

from app.services.ai_usage import AIUsageLimited, AIUsageUnavailable
from app.services.llm.base import LLMProviderRateLimited


async def usage_limited(_request: Request, exc: AIUsageLimited) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"{exc} Try again in {exc.retry_after} seconds."},
        headers={"Retry-After": str(exc.retry_after), "Cache-Control": "no-store"},
    )


async def usage_unavailable(_request: Request, _exc: AIUsageUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503, content={"detail": "AI usage limits are temporarily unavailable. "
                                 "Please try again shortly."},
        headers={"Retry-After": "30", "Cache-Control": "no-store"},
    )


async def provider_limited(_request: Request, exc: LLMProviderRateLimited) -> JSONResponse:
    return JSONResponse(
        status_code=429, content={"detail": "The AI provider is temporarily at its usage limit. "
                                            f"Try again in {exc.retry_after} seconds."},
        headers={"Retry-After": str(exc.retry_after), "Cache-Control": "no-store"},
    )
