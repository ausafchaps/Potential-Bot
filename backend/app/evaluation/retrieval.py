import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import Course, Document, DocumentChunk, DocumentStatus, User
from app.services.hybrid_retrieval import search_course_chunks_by_hybrid
from app.services.retrieval import search_course_chunks
from app.services.vector_retrieval import search_course_chunks_by_vector

DEFAULT_RETRIEVAL_DATASET_PATH = Path(__file__).parent / "datasets" / "retrieval_v1.json"
RetrievalMode = Literal["keyword", "vector", "hybrid"]
DEFAULT_RETRIEVAL_COMPARISON_MODES: tuple[RetrievalMode, ...] = (
    "keyword",
    "vector",
    "hybrid",
)


@dataclass(frozen=True)
class RetrievalEvalChunk:
    text: str
    page_number: int | None = None


@dataclass(frozen=True)
class RetrievalEvalDocument:
    filename: str
    chunks: list[RetrievalEvalChunk]
    content_type: str = "text/plain"


@dataclass(frozen=True)
class ExpectedRetrievalResult:
    filename: str
    chunk_index: int | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class RetrievalEvalCase:
    id: str
    query: str
    documents: list[RetrievalEvalDocument]
    expected_results: list[ExpectedRetrievalResult]
    top_k: int = 5


@dataclass(frozen=True)
class RetrievalEvalDataset:
    name: str
    cases: list[RetrievalEvalCase]
    description: str | None = None


@dataclass(frozen=True)
class EvaluatedRetrievedChunk:
    document_filename: str
    chunk_index: int
    page_number: int | None


@dataclass(frozen=True)
class RetrievalCaseResult:
    mode: RetrievalMode
    case_id: str
    query: str
    top_k: int
    passed: bool
    hit_at_k: float
    reciprocal_rank: float
    precision_at_k: float
    expected_results: list[ExpectedRetrievalResult]
    returned_results: list[EvaluatedRetrievedChunk]


@dataclass(frozen=True)
class RetrievalEvalReport:
    mode: RetrievalMode
    dataset: str
    case_count: int
    passed_case_count: int
    hit_at_k: float
    mean_reciprocal_rank: float
    precision_at_k: float
    case_results: list[RetrievalCaseResult]

    @property
    def failed_case_results(self) -> list[RetrievalCaseResult]:
        return [case_result for case_result in self.case_results if not case_result.passed]


@dataclass(frozen=True)
class RetrievalComparisonCaseResult:
    case_id: str
    query: str
    top_k: int
    mode_results: dict[RetrievalMode, RetrievalCaseResult]


@dataclass(frozen=True)
class RetrievalComparisonReport:
    dataset: str
    case_count: int
    modes: list[RetrievalMode]
    mode_reports: dict[RetrievalMode, RetrievalEvalReport]
    case_results: list[RetrievalComparisonCaseResult]
    best_mode_by_hit_at_k: RetrievalMode
    best_mode_by_mrr: RetrievalMode
    best_mode_by_precision_at_k: RetrievalMode


def load_retrieval_eval_dataset(path: Path | None = None) -> RetrievalEvalDataset:
    dataset_path = path or DEFAULT_RETRIEVAL_DATASET_PATH
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return parse_retrieval_eval_dataset(payload)


def parse_retrieval_eval_dataset(payload: dict[str, Any]) -> RetrievalEvalDataset:
    return RetrievalEvalDataset(
        name=payload["name"],
        description=payload.get("description"),
        cases=[parse_retrieval_eval_case(case_payload) for case_payload in payload["cases"]],
    )


def parse_retrieval_eval_case(payload: dict[str, Any]) -> RetrievalEvalCase:
    return RetrievalEvalCase(
        id=payload["id"],
        query=payload["query"],
        top_k=payload.get("top_k", 5),
        documents=[
            RetrievalEvalDocument(
                filename=document_payload["filename"],
                content_type=document_payload.get("content_type", "text/plain"),
                chunks=[
                    RetrievalEvalChunk(
                        text=chunk_payload["text"],
                        page_number=chunk_payload.get("page_number"),
                    )
                    for chunk_payload in document_payload["chunks"]
                ],
            )
            for document_payload in payload["documents"]
        ],
        expected_results=[
            ExpectedRetrievalResult(
                filename=expected_payload["filename"],
                chunk_index=expected_payload.get("chunk_index"),
                page_number=expected_payload.get("page_number"),
            )
            for expected_payload in payload["expected_results"]
        ],
    )


