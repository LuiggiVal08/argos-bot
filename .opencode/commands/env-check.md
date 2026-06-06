---
description: Verifica la configuración de entorno y los controles de seguridad (OWASP)
agent: plan
---

Current docker compose / env state:
!`docker compose config 2>/dev/null | head -200 || echo "no docker compose file"`

Re-read @spec.md section 1 (infra) and section 4 (OWASP 4-phase incident response).

Verify and report:
1. **ENVIRONMENT_MODE** is set to one of `BACKTESTING`, `PAPER_TRADING`, `LIVE`. If `LIVE`, all required secret env vars must be non-empty — otherwise the init cycle must fail with exit code 1 (spec section 5 Historia 5 sad path).
2. **Secrets**: API keys, private keys, and exchange signatures are injected via env vars, never hardcoded. The `.env` file must be in `.gitignore`.
3. **Healthchecks**: Each service in `docker-compose` defines a `healthcheck` (spec section 4 phase 4 — Recovery).
4. **Network isolation**: Containers that should not reach the public internet (e.g. backtesting data loader) are restricted by network rules.
5. **Logging**: Structured logging is configured (`winston` for NestJS, stdlib `logging` for FastAPI).

Output: PASS / NEEDS FIXES with file:line for each finding. Do not edit any files.
