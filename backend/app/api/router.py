from fastapi import APIRouter, Depends

from app.api.dependencies import require_admin, require_resource_owner
from app.api.routes.admin import router as admin_router
from app.api.routes.answers import router as answers_router
from app.api.routes.auth import router as auth_router
from app.api.routes.courses import router as courses_router
from app.api.routes.documents import document_router
from app.api.routes.documents import router as documents_router
from app.api.routes.flashcards import router as flashcards_router
from app.api.routes.health import router as health_router
from app.api.routes.history import router as history_router
from app.api.routes.questions import router as questions_router
from app.api.routes.quizzes import router as quizzes_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.study_recommendations import router as study_recommendations_router
from app.api.routes.users import router as users_router
from app.api.routes.weak_topics import router as weak_topics_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router, dependencies=[Depends(require_admin)])
api_router.include_router(answers_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(courses_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(document_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(documents_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(flashcards_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(history_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(questions_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(quizzes_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(retrieval_router, dependencies=[Depends(require_resource_owner)])
api_router.include_router(
    study_recommendations_router, dependencies=[Depends(require_resource_owner)]
)
api_router.include_router(users_router)
api_router.include_router(weak_topics_router, dependencies=[Depends(require_resource_owner)])