def run_retrieval_evaluation(
    db: Session,
    dataset: RetrievalEvalDataset | None = None,
    mode: RetrievalMode = "keyword",
) -> RetrievalEvalReport:
    eval_dataset = dataset or load_retrieval_eval_dataset()
    case_results = [
        run_retrieval_eval_case(db, case, mode=mode) for case in eval_dataset.cases
    ]
    return build_retrieval_eval_report(
        dataset_name=eval_dataset.name,
        mode=mode,
        case_results=case_results,
    )


def run_retrieval_comparison(
    db: Session,
    dataset: RetrievalEvalDataset | None = None,
    modes: tuple[RetrievalMode, ...] = DEFAULT_RETRIEVAL_COMPARISON_MODES,
) -> RetrievalComparisonReport:
    eval_dataset = dataset or load_retrieval_eval_dataset()
    case_results: list[RetrievalComparisonCaseResult] = []
    mode_case_results: dict[RetrievalMode, list[RetrievalCaseResult]] = {
        mode: [] for mode in modes
    }

    for case in eval_dataset.cases:
        course = seed_retrieval_eval_case(db, case)
        mode_results = {
            mode: run_retrieval_eval_case_for_course(
                db,
                case=case,
                course_id=course.id,
                mode=mode,
            )
            for mode in modes
        }
        for mode, mode_result in mode_results.items():
            mode_case_results[mode].append(mode_result)

        case_results.append(
            RetrievalComparisonCaseResult(
                case_id=case.id,
                query=case.query,
                top_k=case.top_k,
                mode_results=mode_results,
            )
        )

    mode_reports = {
        mode: build_retrieval_eval_report(
            dataset_name=eval_dataset.name,
            mode=mode,
            case_results=case_results_for_mode,
        )
        for mode, case_results_for_mode in mode_case_results.items()
    }

    return RetrievalComparisonReport(
        dataset=eval_dataset.name,
        case_count=len(eval_dataset.cases),
        modes=list(modes),
        mode_reports=mode_reports,
        case_results=case_results,
        best_mode_by_hit_at_k=find_best_mode(mode_reports, "hit_at_k"),
        best_mode_by_mrr=find_best_mode(mode_reports, "mean_reciprocal_rank"),
        best_mode_by_precision_at_k=find_best_mode(mode_reports, "precision_at_k"),
    )


def build_retrieval_eval_report(
    *,
    dataset_name: str,
    mode: RetrievalMode,
    case_results: list[RetrievalCaseResult],
) -> RetrievalEvalReport:
    case_count = len(case_results)
    return RetrievalEvalReport(
        mode=mode,
        dataset=dataset_name,
        case_count=case_count,
        passed_case_count=sum(1 for case_result in case_results if case_result.passed),
        hit_at_k=average(case_result.hit_at_k for case_result in case_results),
        mean_reciprocal_rank=average(
            case_result.reciprocal_rank for case_result in case_results
        ),
        precision_at_k=average(case_result.precision_at_k for case_result in case_results),
        case_results=case_results,
    )


def run_retrieval_eval_case(
    db: Session,
    case: RetrievalEvalCase,
    mode: RetrievalMode = "keyword",
) -> RetrievalCaseResult:
    course = seed_retrieval_eval_case(db, case)
    return run_retrieval_eval_case_for_course(
        db,
        case=case,
        course_id=course.id,
        mode=mode,
    )


def run_retrieval_eval_case_for_course(
    db: Session,
    *,
    case: RetrievalEvalCase,
    course_id: uuid.UUID,
    mode: RetrievalMode,
) -> RetrievalCaseResult:
    returned_results = run_retrieval_for_mode(
        db,
        course_id=course_id,
        query=case.query,
        limit=case.top_k,
        mode=mode,
    )

    if not case.expected_results:
        passed = len(returned_results) == 0
        score = 1.0 if passed else 0.0
        return RetrievalCaseResult(
            mode=mode,
            case_id=case.id,
            query=case.query,
            top_k=case.top_k,
            passed=passed,
            hit_at_k=score,
            reciprocal_rank=score,
            precision_at_k=score,
            expected_results=case.expected_results,
            returned_results=returned_results,
        )

    first_match_rank = first_relevant_rank(returned_results, case.expected_results)
    relevant_count = count_relevant_results(returned_results, case.expected_results)
    passed = first_match_rank is not None

    return RetrievalCaseResult(
        mode=mode,
        case_id=case.id,
        query=case.query,
        top_k=case.top_k,
        passed=passed,
        hit_at_k=1.0 if passed else 0.0,
        reciprocal_rank=1.0 / first_match_rank if first_match_rank is not None else 0.0,
        precision_at_k=relevant_count / case.top_k,
        expected_results=case.expected_results,
        returned_results=returned_results,
    )


