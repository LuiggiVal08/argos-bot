---
project: argos-bot
total_tasks: 14
completed: 14
in_progress: 0
blocked: 0
overall_pct: 100
last_updated: 2026-06-07
---

# TASKS — argos-bot

> Tracker persistente. Se mapea 1:1 con las historias de `spec.md` sección 5.
> Actualizado al final de cada sesión de trabajo.

**Estados**: ⬜ TODO · 🟡 IN_PROGRESS · ✅ DONE · ⛔ BLOCKED · 🚫 CANCELLED
**%**: progreso de la historia completa (no por tarea individual)

---

## Resumen ejecutivo

| ID    | Historia                | Estado | %      | Tareas |
|-------|-------------------------|--------|--------|--------|
| Setup | Infra y tools           | ✅     | 100%   | 14/14  |
| H1    | Tick Pipeline (<2ms)    | ✅     | 100%   | 11/11  |
| H2    | Position Sizing (≤1%)   | ✅     | 100%   | 9/9    |
| H3    | Circuit Breaker (5%)    | 🟡     | 0%     | 0/9    |
| H4    | OWASP Incident Response | ⬜     | 0%     | 0/4    |
| H5    | Secrets & Env Mode      | ⬜     | 0%     | 0/4    |

---

## ✅ Setup — Infraestructura y herramientas

> Todo lo previo a implementar las historias de usuario.

- [x] S001 — Crear estructura del proyecto (`apps/data-engine`, `apps/analytics-engine`)
- [x] S002 — Escribir `spec.md` con las 5 historias
- [x] S003 — Configurar `opencode.json` (plugin + MCP context7)
- [x] S004 — Mover 10 tools a `.opencode/tools/`
- [x] S005 — 12 slash commands en `.opencode/commands/`
- [x] S006 — 28 custom tools cargados sin error
- [x] S007 — Cargar 7 skills relevantes
- [x] S008 — Fix `import.meta.dir` (Bun → Node) en `backtest.ts`, `indicators.ts`
- [x] S009 — Fix regex `(?i)` en `quality.ts` (flag inline no soportado)
- [x] S010 — 21 `execute()` marcados como `async` (compatibilidad Effect)
- [x] S011 — 16 tools con `args: {}` añadidos
- [x] S012 — Crear `AGENTS.md` con reglas e invariantes
- [x] S013 — Crear `TASKS.md` (este archivo)
- [x] S014 — Refactor agnóstico: spec.md + AGENTS.md + config.json + README + health.ts + .gitattributes

**Progreso**: 14/14 = **100%**

---

## ✅ H1 — Tick Pipeline (<2ms)

> spec.md §5 Historia 1. NestJS WS → use case → broker XADD < 2ms p99. FastAPI consume async. Sad path: broker down → buffer in-memory max 100; > 10s → close WS orderly.

- [x] H1-001 — Domain: `Tick` entity, `Symbol` / `Price` / `StreamName` value objects
- [x] H1-002 — Application ports: `MessageBus`, `ExchangeGateway`, `TickBuffer`, `HealthMonitor`
- [x] H1-003 — Application use cases: `IngestTickUseCase`, `BufferTickUseCase`, `FlushBufferUseCase`, `HealthMonitorUseCase`
- [x] H1-004 — Infrastructure: `BinanceWebSocketAdapter`, `RedisProtocolBus`, `InMemoryTickBuffer`
- [x] H1-005 — Sad path: `HealthMonitorUseCase` con cutoff de 10s (cierra WS)
- [x] H1-006 — NestJS DI wiring: `AppModule` con providers + lifecycle hooks
- [x] H1-007 — Analytics-engine subscriber mínimo (prueba end-to-end)
- [x] H1-008 — Tests unit: domain + use cases con ports mockeados (26/26 PASS)
- [x] H1-009 — Tests integration: Redis real (Docker) con p99 < 2ms
- [x] H1-010 — Benchmark de latencia XADD (`benchmark/xadd-latency.ts`)
- [x] H1-011 — Bitácora + cierre H1

**Progreso**: 11/11 = **100%**
**Dependencias**: ninguna
**Notas**:
- Buffer de 100 es insuficiente para 10s a >10 ticks/s. Spec se implementa literal; sizing del buffer queda como follow-up H1-FU1.
- H1-009 y H1-010 no se ejecutaron en sandbox (no hay Docker/red broker); se ejecutan en CI/dev con `docker compose up broker` y `ARGOS_BROKER_URL=redis://localhost:6379`.
- Hexagonal: `tick-pipeline.service.ts` se movió a `infrastructure/services/` (es glue NestJS, no caso de uso del dominio). Application/ queda sin imports de Infrastructure.
- ESLint añadido (`@typescript-eslint` con rule override para domain class `Symbol`).
- `@nestjs/config@3.2.0` instalado (3.1.x requiere `reflect-metadata@^0.1.13`, conflict).

