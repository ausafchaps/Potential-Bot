import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Course,
    Flashcard,
    FlashcardCitation,
    FlashcardSet,
    FlashcardSetStatus,
)
from app.schemas.flashcard import FlashcardSetCreate
from app.services.answer_orchestrator import (
    GroundedEvidenceChunk,
    build_grounded_prompt,
    get_grounded_evidence_chunks,
)
from app.services.llm.base import LLMProvider, LLMRequest
from app.services.llm.factory import get_llm_provider
from app.services.retrieval import CourseNotFoundError


class FlashcardSetNotFoundError(ValueError):
    pass


class FlashcardGenerationError(ValueError):
    pass


@dataclass(frozen=True)
class GeneratedFlashcard:
    front: str
    back: str


@dataclass(frozen=True)
class GeneratedFlashcardSet:
    title: str
    cards: list[GeneratedFlashcard]


def create_course_flashcard_set(
    db: Session,
    *,
    course_id: uuid.UUID,
    payload: FlashcardSetCreate,
    provider: LLMProvider | None = None,
) -> FlashcardSet:
    resolved_provider = provider or get_llm_provider()
    evidence_chunks = get_grounded_evidence_chunks(
        db,
        course_id=course_id,
        query=payload.topic,
        limit=payload.limit,
    )

    if not evidence_chunks:
        flashcard_set = FlashcardSet(
            course_id=course_id,
            topic=payload.topic,
            title=None,
            difficulty=payload.difficulty,
            status=FlashcardSetStatus.insufficient_evidence,
            provider=resolved_provider.provider_name,
            prompt=None,
        )
        db.add(flashcard_set)
        db.commit()
        return get_flashcard_set(db, flashcard_set.id)

    prompt = build_flashcard_prompt(payload, evidence_chunks)
    generated_set = generate_flashcards_from_evidence(
        provider=resolved_provider,
        payload=payload,
        prompt=prompt,
        evidence_chunks=evidence_chunks,
    )
    flashcard_set = FlashcardSet(
        course_id=course_id,
        topic=payload.topic,
        title=generated_set.title,
        difficulty=payload.difficulty,
        status=FlashcardSetStatus.generated,
        provider=resolved_provider.provider_name,
        prompt=prompt,
    )
    db.add(flashcard_set)
    db.flush()

    for card_position, generated_card in enumerate(generated_set.cards, start=1):
        flashcard = Flashcard(
            flashcard_set_id=flashcard_set.id,
            position=card_position,
            front=generated_card.front,
            back=generated_card.back,
        )
        db.add(flashcard)
        db.flush()

        citation_chunk = evidence_chunks[min(card_position - 1, len(evidence_chunks) - 1)]
        db.add(
            FlashcardCitation(
                flashcard_id=flashcard.id,
                document_id=citation_chunk.document_id,
                chunk_id=citation_chunk.chunk_id,
                position=1,
                document_filename=citation_chunk.document_filename,
                chunk_index=citation_chunk.chunk_index,
                page_number=citation_chunk.page_number,
                text=citation_chunk.text,
            )
        )

    db.commit()
    return get_flashcard_set(db, flashcard_set.id)


def generate_flashcards_from_evidence(
    *,
    provider: LLMProvider,
    payload: FlashcardSetCreate,
    prompt: str,
    evidence_chunks: list[GroundedEvidenceChunk],
) -> GeneratedFlashcardSet:
    if provider.provider_name == "fake":
        return generate_fake_flashcards(payload, evidence_chunks)

    response = provider.generate_answer(
        LLMRequest(
            question=f"Generate flashcards about {payload.topic}",
            prompt=prompt,
            context_chunks=evidence_chunks,  # type: ignore[arg-type]
        )
    )
    return parse_generated_flashcards_json(response.text, card_count=payload.card_count)


def generate_fake_flashcards(
    payload: FlashcardSetCreate,
    evidence_chunks: list[GroundedEvidenceChunk],
) -> GeneratedFlashcardSet:
    cards: list[GeneratedFlashcard] = []
    for index in range(1, payload.card_count + 1):
        chunk = evidence_chunks[(index - 1) % len(evidence_chunks)]
        cards.append(
            GeneratedFlashcard(
                front=f"What should you remember about {payload.topic}? ({index})",
                back=chunk.text,
            )
        )

    return GeneratedFlashcardSet(
        title=f"{payload.topic.title()} Flashcards",
        cards=cards,
    )


def build_flashcard_prompt(
    payload: FlashcardSetCreate,
    chunks: list[GroundedEvidenceChunk],
) -> str:
    grounded_prompt = build_grounded_prompt(payload.topic, chunks)
    return (
        "Generate study flashcards using only the provided study material.\n"
        f"Difficulty: {payload.difficulty.value}\n"
        f"Card count: {payload.card_count}\n"
        "Return valid JSON only with this shape:\n"
        "{\n"
        '  "title": "Flashcard set title",\n'
        '  "cards": [\n'
        "    {\n"
        '      "front": "Question or prompt",\n'
        '      "back": "Answer supported by the material"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"{grounded_prompt}"
    )


def parse_generated_flashcards_json(
    text: str,
    *,
    card_count: int,
) -> GeneratedFlashcardSet:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FlashcardGenerationError("Flashcard provider returned invalid JSON") from exc

    try:
        title = str(payload["title"]).strip()
        cards_payload = payload["cards"]
    except (KeyError, TypeError) as exc:
        raise FlashcardGenerationError("Flashcard provider response is missing fields") from exc

    if not title:
        raise FlashcardGenerationError("Flashcard provider returned an empty title")
    if not isinstance(cards_payload, list) or len(cards_payload) < card_count:
        raise FlashcardGenerationError("Flashcard provider returned too few cards")

    return GeneratedFlashcardSet(
        title=title,
        cards=[
            parse_generated_flashcard(card_payload)
            for card_payload in cards_payload[:card_count]
        ],
    )


def parse_generated_flashcard(payload: dict[str, Any]) -> GeneratedFlashcard:
    try:
        front = str(payload["front"]).strip()
        back = str(payload["back"]).strip()
    except (KeyError, TypeError) as exc:
        raise FlashcardGenerationError(
            "Flashcard provider response is missing card fields"
        ) from exc

    if not front or not back:
        raise FlashcardGenerationError("Flashcard provider returned empty card fields")

    return GeneratedFlashcard(front=front, back=back)


def list_course_flashcard_sets(db: Session, course_id: uuid.UUID) -> list[FlashcardSet]:
    if db.get(Course, course_id) is None:
        raise CourseNotFoundError("Course was not found")

    return list(
        db.scalars(
            select(FlashcardSet)
            .where(FlashcardSet.course_id == course_id)
            .order_by(FlashcardSet.created_at.desc(), FlashcardSet.id.desc())
        )
    )


def get_flashcard_set(db: Session, flashcard_set_id: uuid.UUID) -> FlashcardSet:
    flashcard_set = db.scalar(
        select(FlashcardSet)
        .where(FlashcardSet.id == flashcard_set_id)
        .options(selectinload(FlashcardSet.cards).selectinload(Flashcard.citations))
    )
    if flashcard_set is None:
        raise FlashcardSetNotFoundError("Flashcard set was not found")
    return flashcard_set
