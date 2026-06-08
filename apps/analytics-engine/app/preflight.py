"""PreflightCheck: validates env requirements before LIVE mode init.

Per spec §5 Historia 5 sad path: if ENVIRONMENT_MODE=LIVE but required
secret env vars are missing or empty, abort init with exit code 1.
"""
from __future__ import annotations

import os
import sys


REQUIRED_LIVE_VARS: tuple[str, str, ...] = (
    "EXCHANGE_API_KEY",
    "EXCHANGE_API_SECRET",
    "ARGOS_BROKER_URL",
)

OPTIONAL_LIVE_VARS: tuple[str, str, ...] = (
    "EXCHANGE_PASSPHRASE",
    "EXCHANGE_ID",
    "EXCHANGE_WS_URL",
)


def preflight_check(mode: str) -> list[str]:
    """Return a list of missing-var error messages.
    If the list is empty, all checks passed.

    In LIVE mode, REQUIRED_LIVE_VARS must be set and non-empty.
    In non-LIVE modes, no vars are strictly required (they may be
    mocked or defaulted).
    """
    errors: list[str] = []
    if mode != "LIVE":
        return errors

    for var in REQUIRED_LIVE_VARS:
        val = os.environ.get(var)
        if not val:
            errors.append(
                f"LIVE mode requires {var} to be set and non-empty"
            )

    return errors


def abort_if_missing(mode: str) -> None:
    """Run preflight_check and sys.exit(1) if any errors found.

    Intended to be called at the top of build_composition() so the
    engine never starts with partial credentials in LIVE mode.
    """
    errors = preflight_check(mode)
    if errors:
        import structlog
        log = structlog.get_logger()
        log.critical(
            "preflight_failed",
            mode=mode,
            errors=errors,
            message="LIVE mode init aborted: missing required secrets",
        )
        print(f"FATAL: LIVE preflight failed: {errors}", file=sys.stderr)
        sys.exit(1)