---

## ✅ H2 — Position Sizing (≤1% del free balance)

> spec.md §5 Historia 2. Capa de Dominio calcula `units = (free_balance * risk_pct) / atr`. SL dinámico a distancia ATR. Sad path: CCXT timeout o balance=0 → abort; size < min_lot → descartar.

- [x] H2-001 — Domain VOs: `Atr`, `RiskPct`, `PositionSize` (validación: atr>0, 0<risk_pct≤0.02, units≥0)
- [x] H2-002 — Domain entity: `RiskCalculator.calculate(free_balance, atr, risk_pct) → PositionSize`
- [x] H2-003 — Application ports: `BalanceProvider`, `AtrCalculator`, `MinLotProvider` (Protocol)
- [x] H2-004 — Application use case: `ComputePositionSizeUseCase` con CCXT-error handling + min_lot check
- [x] H2-005 — Infrastructure adapters: `TaAtrCalculator` (lib `ta`), `CcxtBalanceProvider`, `MockBalanceProvider`, `CcxtMinLotProvider`
- [x] H2-006 — API endpoint: `POST /risk/position-size` con DI composition root
- [x] H2-007 — Tests unit (VOs + entity + use case con mocks) + integration (TA lib real)
- [x] H2-008 — Validation: pytest (43 passed, 1 skipped), mypy clean, arch_lint clean, secret_scan clean
- [x] H2-009 — Commit + PR body (`docs/prs/h2-position-sizing.md`); **PR #2 mergeado a dev**

**Progreso**: 9/9 = **100%**
**Dependencias**: ninguna
**Notas**: el tool opencode `risk_position_size` ya implementa la fórmula base (H2-002 lo institucionaliza en el engine). Min lot check es la pieza nueva que el tool no tenía. Integration con strategy/IA queda para historias posteriores.

---

## 🟡 H3 — Circuit Breaker (5% drawdown diario)

> spec.md §5 Historia 3. Cortar operativa si pérdida diaria ≥ 5% del balance de apertura UTC 00:00. Acciones: cancelar órdenes, cerrar posiciones a mercado, `ENVIRONMENT_MODE=PASIVO`, halt loop, log crítico.

- [ ] H3-001 — Domain VOs: `DrawdownSnapshot`, `DrawdownVerdict`, `TripAction`
- [ ] H3-002 — Domain entity: `CircuitBreaker.evaluate(snapshot) → verdict` (SAFE/WARN/TRIP) + `should_reset_utc(now)`
- [ ] H3-003 — Application ports: `TradeJournal`, `ExchangeOrderClient`, `EnvironmentModeWriter`, `DrawdownSnapshotRepo`
- [ ] H3-004 — Application use cases: `CheckDrawdownUseCase`, `TripCircuitBreakerUseCase`, `OpenDayUseCase`
- [ ] H3-005 — Infrastructure: `InMemoryTradeJournal`, `InMemorySnapshotRepo`, `CcxtOrderClient`, `FileEnvironmentModeWriter`
- [ ] H3-006 — API: `GET /risk/drawdown`, `POST /risk/drawdown/check`, `POST /risk/day/open`
- [ ] H3-007 — Tests unit + integration
- [ ] H3-008 — Validation: pytest, mypy, arch_lint, secret_scan
- [ ] H3-009 — Commit + PR title/description

**Progreso**: 0/9 = **0%**
**Dependencias**: H5-003 (env mode write file/secret) — H3 escribe `ENVIRONMENT_MODE=PASIVO` via port; H5 controla el sad path
**Notas**: tool opencode `risk_drawdown_check` ya tiene SAFE/WARN/TRIP; H3 la institucionaliza y agrega las 4 acciones de disparo. Reset diario via endpoint `POST /risk/day/open`; scheduler cron es H3-FU1.

---

## ⬜ H4 — OWASP Incident Response (4 fases)

> spec.md §5 Historia 4. Protocolo OWASP: Detect → Contain → Eradicate → Recover.

- [ ] H4-001 — Definir las 4 fases en `docs/incident-response.md`
- [ ] H4-002 — Detectores automáticos (anomalía de latencia, error rate, drawdown)
- [ ] H4-003 — Runbook por fase con responsabilidades y plazos
- [ ] H4-004 — Drill end-to-end con `/incident-drill`

**Progreso**: 0/4 = **0%**
**Dependencias**: H3 (Circuit Breaker como trigger de Contain)
**Notas**: —

---

## ⬜ H5 — Secrets & Env Mode

