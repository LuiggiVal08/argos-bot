from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ModelVersion:
    major: int
    minor: int
    patch: int
    timestamp: str = ""

    def __str__(self) -> str:
        base = f"v{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.timestamp}" if self.timestamp else base

    @classmethod
    def parse(cls, version_str: str) -> ModelVersion:
        m = re.match(r"v?(\d+)\.(\d+)\.(\d+)(?:-(.+))?", version_str)
        if not m:
            raise ValueError(f"invalid version format: {version_str}")
        return cls(
            major=int(m.group(1)),
            minor=int(m.group(2)),
            patch=int(m.group(3)),
            timestamp=m.group(4) or "",
        )

    @classmethod
    def from_datetime(cls, major: int, minor: int) -> ModelVersion:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return cls(major=major, minor=minor, patch=0, timestamp=ts)

    def bumped_patch(self) -> ModelVersion:
        return ModelVersion(
            major=self.major,
            minor=self.minor,
            patch=self.patch + 1,
            timestamp=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )

    def bumped_minor(self) -> ModelVersion:
        return ModelVersion(
            major=self.major,
            minor=self.minor + 1,
            patch=0,
            timestamp=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )

    @property
    def semver_key(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __lt__(self, other: ModelVersion) -> bool:
        return self.semver_key < other.semver_key

    def __gt__(self, other: ModelVersion) -> bool:
        return self.semver_key > other.semver_key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModelVersion):
            return NotImplemented
        return self.semver_key == other.semver_key

    def __hash__(self) -> int:
        return hash(self.semver_key)
