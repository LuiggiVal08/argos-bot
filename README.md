# argos-bot

> Autonomous production-grade crypto perpetual futures trading bot.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Status: Pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)]()
[![Stack: NestJS + FastAPI + Redis](https://img.shields.io/badge/stack-NestJS%20%2B%20FastAPI%20%2B%20Redis-blue)]()

## Status

🚧 **In development** — built spec-first, story by story from [`spec.md`](./spec.md).

Live progress: [`TASKS.md`](./TASKS.md). Working on the H1 story (Tick Pipeline, <2ms p99 SLA).

## Architecture

Event-driven microservices, hexagonal internally.

| Service | Stack | Role |
|---|---|---|
| `data-engine` | NestJS (TS) | WebSocket → exchange, injects ticks to Redis (<2ms p99 SLA) |
| `analytics-engine` | FastAPI (Py 3.11) | Consumes Redis, computes indicators, emits signals |
| `redis` | 7-alpine | Message broker / buffer |

Services communicate **only** via Redis. No direct imports across services.

Hard invariants (from `spec.md` §5): 1% risk per trade, ATR-based SL distance, 5% daily drawdown circuit-breaker. See [`AGENTS.md`](./AGENTS.md) for the full ruleset.

## Quick start

The same code runs in two ways. Pick one.

### Option A — Docker Compose (recommended for production / CI)

```bash
git clone https://github.com/LuiggiVal08/argos-bot.git
cd argos-bot
docker compose up -d
docker compose ps
```

### Option B — Bare metal (recommended for native dev on Windows / macOS / Linux)

The app code is **deployment-agnostic** — Docker is one option, not the only one. The same binaries run natively.

#### 1. Install a RESP-compatible broker

| OS | Install | Notes |
|---|---|---|
| macOS | `brew install redis` | Start with `brew services start redis` |
| Ubuntu / Debian (incl. WSL2) | `sudo apt install redis-server` | WSL2 forwards ports to `localhost` automatically |
| Windows (native, no WSL) | `choco install memurai` or `scoop install memurai` | Memurai is a Redis-compatible Windows broker |
| Any | `docker run -d -p 6379:6379 redis:7-alpine` | Still works if you only have Docker for the broker |

The broker is pluggable — it only needs to speak the RESP protocol. See [`AGENTS.md`](./AGENTS.md) §2 invariant #14.

#### 2. Run the services

```bash
# Terminal 1 — data-engine (NestJS)
cd apps/data-engine
ARGOS_BROKER_URL=redis://localhost:6379 npm run dev

# Terminal 2 — analytics-engine (FastAPI)
cd apps/analytics-engine
ARGOS_BROKER_URL=redis://localhost:6379 uvicorn app.main:app --reload --port 8000
```

#### 3. Verify

```bash
# Single command, auto-detects Docker or bare metal
/health
```

This delegates to the `health_health_check` AI tool, which checks broker reachability, git status, and either `docker compose ps` (if Docker is present) or HTTP health endpoints on each service.

## Repository layout

```
argos-bot/
├── apps/
│   ├── data-engine/         # NestJS, TS — WebSocket → Redis
│   └── analytics-engine/    # FastAPI, Py 3.11 — Redis → signals
├── spec.md                  # Source of truth (5 user stories in §5)
├── AGENTS.md                # Rules for the AI agent working on this project
├── TASKS.md                 # Live progress tracker
├── LICENSE                  # MIT
├── docker-compose.yml       # data-engine + analytics-engine + redis
├── config.json              # ENVIRONMENT_MODE + risk params
├── skills-lock.json         # Pinned AI agent skills (lockfile)
└── .opencode/               # AI agent tooling (tools, commands, skills)
```

## Operating modes

`ENVIRONMENT_MODE` ∈ `{BACKTESTING, PAPER_TRADING, LIVE}` (set in `config.json`).

| Mode | Real money? | Use case |
|---|---|---|
| `BACKTESTING` | No | Validate strategies on historical data |
| `PAPER_TRADING` | No | Validate pipeline end-to-end with live ticks |
| `LIVE` | **Yes** | Real trading. Aborts on missing secret env vars. |

Default is `PAPER_TRADING`. To switch to `LIVE` you must confirm explicitly.

## Development workflow

Git-flow-lite:

- `main` — production, deployable. Receives merges from `dev` (or `hotfix/*`).
- `dev` — integration. Base for new feature branches.
- `feature/<id>-<slug>` — one branch per `spec.md` story. Merge → `dev`.
- `fix/<slug>` — non-critical bug. Merge → `dev`.
- `hotfix/<slug>` — critical prod bug. Merge → `main` **and** `dev`.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat(data-engine): h1-001 scaffold Redis publisher`.

PRs are opened and merged manually on GitHub (this repo does not use the `gh` CLI). See [`AGENTS.md`](./AGENTS.md) §12 for the full workflow.

## Documentation

- **[spec.md](./spec.md)** — Full product spec, 5 user stories, hard invariants.
- **[AGENTS.md](./AGENTS.md)** — Rules the AI agent follows on this project.
- **[TASKS.md](./TASKS.md)** — Current progress, story status, dev log.

## License

[MIT](./LICENSE) © 2026 Luiggi.
