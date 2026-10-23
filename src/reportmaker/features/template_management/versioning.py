"""Version history for stored templates: snapshot files under a history directory."""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from reportmaker.features.template_management.exceptions import (
    TemplateVersionNotFoundError,
)
from reportmaker.features.template_management.models import (
    TemplateVersion,
    VersionSource,
)
from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_VERSIONS = 50

_STAMP_FORMAT = "%Y%m%dT%H%M%S%fZ"
# Anchored on purpose: a version id is joined onto a path, so anything that
# does not look exactly like one we generated must never reach the filesystem.
_VERSION_ID = re.compile(r"^(\d{8}T\d{12}Z)__(save|import|delete|rollback)$")


class VersionStore:
    """Keeps the previous contents of each template, newest ``max_versions`` only.

    A snapshot is the file as it was *before* a change, so the current file is
    never part of the history. Ids sort chronologically, which is what pruning
    and listing rely on.
    """

    def __init__(self, history_dir: Path, max_versions: int = DEFAULT_MAX_VERSIONS):
        if max_versions < 1:
            raise ValueError("max_versions must be at least 1")
        self._root = history_dir
        self._max_versions = max_versions

    def snapshot(self, stem: str, content: bytes, source: VersionSource) -> None:
        """Record ``content`` as a version of ``stem`` and prune the oldest."""
        versions = self._ids(stem)
        # Re-saving unchanged content would only push real history out.
        if versions and self._path(stem, versions[-1]).read_bytes() == content:
            return
        directory = ensure_directory(self._dir(stem))
        version_id = self._new_id(versions, source)
        (directory / f"{version_id}.yaml").write_bytes(content)
        logger.info(f"Recorded version '{version_id}' of template '{stem}'")
        for stale in self._ids(stem)[: -self._max_versions]:
            self._path(stem, stale).unlink()

    def list_versions(self, stem: str) -> List[TemplateVersion]:
        """Return the versions of ``stem``, newest first."""
        return [
            self._describe(stem, version_id)
            for version_id in reversed(self._ids(stem))
        ]

    def read(self, stem: str, version_id: str) -> bytes:
        """Return the stored content of one version.

        Raises:
            TemplateVersionNotFoundError: if there is no such version.
        """
        path = self._path(stem, version_id)
        if not path.is_file():
            raise TemplateVersionNotFoundError(
                f"Template '{stem}' has no version '{version_id}'"
            )
        return path.read_bytes()

    def _dir(self, stem: str) -> Path:
        # A stem such as ".." would point the history outside its own folder.
        if not stem.strip("._-"):
            raise TemplateVersionNotFoundError(f"'{stem}' is not a template name")
        return self._root / stem

    def _path(self, stem: str, version_id: str) -> Path:
        if not _VERSION_ID.match(version_id):
            raise TemplateVersionNotFoundError(
                f"Template '{stem}' has no version '{version_id}'"
            )
        return self._dir(stem) / f"{version_id}.yaml"

    def _ids(self, stem: str) -> List[str]:
        directory = self._dir(stem)
        if not directory.is_dir():
            return []
        return sorted(
            p.stem for p in directory.glob("*.yaml") if _VERSION_ID.match(p.stem)
        )

    def _new_id(self, existing: List[str], source: VersionSource) -> str:
        moment = datetime.now(timezone.utc)
        # Strictly after the newest id even if the clock stalls or steps back,
        # otherwise the id order would stop matching the order of the edits.
        if existing:
            newest = datetime.strptime(
                existing[-1].split("__")[0], _STAMP_FORMAT
            ).replace(tzinfo=timezone.utc)
            moment = max(moment, newest + timedelta(microseconds=1))
        return f"{moment.strftime(_STAMP_FORMAT)}__{source.value}"

    def _describe(self, stem: str, version_id: str) -> TemplateVersion:
        stamp, source = version_id.split("__")
        return TemplateVersion(
            version_id=version_id,
            created_at=datetime.strptime(stamp, _STAMP_FORMAT).replace(
                tzinfo=timezone.utc
            ),
            source=VersionSource(source),
            size_bytes=self._path(stem, version_id).stat().st_size,
        )
