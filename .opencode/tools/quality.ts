import { tool } from '@opencode-ai/plugin';
import { execFileSync } from 'child_process';
import { existsSync, readdirSync, readFileSync, statSync } from 'fs';
import * as path from 'path';

const ROOT = process.cwd();

const run = (cmd: string, args: string[], opts: { cwd?: string; env?: NodeJS.ProcessEnv } = {}): string => {
    try {
        return execFileSync(cmd, args, {
            encoding: 'utf8',
            cwd: opts.cwd ?? ROOT,
            env: opts.env ?? process.env,
            stdio: ['ignore', 'pipe', 'pipe'],
            maxBuffer: 50 * 1024 * 1024,
        });
    } catch (e: any) {
        const out = (e.stdout ?? '') + (e.stderr ?? '');
        return `[exit ${e.status ?? '?'}]\n${out}`;
    }
};

export const typecheck_data_engine = tool({
    description: 'Run tsc --noEmit on the data-engine. Returns the output (errors or success).',
    args: {},
  async execute() {
        const cwd = path.join(ROOT, 'apps/data-engine');
        if (!existsSync(cwd))
            return {
                title: 'typecheck_data_engine',
                output: `SKIP: ${cwd} does not exist. Run init_data_engine first.`,
            };
        if (!existsSync(path.join(cwd, 'node_modules')))
            return {
                title: 'typecheck_data_engine',
                output: 'SKIP: node_modules missing. Run `npm install` in apps/data-engine first.',
            };
        return {
            title: 'typecheck_data_engine',
            output: run('npx', ['tsc', '--noEmit'], { cwd }),
        };
    },
});

export const lint_data_engine = tool({
    description: 'Run eslint on the data-engine src tree.',
    args: {},
  async execute() {
        const cwd = path.join(ROOT, 'apps/data-engine');
        if (!existsSync(cwd))
            return {
                title: 'lint_data_engine',
                output: `SKIP: ${cwd} does not exist. Run init_data_engine first.`,
            };
        if (!existsSync(path.join(cwd, 'node_modules')))
            return {
                title: 'lint_data_engine',
                output: 'SKIP: node_modules missing. Run `npm install` in apps/data-engine first.',
            };
        return {
            title: 'lint_data_engine',
            output: run('npx', ['eslint', 'src'], { cwd }),
        };
    },
});

export const test_data_engine = tool({
    description: 'Run jest in the data-engine. Tail-friendly output.',
    args: {},
  async execute() {
        const cwd = path.join(ROOT, 'apps/data-engine');
        if (!existsSync(cwd))
            return {
                title: 'test_data_engine',
                output: `SKIP: ${cwd} does not exist. Run init_data_engine first.`,
            };
        if (!existsSync(path.join(cwd, 'node_modules')))
            return {
                title: 'test_data_engine',
                output: 'SKIP: node_modules missing. Run `npm install` in apps/data-engine first.',
            };
        return {
            title: 'test_data_engine',
            output: run('npx', ['jest', '--colors=false'], { cwd }),
        };
    },
});

export const test_analytics_engine = tool({
    description: 'Run pytest in the analytics-engine.',
    args: {},
  async execute() {
        const cwd = path.join(ROOT, 'apps/analytics-engine');
        if (!existsSync(cwd))
            return {
                title: 'test_analytics_engine',
                output: `SKIP: ${cwd} does not exist. Run init_analytics_engine first.`,
            };
        return {
            title: 'test_analytics_engine',
            output: run('python3', ['-m', 'pytest', '-v', '--tb=short'], { cwd }),
        };
    },
});

const walk = (dir: string, out: string[] = []): string[] => {
    if (!existsSync(dir)) return out;
    for (const entry of readdirSync(dir)) {
        const p = path.join(dir, entry);
        const st = statSync(p);
        if (st.isDirectory()) walk(p, out);
        else out.push(p);
    }
    return out;
};

