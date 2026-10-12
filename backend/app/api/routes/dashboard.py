import uuid

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import CurrentUser, Database
from app.schemas.dashboard import StudyDashboard
from app.services.dashboard import get_study_dashboard
from app.services.retrieval import CourseNotFoundError

router = APIRouter(tags=["study dashboard"])


@router.get("/courses/{course_id}/dashboard", response_model=StudyDashboard)
def dashboard(course_id: uuid.UUID, db: Database, user: CurrentUser,
              response: Response) -> StudyDashboard:
    response.headers["Cache-Control"] = "no-store"
    try:
        return get_study_dashboard(db, course_id, user.id)
    except CourseNotFoundError as exc:
        raise HTTPException(404, str(exc), headers={"Cache-Control": "no-store"}) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503,
                            "Your study dashboard is temporarily unavailable. Refresh to retry.",
                            headers={"Cache-Control": "no-store"}) from exc
