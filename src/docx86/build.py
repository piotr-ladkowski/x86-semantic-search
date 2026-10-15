"""Which version is running: the commit an image was built from, when, and when this server started.

The commit, build time and repository URL are baked into the image as DOCX86_GIT_COMMIT,
DOCX86_BUILD_DATE and DOCX86_SOURCE_URL (Dockerfile build arguments, filled in by CI); outside an
image they are unset and the site says "development build".

The deployment time itself is not visible from inside a pod: the pod has no Kubernetes API token
(deliberately) and the Downward API cannot expose a pod's creation time. So `started_at` is when
this server process started. After a rollout (an Argo CD Image Updater sync, `kubectl apply`, ...)
that is when the new version went live on this pod; a pod restarted later reports the later time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from . import __version__
from .config import Settings


@dataclass(frozen=True)
class BuildInfo:
    version: str  # the package version (pyproject), not the commit
    commit: str | None
    built_at: datetime | None
    source_url: str | None
    started_at: datetime

    @property
    def short_commit(self) -> str | None:
        return self.commit[:7] if self.commit else None

    @property
    def commit_url(self) -> str | None:
        if self.commit and self.source_url:
            return f"{self.source_url.rstrip('/')}/commit/{self.commit}"
        return None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "commit": self.commit,
            "commit_url": self.commit_url,
            "built_at": _iso(self.built_at),
            "started_at": _iso(self.started_at),
        }


def _utc(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.astimezone(UTC) if moment.tzinfo else moment.replace(tzinfo=UTC)


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z") if moment else None


def build_info(settings: Settings) -> BuildInfo:
    """Call once at startup: `started_at` is taken now."""
    return BuildInfo(
        version=__version__,
        commit=settings.git_commit,
        built_at=_utc(settings.build_date),
        source_url=settings.source_url,
        started_at=datetime.now(UTC),
    )