def run_retrieval_for_mode(
    db: Session,
    *,
    course_id: uuid.UUID,
    query: str,
    limit: int,
    mode: RetrievalMode,
) -> list[EvaluatedRetrievedChunk]:
    if mode == "keyword":
        results = search_course_chunks(db, course_id=course_id, query=query, limit=limit)
    elif mode == "vector":
        results = search_course_chunks_by_vector(
            db,
            course_id=course_id,
            query=query,
            limit=limit,
        )
    elif mode == "hybrid":
        results = search_course_chunks_by_hybrid(
            db,
            course_id=course_id,
            query=query,
            limit=limit,
        )
    else:
        raise ValueError(f"Unsupported retrieval mode '{mode}'")

    return [
        EvaluatedRetrievedChunk(
            document_filename=result.document_filename,
            chunk_index=result.chunk_index,
            page_number=result.page_number,
        )
        for result in results
    ]


def seed_retrieval_eval_case(db: Session, case: RetrievalEvalCase) -> Course:
    user = User(
        email=f"eval-{case.id}-{uuid.uuid4()}@example.com",
        display_name="Retrieval Eval",
    )
    course = Course(
        title=f"Retrieval eval: {case.id}",
        description="Generated by retrieval evaluation.",
        owner=user,
    )

    for eval_document in case.documents:
        document = Document(
            filename=eval_document.filename,
            content_type=eval_document.content_type,
            status=DocumentStatus.completed,
            page_count=max_page_number(eval_document.chunks),
            course=course,
        )
        for chunk_index, eval_chunk in enumerate(eval_document.chunks):
            document.chunks.append(
                DocumentChunk(
                    chunk_index=chunk_index,
                    text=eval_chunk.text,
                    page_number=eval_chunk.page_number,
                    token_count=len(eval_chunk.text.split()),
                )
            )

    db.add(user)
    db.commit()
    db.refresh(course)
    return course


def max_page_number(chunks: list[RetrievalEvalChunk]) -> int | None:
    page_numbers = [chunk.page_number for chunk in chunks if chunk.page_number is not None]
    if not page_numbers:
        return None
    return max(page_numbers)


def first_relevant_rank(
    returned_results: list[EvaluatedRetrievedChunk],
    expected_results: list[ExpectedRetrievalResult],
) -> int | None:
    for rank, returned_result in enumerate(returned_results, start=1):
        if is_relevant_result(returned_result, expected_results):
            return rank
    return None


def count_relevant_results(
    returned_results: list[EvaluatedRetrievedChunk],
    expected_results: list[ExpectedRetrievalResult],
) -> int:
    return sum(
        1
        for returned_result in returned_results
        if is_relevant_result(returned_result, expected_results)
    )


def is_relevant_result(
    returned_result: Any,
    expected_results: list[ExpectedRetrievalResult],
) -> bool:
    return any(matches_expected_result(returned_result, expected) for expected in expected_results)


def matches_expected_result(
    returned_result: Any,
    expected: ExpectedRetrievalResult,
) -> bool:
    if returned_result.document_filename != expected.filename:
        return False
    if expected.chunk_index is not None and returned_result.chunk_index != expected.chunk_index:
        return False
    if expected.page_number is not None and returned_result.page_number != expected.page_number:
        return False
    return True


def find_best_mode(
    mode_reports: dict[RetrievalMode, RetrievalEvalReport],
    metric_name: Literal["hit_at_k", "mean_reciprocal_rank", "precision_at_k"],
) -> RetrievalMode:
    return max(
        mode_reports,
        key=lambda mode: getattr(mode_reports[mode], metric_name),
    )


def average(values: Any) -> float:
    collected_values = list(values)
    if not collected_values:
        return 0.0
    return sum(collected_values) / len(collected_values)
