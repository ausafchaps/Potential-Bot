from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.admin import AdminMetricsResponse
from app.services.admin_metrics import get_admin_metrics

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics", response_model=AdminMetricsResponse)
def get_admin_metrics_endpoint(
    db: Annotated[Session, Depends(get_db)],
) -> AdminMetricsResponse:
    return get_admin_metrics(db)

