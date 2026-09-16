import math

from cognitive_os.infrastructure.ai.openai_drafts import OpenAIDraftProvider


def validate_vectors(vectors, count):
    if len(vectors) != count:
        raise ValueError("Embedding count mismatch")
    for vector in vectors:
        if (len(vector) != 1536 or not all(math.isfinite(value) for value in vector)
                or sum(value * value for value in vector) <= 0):
            raise ValueError("Invalid embedding")
    return vectors


class OpenAIEmbeddingProvider(OpenAIDraftProvider):
    def __init__(self, settings):
        super().__init__(settings)
        self.model_name = settings.openai_embedding_model

    def embed(self, texts):
        result = []
        for offset in range(0, len(texts), 16):
            batch = texts[offset:offset + 16]
            if any(not value.strip() or len(value.encode("utf-8")) > 6000 for value in batch):
                raise ValueError("Embedding input outside limits")
            response = self.client.embeddings.create(model=self.model_name, input=batch,
                                                       dimensions=1536, encoding_format="float")
            items = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in items] != list(range(len(batch))):
                raise ValueError("Embedding indices mismatch")
            result.extend(validate_vectors([item.embedding for item in items], len(batch)))
        return result
