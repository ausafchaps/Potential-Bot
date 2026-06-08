import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Course,
    Quiz,
    QuizCitation,
    QuizQuestion,
    QuizQuestionOption,
    QuizStatus,
)
from app.schemas.quiz import QuizCreate
from app.services.answer_orchestrator import (
    GroundedEvidenceChunk,
    build_grounded_prompt,
    get_grounded_evidence_chunks,
)
from app.services.llm.base import LLMProvider, LLMRequest
from app.services.llm.factory import get_llm_provider
from app.services.retrieval import CourseNotFoundError


class QuizNotFoundError(ValueError):
    pass


class QuizGenerationError(ValueError):
    pass


@dataclass(frozen=True)
class GeneratedQuizOption:
    text: str
    is_correct: bool


@dataclass(frozen=True)
class GeneratedQuizQuestion:
    question: str
    options: list[GeneratedQuizOption]
    explanation: str


@dataclass(frozen=True)
class GeneratedQuiz:
    title: str
    questions: list[GeneratedQuizQuestion]


def create_course_quiz(
    db: Session,
    *,
    course_id: uuid.UUID,
    payload: QuizCreate,
    provider: LLMProvider | None = None,
) -> Quiz:
    resolved_provider = provider or get_llm_provider()
    evidence_chunks = get_grounded_evidence_chunks(
        db,
        course_id=course_id,
        query=payload.topic,
        limit=payload.limit,
    )

    if not evidence_chunks:
        quiz = Quiz(
            course_id=course_id,
            topic=payload.topic,
            title=None,
            difficulty=payload.difficulty,
            status=QuizStatus.insufficient_evidence,
            provider=resolved_provider.provider_name,
            prompt=None,
        )
        db.add(quiz)
        db.commit()
        return get_quiz(db, quiz.id)

    prompt = build_quiz_prompt(payload, evidence_chunks)
    generated_quiz = generate_quiz_from_evidence(
        provider=resolved_provider,
        payload=payload,
        prompt=prompt,
        evidence_chunks=evidence_chunks,
    )
    quiz = Quiz(
        course_id=course_id,
        topic=payload.topic,
        title=generated_quiz.title,
        difficulty=payload.difficulty,
        status=QuizStatus.generated,
        provider=resolved_provider.provider_name,
        prompt=prompt,
    )
    db.add(quiz)
    db.flush()

    for question_position, generated_question in enumerate(generated_quiz.questions, start=1):
        quiz_question = QuizQuestion(
            quiz_id=quiz.id,
            position=question_position,
            question_text=generated_question.question,
            explanation=generated_question.explanation,
        )
        db.add(quiz_question)
        db.flush()

        for option_position, generated_option in enumerate(generated_question.options, start=1):
            db.add(
                QuizQuestionOption(
                    quiz_question_id=quiz_question.id,
                    position=option_position,
                    text=generated_option.text,
                    is_correct=generated_option.is_correct,
                )
            )

        citation_chunk = evidence_chunks[min(question_position - 1, len(evidence_chunks) - 1)]
        db.add(
            QuizCitation(
                quiz_question_id=quiz_question.id,
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
    return get_quiz(db, quiz.id)


def generate_quiz_from_evidence(
    *,
    provider: LLMProvider,
    payload: QuizCreate,
    prompt: str,
    evidence_chunks: list[GroundedEvidenceChunk],
) -> GeneratedQuiz:
    if provider.provider_name == "fake":
        return generate_fake_quiz(payload, evidence_chunks)

    response = provider.generate_answer(
        LLMRequest(
            question=f"Generate a quiz about {payload.topic}",
            prompt=prompt,
            context_chunks=evidence_chunks,  # type: ignore[arg-type]
        )
    )
    return parse_generated_quiz_json(response.text, question_count=payload.question_count)


def generate_fake_quiz(
    payload: QuizCreate,
    evidence_chunks: list[GroundedEvidenceChunk],
) -> GeneratedQuiz:
    questions = [
        GeneratedQuizQuestion(
            question=f"According to the study material, what is important about {payload.topic}?",
            options=[
                GeneratedQuizOption(text=evidence_chunks[0].text, is_correct=True),
                GeneratedQuizOption(
                    text="It is unrelated to the provided material.",
                    is_correct=False,
                ),
                GeneratedQuizOption(
                    text="It only appears in unsupported outside sources.",
                    is_correct=False,
                ),
                GeneratedQuizOption(
                    text="It cannot be studied from course notes.",
                    is_correct=False,
                ),
            ],
            explanation=(
                "The correct option is drawn directly from the retrieved study material."
            ),
        )
    ]

    for index in range(2, payload.question_count + 1):
        chunk = evidence_chunks[(index - 1) % len(evidence_chunks)]
        questions.append(
            GeneratedQuizQuestion(
                question=f"Which source detail best supports {payload.topic}? ({index})",
                options=[
                    GeneratedQuizOption(text=chunk.text, is_correct=True),
                    GeneratedQuizOption(
                        text="A detail not present in the uploaded notes.",
                        is_correct=False,
                    ),
                    GeneratedQuizOption(
                        text="A claim without a course citation.",
                        is_correct=False,
                    ),
                    GeneratedQuizOption(
                        text="A general answer with no source evidence.",
                        is_correct=False,
                    ),
                ],
                explanation="This option is supported by the cited chunk.",
            )
        )

    return GeneratedQuiz(title=f"{payload.topic.title()} Quiz", questions=questions)


def build_quiz_prompt(payload: QuizCreate, chunks: list[GroundedEvidenceChunk]) -> str:
    grounded_prompt = build_grounded_prompt(payload.topic, chunks)
    return (
        "Generate a multiple-choice study quiz using only the provided study material.\n"
        f"Difficulty: {payload.difficulty.value}\n"
        f"Question count: {payload.question_count}\n"
        "Return valid JSON only with this shape:\n"
        "{\n"
        '  "title": "Quiz title",\n'
        '  "questions": [\n'
        "    {\n"
        '      "question": "Question text",\n'
        '      "options": [\n'
        '        {"text": "Option text", "is_correct": true}\n'
        "      ],\n"
        '      "explanation": "Why the correct answer is supported"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"{grounded_prompt}"
    )


def parse_generated_quiz_json(text: str, *, question_count: int) -> GeneratedQuiz:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QuizGenerationError("Quiz provider returned invalid JSON") from exc

    try:
        title = str(payload["title"]).strip()
        questions_payload = payload["questions"]
    except (KeyError, TypeError) as exc:
        raise QuizGenerationError("Quiz provider response is missing quiz fields") from exc

    if not title:
        raise QuizGenerationError("Quiz provider returned an empty title")
    if not isinstance(questions_payload, list) or len(questions_payload) < question_count:
        raise QuizGenerationError("Quiz provider returned too few questions")

    return GeneratedQuiz(
        title=title,
        questions=[
            parse_generated_question(question_payload)
            for question_payload in questions_payload[:question_count]
        ],
    )


def parse_generated_question(payload: dict[str, Any]) -> GeneratedQuizQuestion:
    try:
        question = str(payload["question"]).strip()
        explanation = str(payload["explanation"]).strip()
        options_payload = payload["options"]
    except (KeyError, TypeError) as exc:
        raise QuizGenerationError("Quiz provider response is missing question fields") from exc

    if not question or not explanation:
        raise QuizGenerationError("Quiz provider returned empty question fields")
    if not isinstance(options_payload, list) or len(options_payload) < 2:
        raise QuizGenerationError("Quiz provider returned too few options")

    options = [parse_generated_option(option_payload) for option_payload in options_payload]
    if sum(1 for option in options if option.is_correct) != 1:
        raise QuizGenerationError("Quiz question must have exactly one correct option")

    return GeneratedQuizQuestion(
        question=question,
        options=options,
        explanation=explanation,
    )


def parse_generated_option(payload: dict[str, Any]) -> GeneratedQuizOption:
    try:
        text = str(payload["text"]).strip()
        is_correct = bool(payload["is_correct"])
    except (KeyError, TypeError) as exc:
        raise QuizGenerationError("Quiz provider response is missing option fields") from exc

    if not text:
        raise QuizGenerationError("Quiz provider returned an empty option")

    return GeneratedQuizOption(text=text, is_correct=is_correct)


def list_course_quizzes(db: Session, course_id: uuid.UUID) -> list[Quiz]:
    if db.get(Course, course_id) is None:
        raise CourseNotFoundError("Course was not found")

    return list(
        db.scalars(
            select(Quiz)
            .where(Quiz.course_id == course_id)
            .order_by(Quiz.created_at.desc(), Quiz.id.desc())
        )
    )


def get_quiz(db: Session, quiz_id: uuid.UUID) -> Quiz:
    quiz = db.scalar(
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(
            selectinload(Quiz.questions)
            .selectinload(QuizQuestion.options),
            selectinload(Quiz.questions)
            .selectinload(QuizQuestion.citations),
        )
    )
    if quiz is None:
        raise QuizNotFoundError("Quiz was not found")
    return quiz
