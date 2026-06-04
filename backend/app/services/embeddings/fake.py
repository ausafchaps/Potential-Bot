import hashlib
import math
import re

from app.services.embeddings.base import EmbeddingProvider

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

CANONICAL_TERMS = {
    "fast": "speed",
    "faster": "speed",
    "quick": "speed",
    "quickly": "speed",
    "rapid": "speed",
    "lookup": "search",
    "lookups": "search",
    "retrieval": "search",
    "retrieve": "search",
    "find": "search",
    "finds": "search",
    "finding": "search",
    "ordered": "sorted",
    "list": "array",
    "lists": "array",
}


class FakeEmbeddingProvider(EmbeddingProvider):
    provider_name = "fake"
    model_name = "fake-token-hash-v1"
    dimensions = 24

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize_for_embedding(text):
            index = stable_bucket(token, self.dimensions)
            vector[index] += 1.0

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector

        return [value / magnitude for value in vector]


def tokenize_for_embedding(text: str) -> list[str]:
    return [
        CANONICAL_TERMS.get(token, token)
        for token in TOKEN_PATTERN.findall(text.lower())
    ]


def stable_bucket(token: str, dimensions: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big") % dimensions

