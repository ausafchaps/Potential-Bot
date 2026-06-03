import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import (
    AnswerCitationResponse,
    QuestionAnswerResponse,
    QuestionCreate,
    RetrievedChunkResponse,
)
from app.services.answer_orchestrator import answer_course_question
from app.services.llm.base import LLMProviderConfigurationError, LLMProviderError
from app.services.retrieval import CourseNotFoundError, EmptySearchQueryError

router = APIRouter(prefix="/courses/{course_id}/questions", tags=["questions"])


@router.post("", response_model=QuestionAnswerResponse)
def ask_course_question_endpoint(
    course_id: uuid.UUID,
    payload: QuestionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> QuestionAnswerResponse:
    try:
        result = answer_course_question(
            db,
            course_id=course_id,
            question_text=payload.question,
            limit=payload.limit,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmptySearchQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except LLMProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return QuestionAnswerResponse(
        status=result.status,
        question_id=result.question.id,
        answer_id=result.answer.id,
        answer=result.answer.text,
        provider=result.answer.provider,
        citations=[
            AnswerCitationResponse.model_validate(citation)
            for citation in result.citations
        ],
        retrieved_chunks=[
            RetrievedChunkResponse(
                document_id=chunk.document_id,
                document_filename=chunk.document_filename,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
                score=chunk.score,
                matched_terms=chunk.matched_terms,
            )
            for chunk in result.retrieved_chunks
        ],
        created_at=result.answer.created_at,
    )
