import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.embeddings.base import EmbeddingProvider
from app.services.retrieval import RankedChunk, search_course_chunks
from app.services.vector_retrieval import VectorRankedChunk, search_course_chunks_by_vector

DEFAULT_KEYWORD_WEIGHT = 0.45
DEFAULT_VECTOR_WEIGHT = 0.55
HYBRID_CANDIDATE_MULTIPLIER = 4
MIN_HYBRID_CANDIDATES = 20


@dataclass(frozen=True)
class HybridRankedChunk:
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    text: str
    hybrid_score: float
    keyword_score: int
    keyword_score_normalized: float
    vector_similarity: float
    vector_similarity_normalized: float
    matched_terms: list[str]
    retrieval_sources: list[str]


@dataclass
class HybridChunkAccumulator:
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    text: str
    keyword_score: int = 0
    vector_similarity: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    retrieval_sources: set[str] = field(default_factory=set)


def search_course_chunks_by_hybrid(
    db: Session,
    *,
    course_id: uuid.UUID,
    query: str,
    limit: int = 5,
    keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
    vector_weight: float = DEFAULT_VECTOR_WEIGHT,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[HybridRankedChunk]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    validate_hybrid_weights(keyword_weight=keyword_weight, vector_weight=vector_weight)

    candidate_limit = max(limit * HYBRID_CANDIDATE_MULTIPLIER, MIN_HYBRID_CANDIDATES)
    keyword_results = search_course_chunks(
        db,
        course_id=course_id,
        query=query,
        limit=candidate_limit,
    )
    vector_results = search_course_chunks_by_vector(
        db,
        course_id=course_id,
        query=query,
        limit=candidate_limit,
        provider=embedding_provider,
    )

    max_keyword_score = max((result.score for result in keyword_results), default=0)
    max_vector_similarity = max((result.similarity for result in vector_results), default=0.0)
    merged_results = merge_hybrid_candidates(keyword_results, vector_results)

    ranked_results = [
        build_hybrid_ranked_chunk(
            accumulator,
            max_keyword_score=max_keyword_score,
            max_vector_similarity=max_vector_similarity,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
        )
        for accumulator in merged_results.values()
    ]

    return sorted(
        ranked_results,
        key=lambda result: (
            -result.hybrid_score,
            -result.keyword_score_normalized,
            -result.vector_similarity_normalized,
            result.document_filename,
            result.chunk_index,
        ),
    )[:limit]


def validate_hybrid_weights(*, keyword_weight: float, vector_weight: float) -> None:
    if keyword_weight < 0 or vector_weight < 0:
        raise ValueError("Hybrid retrieval weights must be zero or greater")
    if keyword_weight + vector_weight <= 0:
        raise ValueError("At least one hybrid retrieval weight must be greater than zero")


def merge_hybrid_candidates(
    keyword_results: list[RankedChunk],
    vector_results: list[VectorRankedChunk],
) -> dict[uuid.UUID, HybridChunkAccumulator]:
    merged_results: dict[uuid.UUID, HybridChunkAccumulator] = {}

    for keyword_result in keyword_results:
        accumulator = get_or_create_keyword_accumulator(merged_results, keyword_result)
        accumulator.keyword_score = keyword_result.score
        accumulator.matched_terms = keyword_result.matched_terms
        accumulator.retrieval_sources.add("keyword")

    for vector_result in vector_results:
        accumulator = get_or_create_vector_accumulator(merged_results, vector_result)
        accumulator.vector_similarity = vector_result.similarity
        accumulator.retrieval_sources.add("vector")

    return merged_results


def get_or_create_keyword_accumulator(
    merged_results: dict[uuid.UUID, HybridChunkAccumulator],
    result: RankedChunk,
) -> HybridChunkAccumulator:
    if result.chunk_id not in merged_results:
        merged_results[result.chunk_id] = HybridChunkAccumulator(
            document_id=result.document_id,
            document_filename=result.document_filename,
            chunk_id=result.chunk_id,
            chunk_index=result.chunk_index,
            page_number=result.page_number,
            text=result.text,
        )
    return merged_results[result.chunk_id]


def get_or_create_vector_accumulator(
    merged_results: dict[uuid.UUID, HybridChunkAccumulator],
    result: VectorRankedChunk,
) -> HybridChunkAccumulator:
    if result.chunk_id not in merged_results:
        merged_results[result.chunk_id] = HybridChunkAccumulator(
            document_id=result.document_id,
            document_filename=result.document_filename,
            chunk_id=result.chunk_id,
            chunk_index=result.chunk_index,
            page_number=result.page_number,
            text=result.text,
        )
    return merged_results[result.chunk_id]


def build_hybrid_ranked_chunk(
    accumulator: HybridChunkAccumulator,
    *,
    max_keyword_score: int,
    max_vector_similarity: float,
    keyword_weight: float,
    vector_weight: float,
) -> HybridRankedChunk:
    keyword_score_normalized = normalize_score(accumulator.keyword_score, max_keyword_score)
    vector_similarity_normalized = normalize_score(
        accumulator.vector_similarity,
        max_vector_similarity,
    )
    hybrid_score = (
        keyword_weight * keyword_score_normalized
        + vector_weight * vector_similarity_normalized
    )

    return HybridRankedChunk(
        document_id=accumulator.document_id,
        document_filename=accumulator.document_filename,
        chunk_id=accumulator.chunk_id,
        chunk_index=accumulator.chunk_index,
        page_number=accumulator.page_number,
        text=accumulator.text,
        hybrid_score=hybrid_score,
        keyword_score=accumulator.keyword_score,
        keyword_score_normalized=keyword_score_normalized,
        vector_similarity=accumulator.vector_similarity,
        vector_similarity_normalized=vector_similarity_normalized,
        matched_terms=accumulator.matched_terms,
        retrieval_sources=sorted(accumulator.retrieval_sources),
    )


def normalize_score(score: float, max_score: float) -> float:
    if max_score <= 0:
        return 0.0
    return score / max_score
