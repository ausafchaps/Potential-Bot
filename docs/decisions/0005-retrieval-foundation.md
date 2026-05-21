# 0005 Retrieval Foundation

## Status

Accepted

## Context

StudyBot can create users and courses, ingest plain text documents, and persist
document chunks. The next step is to make those chunks searchable before adding
LLM answers. This gives the project an inspectable retrieval baseline.

## Decision

Add course-scoped keyword retrieval.

The first retrieval module includes:

- `GET /courses/{course_id}/search`
- query tokenization and normalization
- simple term-frequency scoring
- completed-document filtering
- course-level isolation
- source metadata in each search result
- configurable result limit

Embeddings, vector search, hybrid search, reranking, and answer generation remain
out of scope.

## Consequences

Keyword retrieval is easy to inspect, test, and compare against future semantic
retrieval. It will miss synonyms and conceptually related text when words do not
overlap, but it gives us the first complete non-LLM study material loop:

```text
create user -> create course -> upload text -> search chunks
```

