from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_usage import provider_limited, usage_limited, usage_unavailable
from app.api.router import api_router
from app.core.config import settings
from app.services.ai_usage import AIUsageLimited, AIUsageUnavailable
from app.services.llm.base import LLMProviderRateLimited


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_exception_handler(AIUsageLimited, usage_limited)
    app.add_exception_handler(AIUsageUnavailable, usage_unavailable)
    app.add_exception_handler(LLMProviderRateLimited, provider_limited)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in settings.cors_origins.split(",")
            if origin.strip()
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Retry-After"],
    )
    app.include_router(api_router)
    return app


app = create_app()
