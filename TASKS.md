---
project: argos-bot
total_tasks: 14
completed: 14
in_progress: 0
blocked: 0
overall_pct: 100
last_updated: 2026-06-06
---

# TASKS — argos-bot

> Tracker persistente. Se mapea 1:1 con las historias de `spec.md` sección 5.
> Actualizado al final de cada sesión de trabajo.

**Estados**: ⬜ TODO · 🟡 IN_PROGRESS · ✅ DONE · ⛔ BLOCKED · 🚫 CANCELLED
**%**: progreso de la historia completa (no por tarea individual)

---

## Resumen ejecutivo

| ID    | Historia                | Estado | %     | Tareas |
|-------|-------------------------|--------|-------|--------|
| Setup | Infra y tools           | ✅     | 100%  | 13/13  |
| H1    | Tick Pipeline (<2ms)    | ⬜     | 0%    | 0/4    |
| H2    | Position Sizing (≤1%)   | ⬜     | 0%    | 0/4    |
| H3    | Circuit Breaker (5%)    | ⬜     | 0%    | 0/4    |
| H4    | OWASP Incident Response | ⬜     | 0%    | 0/4    |
| H5    | Secrets & Env Mode      | ⬜     | 0%    | 0/4    |

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

## ⬜ H1 — Tick Pipeline (<2ms)

> spec.md §5 Historia 1. Inyectar ticks del exchange a Redis Streams y consumirlos en analytics-engine en <2ms p99.

- [ ] H1-001 — Scaffold publisher Redis Streams en `data-engine/src/infrastructure/redis/`
- [ ] H1-002 — Scaffold consumer Redis Streams en `analytics-engine/app/infrastructure/redis/`
- [ ] H1-003 — Benchmark de latencia end-to-end (pytest + script TS)
- [ ] H1-004 — Verificar SLA <2ms p99 en CI

**Progreso**: 0/4 = **0%**
**Dependencias**: ninguna
**Notas**: —

---

## ⬜ H2 — Position Sizing (≤1% del free balance)

> spec.md §5 Historia 2. Calcular tamaño de posición: `size = (free_balance * risk_pct) / atr`.

- [ ] H2-001 — Implementar ATR en `analytics-engine/app/domain/indicators/atr.py`
- [ ] H2-002 — Implementar `position_size` con validación (rechazar `risk_pct > 0.02`)
- [ ] H2-003 — Tests unitarios (casos límite: balance=0, atr=0, risk_pct>2%)
- [ ] H2-004 — Wire-up al ejecutor (tool `risk_position_size` ya existe)

**Progreso**: 0/4 = **0%**
**Dependencias**: ninguna
**Notas**: el tool `risk_position_size` ya valida y retorna JSON; H2-002 lo implementa dentro del analytics-engine (versión persistente), H2-004 lo conecta.

---

## ⬜ H3 — Circuit Breaker (5% drawdown diario)

> spec.md §5 Historia 3. Cortar operativa si pérdida diaria ≥ 5% del balance de apertura UTC 00:00.

- [ ] H3-001 — Tracker de P&L diario (snapshot UTC 00:00 + delta intradía)
- [ ] H3-002 — `drawdown_check` con umbrales SAFE / WARN / TRIP
- [ ] H3-003 — Acciones de disparo: cancelar órdenes, cerrar posiciones, `ENVIRONMENT_MODE=PASIVO`
- [ ] H3-004 — Tests SAFE / WARN (3% < 5%) / TRIP (5% ≥)

**Progreso**: 0/4 = **0%**
**Dependencias**: H5-003 (env mode)
**Notas**: tool `risk_drawdown_check` ya existe con la lógica SAFE/WARN/TRIP; H3 lo institucionaliza dentro del engine.

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
