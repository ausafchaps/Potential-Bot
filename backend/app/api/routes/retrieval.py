import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.retrieval import HybridSearchResponse, SearchResponse, VectorSearchResponse
from app.services.hybrid_retrieval import search_course_chunks_by_hybrid
from app.services.retrieval import (
    CourseNotFoundError,
    EmptySearchQueryError,
    search_course_chunks,
)
from app.services.vector_retrieval import search_course_chunks_by_vector

router = APIRouter(prefix="/courses/{course_id}", tags=["retrieval"])


@router.get("/search", response_model=SearchResponse)
def search_course_endpoint(
    course_id: uuid.UUID,
    query: Annotated[str, Query(min_length=1, max_length=300)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> SearchResponse:
    try:
        results = search_course_chunks(db, course_id=course_id, query=query, limit=limit)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmptySearchQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return SearchResponse(course_id=course_id, query=query, results=results)


@router.get("/search/hybrid", response_model=HybridSearchResponse)
def hybrid_search_course_endpoint(
    course_id: uuid.UUID,
    query: Annotated[str, Query(min_length=1, max_length=300)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> HybridSearchResponse:
    try:
        results = search_course_chunks_by_hybrid(
            db,
            course_id=course_id,
            query=query,
            limit=limit,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmptySearchQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return HybridSearchResponse(course_id=course_id, query=query, results=results)


@router.get("/search/vector", response_model=VectorSearchResponse)
def vector_search_course_endpoint(
    course_id: uuid.UUID,
    query: Annotated[str, Query(min_length=1, max_length=300)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> VectorSearchResponse:
    try:
        results = search_course_chunks_by_vector(
            db,
            course_id=course_id,
            query=query,
            limit=limit,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmptySearchQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return VectorSearchResponse(course_id=course_id, query=query, results=results)
