"""Runtime configuration. Every setting is an env var with the DOCX86_ prefix (see deploy/k8s)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCX86_", env_file=".env", extra="ignore")

    content_dir: Path = PROJECT_ROOT / "content"
    index_dir: Path = PROJECT_ROOT / "index"

    # "fastembed" = real semantic embeddings (production). "hash" = dependency-free lexical
    # stand-in used by tests; it is NOT semantic and must not be deployed.
    embedder: Literal["fastembed", "hash"] = "fastembed"
    model_name: str = "BAAI/bge-small-en-v1.5"
    model_cache_dir: Path = PROJECT_ROOT / ".cache" / "models"
    # Never touch the network: load the model from model_cache_dir only (set in the image).
    model_offline: bool = False
    # onnxruntime defaults to one thread per *node* core, ignoring the pod CPU limit. Query
    # embedding is tiny, so keep it single-threaded and scale with replicas instead.
    embed_threads: int = 1

    # Dev convenience: rebuild the index at startup when content changed. Leave off in
    # production, where a stale index must fail the rollout rather than silently re-embed.
    rebuild_stale_index: bool = False

    # Local copy of the Intel SDM, used only by `docx86 sdm ...` while authoring content.
    sdm_pdf: Path = PROJECT_ROOT / "docs" / "docs.x86.pdf"

    # Tracing itself is configured with the standard OTEL_* variables (docs/ARCHITECTURE.md). By
    # default spans carry no search text and no client address; this opts in to both.
    trace_user_data: bool = False

    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