const importPatterns: Record<string, RegExp[]> = {
    data_engine: [/^import .* from ["'](ioredis|ws|ccxt|axios|@nestjs\/websockets)["']/m],
    analytics_engine: [/^import .* from ["'](ccxt|redis|ta|pandas|numpy|fastapi|uvicorn|tensorflow|torch)["']/m],
};

export const arch_lint = tool({
    description:
        'Read-only hexagonal architecture lint. Reports any Domain-layer file that imports from Infrastructure, and any Application-layer file that imports concrete adapter packages. Returns PASS or a list of violations.',
    args: {},
  async execute() {
        const violations: string[] = [];

        const de = path.join(ROOT, 'apps/data-engine/src/domain');
        const ae = path.join(ROOT, 'apps/analytics-engine/app/domain');

        for (const [engine, root] of [
            ['data-engine', de],
            ['analytics-engine', ae],
        ] as const) {
            if (!existsSync(root)) continue;
            const files = walk(root).filter((f) => /\.(ts|py)$/.test(f));
            const ban = importPatterns[engine === 'data-engine' ? 'data_engine' : 'analytics_engine'];
            for (const f of files) {
                const text = readFileSync(f, 'utf8');
                for (const re of ban) {
                    if (re.test(text)) violations.push(`${f}: domain-layer import violates hexagonal rules`);
                    break;
                }
            }
        }

        const aeApp = path.join(ROOT, 'apps/analytics-engine/app/application');
        const deApp = path.join(ROOT, 'apps/data-engine/src/application');
        const appRoots = [deApp, aeApp];
        const appBans: RegExp[] = [
            /from\s+["'](ccxt|ioredis|ws|axios|fastapi)["']/,
            /import\s+(ccxt|ioredis|ws|axios|fastapi)\b/,
        ];
        for (const root of appRoots) {
            if (!existsSync(root)) continue;
            const files = walk(root).filter((f) => /\.(ts|py)$/.test(f));
            for (const f of files) {
                const text = readFileSync(f, 'utf8');
                for (const re of appBans) {
                    if (re.test(text))
                        violations.push(`${f}: application-layer imports a concrete adapter (use a port instead)`);
                    break;
                }
            }
        }

        if (!violations.length) return { title: 'arch_lint', output: 'PASS: no hexagonal violations detected.' };
        return {
            title: 'arch_lint',
            output: `NEEDS FIXES (${violations.length}):\n` + violations.map((v) => `  - ${v}`).join('\n'),
        };
    },
});

const SECRET_REGEX = /(api[_-]?key|secret|private[_-]?key|passphrase)\s*[:=]\s*['"][A-Za-z0-9_\-/.+=]{16,}['"]/i;

export const secret_scan = tool({
    description:
        'Grep the codebase for likely-hardcoded secrets. Excludes .env.example, config.json, .git/, node_modules/, __pycache__/, and binary files. Reports file:line for each match.',
    args: {},
  async execute() {
        const skipDirs = new Set(['node_modules', '__pycache__', '.git', 'dist', '.venv', 'venv', 'env', '.opencode']);
        const skipFiles = new Set(['.env.example', 'config.json']);

        const findings: string[] = [];
        const visit = (dir: string) => {
            if (!existsSync(dir)) return;
            for (const entry of readdirSync(dir)) {
                const p = path.join(dir, entry);
                if (skipDirs.has(entry)) continue;
                const st = statSync(p);
                if (st.isDirectory()) visit(p);
                else {
                    if (skipFiles.has(entry)) continue;
                    if (!/\.(ts|js|py|json|yml|yaml|env|md|sh)$/.test(entry)) continue;
                    if (entry.endsWith('.example')) continue;
                    const text = readFileSync(p, 'utf8');
                    const lines = text.split('\n');
                    for (let i = 0; i < lines.length; i++) {
                        if (SECRET_REGEX.test(lines[i])) findings.push(`${p}:${i + 1}: ${lines[i].trim()}`);
                    }
                }
            }
        };

        visit(ROOT);

        if (!findings.length) return { title: 'secret_scan', output: 'PASS: no hardcoded secrets found.' };
        return {
            title: 'secret_scan',
            output: `NEEDS FIXES (${findings.length}):\n` + findings.map((f) => `  - ${f}`).join('\n'),
        };
    },
});
