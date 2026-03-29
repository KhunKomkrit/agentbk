"""Sentence-transformer embedder — lazy singleton, multilingual (Thai-compatible)."""
from __future__ import annotations
import logging
import os
import warnings
from typing import TYPE_CHECKING

# Suppress noisy output from HuggingFace Hub / transformers before any import.
# Must be set at module level (before huggingface_hub is imported).
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_model: "SentenceTransformer | None" = None
_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def get_embedder() -> "SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a list of strings."""
    model = get_embedder()
    vecs = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [v.tolist() for v in vecs]
