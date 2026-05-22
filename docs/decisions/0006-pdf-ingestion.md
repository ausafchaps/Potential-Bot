# 0006 PDF Ingestion

## Status

Accepted

## Context

StudyBot can ingest plain text files and search persisted chunks. Real student
material is often distributed as PDFs, so the ingestion layer should support
text-based PDFs before moving into LLM answers.

## Decision

Use `pypdf` for the first PDF ingestion module.

The module includes:

- shared ingestion helpers for chunking, token estimates, status transitions, and
  chunk persistence
- `POST /courses/{course_id}/documents/pdf`
- page-by-page PDF text extraction with `PdfReader` and `page.extract_text()`
- persisted `page_count` on documents
- persisted `page_number` on chunks
- retrieval responses that include `page_number`

Scanned PDFs and OCR are out of scope.

## Consequences

This makes StudyBot useful with text-based course PDFs while keeping ingestion
simple and testable. It will not extract text from image-only or scanned PDFs;
those require a later OCR pipeline.

