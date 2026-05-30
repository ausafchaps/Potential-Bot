from app.services.llm.base import LLMRequest, LLMResponse


class FakeLLMProvider:
    provider_name = "fake"

    def generate_answer(self, request: LLMRequest) -> LLMResponse:
        if not request.context_chunks:
            return LLMResponse(text="I could not find enough source material to answer.")

        first_chunk = request.context_chunks[0]
        answer = (
            "Based on the provided study material: "
            f"{first_chunk.text.strip()} [1]"
        )
        return LLMResponse(text=answer)

