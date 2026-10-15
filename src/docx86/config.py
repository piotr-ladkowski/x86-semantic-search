"""Runtime configuration. Every setting is an env var with the DOCX86_ prefix (see deploy/k8s)."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import field_validator
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

    # Relevance floor: a result whose score (cosine similarity plus the mnemonic boost) is below
    # this is labelled a weak match, and the site says "no good match" when nothing clears it.
    # Measured on 2026-10-08 for the default model with 32 pages: every expected eval page scored
    # 0.649 or more, off-topic queries ("weather tomorrow in berlin") 0.62 or less. x86 queries
    # that are out of scope score far higher (0.71-0.88) and are handled by `scope.py` instead.
    # `docx86 eval` prints the current margin; re-measure after changing the model or the
    # search units. The hash embedder's scores are lexical and not comparable (tests use 0).
    search_floor: float = 0.64

    # Local copy of the Intel SDM, used only by `docx86 sdm ...` while authoring content.
    sdm_pdf: Path = PROJECT_ROOT / "docs" / "docs.x86.pdf"
    # Local copy of the Wikibooks x86 Assembly print version, used only by `docx86 wiki ...`.
    wikibooks_html: Path = PROJECT_ROOT / "docs" / "wikibooks_x86.html"
    # More local reference copies, read only by the evidence tooling (see docs/EVIDENCE.md).
    # Their extracted sentences are cached under cache_dir (safe to delete).
    sysv_abi_pdf: Path = PROJECT_ROOT / "docs" / "sysv_abi.pdf"
    ms_calling_convention_html: Path = PROJECT_ROOT / "docs" / "ms_x64_calling_convention.html"
    ms_stack_usage_html: Path = PROJECT_ROOT / "docs" / "ms_x64_stack_usage.html"
    cache_dir: Path = PROJECT_ROOT / ".cache"

    # Tracing itself is configured with the standard OTEL_* variables (docs/ARCHITECTURE.md). By
    # default spans carry no search text and no client address; this opts in to both.
    trace_user_data: bool = False

    # Which version is running (see build.py): set by the image build from CI build arguments, unset
    # in development. Shown in the page footer and at /api/version.
    git_commit: str | None = None
    build_date: datetime | None = None
    source_url: str | None = None  # repository URL, for the commit link

    log_level: str = "INFO"

    @field_validator("git_commit", "build_date", "source_url", mode="before")
    @classmethod
    def _empty_is_unset(cls, value):
        # The Dockerfile always sets these; a build without the arguments leaves them empty.
        return None if value == "" else value


def get_settings() -> Settings:
    return Settings()
