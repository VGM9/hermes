#!/usr/bin/env node
/**
 * install-tasks.js — Deploy hermes VS Code tasks into the workspace.
 *
 * Writes hermes:* task entries into .vscode/tasks.json of the target workspace.
 * Existing non-hermes tasks are untouched. Idempotent: re-running replaces
 * hermes tasks in place.
 *
 * Workspace root resolution (in priority order):
 *   1. --root /abs/path      explicit override
 *   2. $INIT_CWD             set by npm to the directory where `npm install`
 *                            was invoked — the workspace root the user declared
 *
 * Usage:
 *   npm run deploy-tasks              # uses $INIT_CWD
 *   npm run deploy-tasks -- --root /abs/path/to/workspace
 *
 * Also runs automatically as postinstall.
 */

import {
  readFileSync, writeFileSync, existsSync,
  mkdirSync,
} from 'fs';
import { join, basename, dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const HERMES_DIR = dirname(fileURLToPath(import.meta.url));

// ── Workspace root resolution ─────────────────────────────────────────────────

/**
 * Resolve the target workspace root.
 *   1. --root flag (explicit override)
 *   2. $INIT_CWD — npm sets this to the directory where `npm install` was run
 */
function resolveWorkspaceRoot(args) {
  const rootFlag = args.indexOf('--root');
  if (rootFlag !== -1 && args[rootFlag + 1]) return resolve(args[rootFlag + 1]);
  if (process.env.INIT_CWD) return resolve(process.env.INIT_CWD);
  return null;
}

// ── Task definitions ──────────────────────────────────────────────────────────

/**
 * Returns hermes task definitions with cwd resolved relative to workspaceRoot.
 * Uses ${workspaceFolder} so tasks survive workspace moves.
 */
function hermesTasksFor(workspaceRoot) {
  const rel = resolve(HERMES_DIR)
    .slice(resolve(workspaceRoot).length)
    .replace(/\\/g, '/')
    .replace(/^\//, '');

  const cwd = `\${workspaceFolder}/${rel}`;

  return [
    {
      label: 'hermes:ensure-daemon',
      detail: 'npm run daemon:ensure — idempotent start. No-op if already running.',
      type: 'shell', command: 'npm', args: ['run', 'daemon:ensure'],
      options: { cwd },
      isBackground: true,
      runOptions: { runOn: 'folderOpen' },
      presentation: { reveal: 'silent', panel: 'shared' },
    },
    {
      label: 'hermes:wake',
      detail: 'npm run wake — wait for chat ready, send wake message. Runs on every folderOpen.',
      type: 'shell', command: 'npm', args: ['run', 'wake'],
      options: { cwd },
      runOptions: { runOn: 'folderOpen' },
      presentation: { reveal: 'silent', panel: 'shared' },
    },
    {
      label: 'hermes:detect-update',
      detail: 'npm run update:detect — report if VS Code update button is present, no click.',
      type: 'shell', command: 'npm', args: ['run', 'update:detect'],
      options: { cwd },
      presentation: { reveal: 'always', panel: 'shared' },
    },
    {
      label: 'hermes:update-and-wake',
      detail: 'npm run update:apply — click update button + handle dialog.',
      type: 'shell', command: 'npm', args: ['run', 'update:apply'],
      options: { cwd },
      isBackground: true,
      presentation: { reveal: 'always', panel: 'shared' },
    },
    {
      label: 'hermes:daemon-stop',
      detail: 'npm run daemon:stop — stop the running daemon.',
      type: 'shell', command: 'npm', args: ['run', 'daemon:stop'],
      options: { cwd },
      presentation: { reveal: 'always', panel: 'shared' },
    },
  ];
}

// ── tasks.json merge ──────────────────────────────────────────────────────────

function readTasksJson(path) {
  if (!existsSync(path)) return { version: '2.0.0', tasks: [] };
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (e) {
    throw new Error(`Failed to parse ${path}: ${e.message}`);
  }
}

function mergeTasks(existing, incoming) {
  const kept = (existing.tasks ?? []).filter(t => !t.label?.startsWith('hermes:'));
  return { ...existing, tasks: [...kept, ...incoming] };
}

/**
 * Walk UP from workspaceRoot toward the filesystem root.
 * If any ancestor directory has a .vscode/tasks.json that already contains
 * hermes tasks, return that ancestor path — we should not write a second copy
 * into a nested workspace root.
 */
function findAncestorWithHermesTasks(workspaceRoot) {
  let dir = dirname(resolve(workspaceRoot));
  while (true) {
    const candidate = join(dir, '.vscode', 'tasks.json');
    if (existsSync(candidate)) {
      try {
        const data = JSON.parse(readFileSync(candidate, 'utf8'));
        if ((data.tasks ?? []).some(t => t.label?.startsWith('hermes:'))) {
          return dir;
        }
      } catch { /* unreadable — keep walking */ }
    }
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

// ── Entry point ───────────────────────────────────────────────────────────────

function main() {
  const args = process.argv.slice(2);
  const workspaceRoot = resolveWorkspaceRoot(args);

  if (!workspaceRoot) {
    console.error('[hermes:install-tasks] Cannot resolve workspace root.');
    console.error('  Run via: npm install (sets $INIT_CWD), or pass --root /abs/path');
    process.exit(1);
  }

  // Refuse to write into a nested workspace root when an ancestor already has
  // hermes tasks — that would create duplicate folderOpen triggers.
  const ancestor = findAncestorWithHermesTasks(workspaceRoot);
  if (ancestor) {
    console.error(`[hermes:install-tasks] Ancestor workspace at ${ancestor} already has hermes tasks.`);
    console.error(`  Writing here would create duplicate folderOpen triggers. Run from the top-level workspace root instead.`);
    process.exit(1);
  }

  const vscodePath = join(workspaceRoot, '.vscode');
  const tasksPath  = join(vscodePath, 'tasks.json');

  if (!existsSync(vscodePath)) mkdirSync(vscodePath, { recursive: true });

  const updated = mergeTasks(readTasksJson(tasksPath), hermesTasksFor(workspaceRoot));
  writeFileSync(tasksPath, JSON.stringify(updated, null, '\t') + '\n', 'utf8');
  console.log(`[hermes:install-tasks] Wrote hermes tasks → ${tasksPath}`);
  // Write hermes_config.local.jsonc with the workspace-specific window_pattern.
  // Gitignored. Overlays the shipped hermes_config.jsonc at runtime.
  const windowPattern = basename(workspaceRoot);
  const localConfigPath = join(HERMES_DIR, 'hermes_config.local.jsonc');
  const localConfig = `// Auto-generated by install-tasks.js — do not commit.\n// Overrides hermes_config.jsonc for this workspace.\n${JSON.stringify({ window_pattern: windowPattern }, null, '\t')}\n`;
  writeFileSync(localConfigPath, localConfig, 'utf8');
  console.log(`[hermes:install-tasks] Wrote local config \u2192 ${localConfigPath} (window_pattern: "${windowPattern}")`);}

main();
