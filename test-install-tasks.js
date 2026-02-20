#!/usr/bin/env node
/**
 * test-install-tasks.js — Integration tests for install-tasks.js
 *
 * Creates isolated temp workspaces, runs the installer, asserts output.
 * No VS Code or pywinauto required. Safe to run in CI or any workspace.
 *
 * Usage:  node test-install-tasks.js
 */

import { mkdtempSync, readFileSync, writeFileSync, existsSync, rmSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { spawnSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const HERMES_DIR = dirname(fileURLToPath(import.meta.url));
const INSTALL_SCRIPT = join(HERMES_DIR, 'install-tasks.js');

let passed = 0;
let failed = 0;

function assert(condition, label) {
  if (condition) {
    console.log(`  ✓ ${label}`);
    passed++;
  } else {
    console.error(`  ✗ ${label}`);
    failed++;
  }
}

function runInstaller(env = {}, args = []) {
  return spawnSync('node', [INSTALL_SCRIPT, ...args], {
    env: { ...process.env, ...env },
    encoding: 'utf8',
  });
}

function withTempDir(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'hermes-test-'));
  try {
    fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

console.log('\ntest: INIT_CWD sets workspace root');
withTempDir(dir => {
  const result = runInstaller({ INIT_CWD: dir });
  const tasksPath = join(dir, '.vscode', 'tasks.json');
  assert(result.status === 0, 'exits 0');
  assert(existsSync(tasksPath), 'tasks.json created');
  const tasks = JSON.parse(readFileSync(tasksPath, 'utf8'));
  const labels = tasks.tasks.map(t => t.label);
  assert(labels.includes('hermes:ensure-daemon'), 'hermes:ensure-daemon present');
  assert(labels.includes('hermes:wake'), 'hermes:wake present');
  assert(tasks.tasks.find(t => t.label === 'hermes:wake')
    ?.runOptions?.runOn === 'folderOpen', 'hermes:wake has runOn:folderOpen');
});

console.log('\ntest: --root flag overrides INIT_CWD');
withTempDir(dir => {
  withTempDir(wrongDir => {
    const result = runInstaller({ INIT_CWD: wrongDir }, ['--root', dir]);
    const tasksPath = join(dir, '.vscode', 'tasks.json');
    assert(result.status === 0, 'exits 0');
    assert(existsSync(tasksPath), 'tasks.json in --root dir, not INIT_CWD dir');
    assert(!existsSync(join(wrongDir, '.vscode', 'tasks.json')), 'INIT_CWD dir untouched');
  });
});

console.log('\ntest: idempotent — re-run replaces hermes tasks, preserves others');
withTempDir(dir => {
  // First run
  runInstaller({ INIT_CWD: dir });
  // Inject a non-hermes task
  const tasksPath = join(dir, '.vscode', 'tasks.json');
  const first = JSON.parse(readFileSync(tasksPath, 'utf8'));
  first.tasks.push({ label: 'my-custom-task', type: 'shell', command: 'echo hi' });
  writeFileSync(tasksPath, JSON.stringify(first, null, '\t'));
  // Second run
  const result = runInstaller({ INIT_CWD: dir });
  const second = JSON.parse(readFileSync(tasksPath, 'utf8'));
  const labels = second.tasks.map(t => t.label);
  assert(result.status === 0, 'exits 0 on second run');
  assert(labels.includes('my-custom-task'), 'non-hermes task preserved');
  assert(labels.filter(l => l === 'hermes:wake').length === 1, 'hermes:wake not duplicated');
});

console.log('\ntest: fails cleanly with no INIT_CWD and no --root');
withTempDir(_dir => {
  const result = runInstaller({ INIT_CWD: '' });
  assert(result.status === 1, 'exits 1');
  assert(result.stderr.includes('Cannot resolve workspace root'), 'helpful error message');
});

// ── Summary ───────────────────────────────────────────────────────────────────

console.log(`\n${passed + failed} assertions: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
