# 0013 Real LLM Provider Integration

## Status

Accepted

## Context

StudyBot already has a grounded answer orchestrator and deterministic fake LLM
provider. The project now needs a way to generate real model answers without
rewriting retrieval, prompt construction, citation persistence, or tests.

## Decision

Add a provider factory and a Groq provider behind the existing LLM provider
interface.

The module includes:

- environment-driven provider selection
- `fake` as the default provider
- `groq` as the first real provider
- API key support through `LLM_API_KEY` or `GROQ_API_KEY`
- model override through `LLM_MODEL`
- default model: `llama-3.1-8b-instant`
- OpenAI-compatible chat completions request handling
- provider configuration errors surfaced as `503`
- provider runtime errors surfaced as `502`
- mocked HTTP tests instead of real external API calls

Streaming, provider fallback, token/cost tracking, multiple real providers, and
frontend model selection remain out of scope.

## Consequences

The app can now run the same grounded question flow with either deterministic
fake answers or real Groq answers. Tests remain free and deterministic, while
local users can opt into real LLM output with environment variables.