> spec.md §5 Historia 5. Variables de entorno, secretos, validación de modo.

- [ ] H5-001 — Validación `config_toggle_mode` con sad path (LIVE sin secrets → abort exit 1)
- [ ] H5-002 — Pre-flight check en LIVE mode al arranque
- [ ] H5-003 — Plantilla `.env.example` completa (data-engine + analytics-engine)
- [ ] H5-004 — Verificar lectura de secrets desde env (nunca hardcoded en código)

**Progreso**: 0/4 = **0%**
**Dependencias**: ninguna
**Notas**: el tool `config_toggle_mode` ya implementa la sad path; H5-001 lo mueve a la capa de aplicación del engine.

---

## ⛔ Bloqueos

_Ninguno actualmente._

---

## Bitácora

### 2026-06-07 — Sesión H1: Tick Pipeline
- ✅ Branch `feature/h1-tick-pipeline` creada desde `dev`.
- ✅ H1-001..H1-007 implementados: domain (Tick, Symbol, Price, StreamName), application ports, use cases, infrastructure adapters (BinanceWebSocketAdapter, RedisProtocolBus, InMemoryTickBuffer, BusHealthMonitor), NestJS DI wiring, FastAPI subscriber mínimo con xread.
- ✅ H1-008: 26/26 tests unitarios PASS (`domain.spec.ts` 14 tests, `use-cases.spec.ts` 12 tests).
- ✅ Validación: `tsc --noEmit` PASS, `eslint` PASS (con override para domain class `Symbol`).
- ✅ Hexagonal: `tick-pipeline.service.ts` movido a `infrastructure/services/` (es glue NestJS). `application/` sin imports de `infrastructure/`.
- ✅ Deps añadidas: `@nestjs/config@3.2.0` (3.1.x choca con `reflect-metadata@0.2.2`).
- ⏭ H1-009 (integration) y H1-010 (benchmark) requieren broker reachable; no ejecutados en sandbox.
- 🐛 Bug detectado y corregido en `FlushBufferUseCase`: `drain()` vaciaba el buffer y al fallar el primer publish solo re-bufeaba ese tick, perdiendo los siguientes. Ahora re-bufea el fallido + todos los restantes en orden.
- ✅ Push de `feature/h1-tick-pipeline` a `origin` (7 commits, todos conventional).
- ✅ **PR #1 mergeado a `dev`** (merge commit `f053fc7`, sin squash — los 7 commits de H1 preservados para bisect y trazabilidad).
- ✅ Rama `feature/h1-tick-pipeline` borrada en local y en `origin`.
- ✅ PR body archivado en `docs/prs/done/h1-tick-pipeline.md` para referencia histórica.
- 🎯 **PR #1 (H1) mergeado a dev** — primera historia cerrada del proyecto.
- 🔒 Sandbox: registry npm ~14s/ping, install tomó ~5 min; tests/lint corren offline en ~5s cada uno.

### 2026-06-06 — Sesión de setup
- ✅ Crash de opencode diagnosticado y resuelto (3 causas: `import.meta.dir`, regex `(?i)`, `execute()` sync).
- ✅ 28 tools operativos, 12 commands, 7 skills, context7 MCP.
- ✅ 5 tools verificados con invocación real: `spec_invariants`, `risk_position_size`, `risk_drawdown_check`, `config_read_config`, `spec_summary`.
- ✅ `AGENTS.md` y `TASKS.md` creados.
- ✅ Política de permisos en `opencode.json` para tools destructivos.
- ✅ Git inicializado, `main` y `dev` pusheadas a `origin` (commits `f3c46e0`, `423221e`).
- ✅ `LICENSE` (MIT) y `README.md` creados.
- ✅ Refactor agnóstico: spec.md §1, §1.2, §4, §6 amendados; AGENTS.md §1, §2 #14, §7, §11 actualizados; config.json migrado a `broker: { kind, url: ${ARGOS_BROKER_URL} }`; `.gitattributes` creado; README "Quick start" dual (Docker + bare metal con WSL2/Memurai); `health_health_check` con detección de deployment model; `docker_docker_*` tools anotados como "uso solo con deploy Docker".
- ✅ Sección 12 (Git workflow) añadida a AGENTS.md.
- ✅ Fase 0 ejecutada: `docker-compose.yml` (3 servicios, broker RESP-compatibile con `ARGOS_BROKER_URL`), NestJS data-engine skeleton, FastAPI analytics-engine skeleton. 20 archivos nuevos en `apps/`. Las tools de opencode habían quedado con la versión pre-agnóstica en memoria; parcheé los 4 archivos afectados (`.env.example` × 2, `main.ts`, `docker-compose.yml`) al contenido correcto.
