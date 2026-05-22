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
