---
description: Genera un commit Conventional Commits a partir de los cambios en staging
agent: build
---

Pending changes:
!`git status --short`

Staged diff:
!`git diff --cached --stat`

Re-read @spec.md to remind yourself of the project context (NestJS data engine + FastAPI analytics engine, hexagonal, OWASP).

Produce a Conventional Commits message:
- Subject line: `<type>(<scope>): <description>` where `scope` is one of `data-engine`, `analytics-engine`, `infra`, `risk`, `spec`, `docs`.
- Types limited to: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `build`, `ci`.
- Body: 1-3 short bullets explaining the *why*, not the *what*.
- Footer: reference any user story from @spec.md section 5 (e.g. `Refs: Historia 2`).

Then:
1. Stage the listed files (only those the user clearly intends — ask if ambiguous).
2. Create the commit with the generated message.
3. Do NOT push.

If the diff touches Domain or Application layers, double-check the commit subject reflects that scope.
