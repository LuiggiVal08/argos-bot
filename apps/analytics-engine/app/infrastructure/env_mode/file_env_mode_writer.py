"""FileEnvironmentModeWriter: persists the mode to a JSON file on disk.

This is the default adapter for bare-metal deployments. The
file path defaults to `/var/lib/argos/env_mode.json` but can
be overridden via the `ARGOS_ENV_MODE_FILE` env var (useful
for tests and dev). The file is rewritten atomically (write
to temp + rename) so a crash mid-write can't leave a
half-baked JSON behind.

The Docker adapter (future) will instead restart the engine
with the new env var, but for now Docker and bare-metal share
this adapter.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ...application.ports.environment_mode_writer import (
    EnvironmentMode,
    EnvironmentModeError,
    EnvironmentModeWriter,
)


class FileEnvironmentModeWriter(EnvironmentModeWriter):
    DEFAULT_PATH = "/var/lib/argos/env_mode.json"

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        if path is None:
            path = os.environ.get("ARGOS_ENV_MODE_FILE", self.DEFAULT_PATH)
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def write(self, mode: EnvironmentMode) -> None:
        try:
            # Atomic write: temp file in the same dir, then rename.
            with tempfile.NamedTemporaryFile(
                "w",
                dir=self._path.parent,
                delete=False,
                prefix=".env_mode.",
                suffix=".tmp",
            ) as tmp:
                json.dump({"mode": mode.value}, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name
            os.replace(tmp_path, self._path)
        except OSError as e:
            raise EnvironmentModeError(
                f"env_mode_write_failed: {self._path}: {e}"
            ) from e

    async def read(self) -> EnvironmentMode:
        if not self._path.exists():
            # Safe default per spec: never auto-default to LIVE.
            return EnvironmentMode.BACKTESTING
        try:
            data = json.loads(self._path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise EnvironmentModeError(
                f"env_mode_read_failed: {self._path}: {e}"
            ) from e
        try:
            return EnvironmentMode(data["mode"])
        except (KeyError, ValueError) as e:
            raise EnvironmentModeError(
                f"env_mode_unparseable: {data}: {e}"
            ) from e
