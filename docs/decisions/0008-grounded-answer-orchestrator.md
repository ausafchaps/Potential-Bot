# 0008 Grounded Answer Orchestrator

## Status

Accepted

## Context

StudyBot can ingest course material, inspect documents and chunks, and search
chunks. The next step is to test the AI-shaped product loop without committing
to a paid provider.

## Decision

Add a grounded answer orchestrator with a provider interface and fake LLM
provider.

The module includes:

- `POST /courses/{course_id}/questions`
- `Question`, `Answer`, and `Citation` tables
- provider interface under `app.services.llm`
- deterministic `FakeLLMProvider`
- prompt construction in the orchestrator service
- keyword retrieval as the evidence source
- structured citations and retrieved chunk metadata in the response
- `200` responses with `insufficient_evidence` when no source chunks match

Real providers such as Groq, Gemini, OpenAI, DeepSeek, or Claude are out of
scope for this module.

## Consequences

This lets the project validate the end-to-end answer flow for free while keeping
tests deterministic. The fake provider is not meant to represent final answer
quality; it proves retrieval, prompt construction, answer persistence, and
citation wiring.

