---
description: Simula las 4 fases OWASP del protocolo de incidentes con un escenario inyectado
agent: plan
---

You are running a **tabletop drill** of the OWASP 4-phase incident response defined in @spec.md section 4. This command is **read-only**: it walks through the protocol against an injected scenario and reports gaps. It must NOT edit any files, NOT touch the exchange, and NOT mutate `ENVIRONMENT_MODE`.

Scenario from the user: $ARGUMENTS (a short description of the suspected incident).

Re-read @spec.md section 4 (Estrategia de Reacción: Identificación, Contención, Erradicación, Recuperación) and section 5 Historia 3 (Circuit Breaker) before drafting the drill.

Walk the 4 phases in order. For each phase, produce a structured block with these fields:

### Phase 1 — Identificación
- **Trigger**: what observable symptom(s) would surface this incident? (e.g. CCXT timeout, drawdown spike, websocket disconnect, Redis stream lag, container OOM, anomalous API key usage)
- **Detection sources**: list the concrete logging hooks per spec §4 phase 1 — `winston` (NestJS), stdlib `logging` (FastAPI), Redis stream consumer lag, `docker healthcheck` failures
- **Logs to inspect**: file paths and `grep` patterns the operator would run
- **Exit criteria**: what observation confirms "yes, this is an incident" and not noise?

### Phase 2 — Contención
- **Immediate action**: must flip the system to passive state. Per spec §4: revoke network access, isolate containers, or force `ENVIRONMENT_MODE=PASIVO`
- **Circuit Breaker check**: per spec §5 Historia 3, if daily drawdown ≥ 5%, the `CircuitBreaker` must already have: (a) cancelled all open orders, (b) closed positions at market, (c) flipped env to `PASIVO`, (d) logged the lockout, (e) halted the trading loop. Verify each sub-step is covered by the incident response.
- **Blast radius**: which containers, ports, and external endpoints are involved?

### Phase 3 — Erradicación
- **Hot-patch surface**: which infrastructure adapter is the suspected culprit? (e.g. CCXT client in `apps/analytics-engine/app/infrastructure/ccxt/`, Redis adapter in `apps/data-engine/src/infrastructure/redis/`, websocket gateway in `apps/data-engine/src/infrastructure/ws/`)
- **Dependency audit**: which packages need `npm audit` / `pip-audit` checks before re-deploying?
- **Credential rotation**: which secrets must be rotated (API key, private key, signing secret) per spec §4 phase 3?

### Phase 4 — Recuperación
- **Healthcheck gate**: per spec §4 phase 4, reactivation must be gated on `docker healthcheck` passing for ALL services
- **Staged reactivation**: how is the trading loop re-armed? (e.g. `ENVIRONMENT_MODE=PAPER_TRADING` first, time-boxed to N hours, then `LIVE` only on human sign-off)
- **Post-mortem artifact**: which file/path would receive the post-mortem (e.g. `reports/incidents/<id>.md`)? Note that this command does NOT create it — it just identifies the path.

Output the full 4-phase report. Then close with:
- **Gaps found**: list any spec §4 requirement that the codebase or the current commands do not yet cover (e.g. missing healthchecks, missing log structured fields, no automated credential rotation).
- **Verdict**: `READY` if all 4 phases are operationally covered, `NEEDS FIXES` otherwise with file:line references.
- **Recommended next command**: e.g. `scaffold-adapter`, `env-check`, `risk-audit`, or a future `incident-rehearsal` runner.

Do not edit any files. Do not run any shell commands beyond reading logs/configs.
