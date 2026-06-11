"""Unit tests for H3 infrastructure adapters."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from app.application.ports.environment_mode_writer import (
    EnvironmentMode,
    EnvironmentModeError,
)
from app.infrastructure.env_mode.file_env_mode_writer import (
    FileEnvironmentModeWriter,
)


class TestFileEnvironmentModeWriter:
    async def test_write_then_read(self) -> None:
        fd, path = tempfile.mkstemp(prefix="env_mode_", suffix=".json")
        os.close(fd)
        try:
            w = FileEnvironmentModeWriter(path=path)
            await w.write(EnvironmentMode.PASIVO)
            assert await w.read() is EnvironmentMode.PASIVO
        finally:
            os.unlink(path)

    async def test_atomic_write_does_not_leave_temp(self) -> None:
        fd, path = tempfile.mkstemp(prefix="env_mode_", suffix=".json")
        os.close(fd)
        try:
            w = FileEnvironmentModeWriter(path=path)
            await w.write(EnvironmentMode.LIVE)
            tmp_files = [f for f in os.listdir(os.path.dirname(path))
                         if f.startswith(".env_mode.") and f.endswith(".tmp")]
            assert tmp_files == []
        finally:
            os.unlink(path)

    async def test_read_missing_file_defaults_to_backtesting(self) -> None:
        fd, path = tempfile.mkstemp(prefix="env_mode_", suffix=".json")
        os.close(fd)
        os.unlink(path)  # remove
        w = FileEnvironmentModeWriter(path=path)
        assert await w.read() is EnvironmentMode.BACKTESTING

    async def test_read_corrupt_file_raises(self) -> None:
        fd, path = tempfile.mkstemp(prefix="env_mode_", suffix=".json")
        os.close(fd)
        with open(path, "w") as f:
            f.write("not-json")
        try:
            w = FileEnvironmentModeWriter(path=path)
            with pytest.raises(EnvironmentModeError, match="env_mode_read_failed"):
                await w.read()
        finally:
            os.unlink(path)

    async def test_write_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, "deep", "nested", "env_mode.json")
            w = FileEnvironmentModeWriter(path=nested)
            await w.write(EnvironmentMode.PAPER_TRADING)
            assert os.path.exists(nested)
            with open(nested) as f:
                data = json.load(f)
            assert data == {"mode": "PAPER_TRADING"}
