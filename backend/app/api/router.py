from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.answers import router as answers_router
from app.api.routes.courses import router as courses_router
from app.api.routes.documents import document_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.history import router as history_router
from app.api.routes.questions import router as questions_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(answers_router)
api_router.include_router(courses_router)
api_router.include_router(document_router)
api_router.include_router(documents_router)
api_router.include_router(health_router, tags=["health"])
api_router.include_router(history_router)
api_router.include_router(questions_router)
api_router.include_router(retrieval_router)
api_router.include_router(users_router)
