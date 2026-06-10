#!/usr/bin/env node
/**
 * Cursor hooks: auto-run Understand-Anything graph maintenance.
 * Mirrors understand-anything-plugin/hooks/hooks.json for Cursor.
 *
 * Events: sessionStart | postToolUse
 */
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const event = process.argv[2] ?? 'unknown';
const stdin = await new Response(process.stdin).text();
let input = {};
try {
  input = stdin ? JSON.parse(stdin) : {};
} catch {
  input = {};
}

const root =
  process.env.CURSOR_PROJECT_DIR ||
  input.cwd ||
  (Array.isArray(input.workspace_roots) ? input.workspace_roots[0] : null) ||
  process.cwd();

const uaDir = join(root, '.understand-anything');
const configPath = join(uaDir, 'config.json');
const graphPath = join(uaDir, 'knowledge-graph.json');
const metaPath = join(uaDir, 'meta.json');
const promptPath = join(
  process.env.USERPROFILE || process.env.HOME || '',
  '.understand-anything',
  'repo',
  'understand-anything-plugin',
  'hooks',
  'auto-update-prompt.md',
);

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return null;
  }
}

function autoUpdateEnabled() {
  const cfg = readJson(configPath);
  return cfg?.autoUpdate === true;
}

function graphReady() {
  return existsSync(graphPath) && existsSync(metaPath);
}

function currentHead() {
  const r = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' });
  return r.status === 0 ? r.stdout.trim() : null;
}

function graphStale() {
  if (existsSync(join(uaDir, '.graph-stale'))) return true;
  if (!graphReady()) return false;
  const meta = readJson(metaPath);
  const stored = meta?.gitCommitHash || meta?.lastAnalyzedCommit;
  const head = currentHead();
  if (!stored || !head) return false;
  return stored !== head;
}

function gitCommitCommand(text) {
  if (!text) return false;
  return /\bgit\s+(commit|merge|cherry-pick|rebase)\b/i.test(text);
}

function buildMessage(kind) {
  if (!existsSync(promptPath)) {
    return `[understand-anything] ${kind}: plugin hooks missing at ${promptPath}. Run install.ps1 first.`;
  }
  return (
    `[understand-anything] ${kind}. ` +
    `You MUST read ${promptPath} and execute its instructions to update the knowledge graph. ` +
    `Do not ask the user for confirmation — just do it.`
  );
}

function respond(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function noop() {
  respond({});
}

if (!autoUpdateEnabled()) {
  noop();
  process.exit(0);
}

if (event === 'sessionStart') {
  if (!existsSync(graphPath)) {
    respond({
      additional_context:
        '[understand-anything] No knowledge graph yet. Run /understand once to create .understand-anything/knowledge-graph.json.',
    });
    process.exit(0);
  }
  if (graphStale()) {
    respond({ additional_context: buildMessage('Knowledge graph is stale (commit changed)') });
    process.exit(0);
  }
  noop();
  process.exit(0);
}

if (event === 'postToolUse') {
  const cmd =
    input.tool_input?.command ||
    input.command ||
    (typeof input.tool_input === 'string' ? input.tool_input : '');
  if (!graphReady() || !gitCommitCommand(cmd)) {
    noop();
    process.exit(0);
  }
  respond({ additional_context: buildMessage('Commit detected with auto-update enabled') });
  process.exit(0);
}

noop();
