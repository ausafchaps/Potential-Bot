from pydantic import BaseModel


class StorageAllowance(BaseModel):
    used: int
    limit: int
    remaining: int


class StorageUsage(BaseModel):
    documents: StorageAllowance
    text_bytes: StorageAllowance
    max_file_bytes: int
    max_pdf_pages: int
    max_text_chars: int
    shared_capacity_available: bool
