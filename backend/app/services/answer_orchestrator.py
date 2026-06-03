import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Answer, AnswerStatus, Citation, Question
from app.services.llm.base import LLMProvider, LLMRequest
from app.services.llm.factory import get_llm_provider
from app.services.retrieval import RankedChunk, search_course_chunks


@dataclass(frozen=True)
class GroundedAnswerResult:
    status: AnswerStatus
    question: Question
    answer: Answer
    citations: list[Citation]
    retrieved_chunks: list[RankedChunk]


def build_grounded_prompt(question: str, chunks: list[RankedChunk]) -> str:
    context_lines = []
    for index, chunk in enumerate(chunks, start=1):
        page = f", page {chunk.page_number}" if chunk.page_number is not None else ""
        context_lines.append(
            f"[{index}] {chunk.document_filename}{page}, chunk {chunk.chunk_index}:\n{chunk.text}"
        )

    context = "\n\n".join(context_lines)
    return (
        "Answer the student's question using only the provided study material.\n"
        "If the material is insufficient, say that the source material does not contain enough "
        "information.\n"
        "Use citation markers like [1] when referring to sources.\n\n"
        f"Question:\n{question}\n\n"
        f"Study material:\n{context}"
    )


def answer_course_question(
    db: Session,
    *,
    course_id: uuid.UUID,
    question_text: str,
    limit: int = 5,
    provider: LLMProvider | None = None,
) -> GroundedAnswerResult:
    provider = provider or get_llm_provider()
    retrieved_chunks = search_course_chunks(
        db,
        course_id=course_id,
        query=question_text,
        limit=limit,
    )

    question = Question(course_id=course_id, text=question_text)
    db.add(question)
    db.flush()

    if not retrieved_chunks:
        answer = Answer(
            question_id=question.id,
            status=AnswerStatus.insufficient_evidence,
            text=None,
            provider=provider.provider_name,
            prompt=None,
        )
        db.add(answer)
        db.commit()
        db.refresh(question)
        db.refresh(answer)
        return GroundedAnswerResult(
            status=AnswerStatus.insufficient_evidence,
            question=question,
            answer=answer,
            citations=[],
            retrieved_chunks=[],
        )

    prompt = build_grounded_prompt(question_text, retrieved_chunks)
    llm_response = provider.generate_answer(
        LLMRequest(question=question_text, prompt=prompt, context_chunks=retrieved_chunks)
    )
    answer = Answer(
        question_id=question.id,
        status=AnswerStatus.answered,
        text=llm_response.text,
        provider=provider.provider_name,
        prompt=prompt,
    )
    db.add(answer)
    db.flush()

    citations: list[Citation] = []
    for position, chunk in enumerate(retrieved_chunks, start=1):
        citation = Citation(
            answer_id=answer.id,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            position=position,
            document_filename=chunk.document_filename,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            text=chunk.text,
        )
        db.add(citation)
        citations.append(citation)

    db.commit()
    db.refresh(question)
    db.refresh(answer)
    for citation in citations:
        db.refresh(citation)

    return GroundedAnswerResult(
        status=AnswerStatus.answered,
        question=question,
        answer=answer,
        citations=citations,
        retrieved_chunks=retrieved_chunks,
    )
