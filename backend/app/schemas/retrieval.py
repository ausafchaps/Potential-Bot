import uuid

from pydantic import BaseModel, ConfigDict


class SearchResult(BaseModel):
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    text: str
    score: int
    matched_terms: list[str]

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    course_id: uuid.UUID
    query: str
    results: list[SearchResult]


class VectorSearchResult(BaseModel):
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    text: str
    similarity: float
    embedding_provider: str
    embedding_model: str

    model_config = ConfigDict(from_attributes=True)


class VectorSearchResponse(BaseModel):
    course_id: uuid.UUID
    query: str
    results: list[VectorSearchResult]


class HybridSearchResult(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


class HybridSearchResponse(BaseModel):
    course_id: uuid.UUID
    query: str
    results: list[HybridSearchResult]
