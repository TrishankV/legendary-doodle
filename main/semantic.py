from functools import lru_cache
from typing import Iterable

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = (
    "sentence-transformers/"
    "all-MiniLM-L6-v2"
)


class SemanticModel:
    """
    Lightweight semantic embedding model.

    This is intentionally provider-independent from the splitter.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
    ):
        self.model_name = model_name

        self.model = SentenceTransformer(
            model_name
        )

    def embed(
        self,
        texts: Iterable[str],
    ) -> np.ndarray:
        """
        Create normalized sentence embeddings.
        """

        texts = list(texts)

        if not texts:
            return np.empty(
                (0, 384),
                dtype=np.float32,
            )

        return self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def similarity(
        self,
        query: str,
        texts: Iterable[str],
    ) -> np.ndarray:
        """
        Compare a query against multiple texts.
        """

        text_embeddings = self.embed(
            texts
        )

        query_embedding = self.embed(
            [query]
        )[0]

        return np.dot(
            text_embeddings,
            query_embedding,
        )


@lru_cache(maxsize=1)
def get_semantic_model() -> SemanticModel:
    """
    Reuse one model instance within the process.
    """

    return SemanticModel()