#!/usr/bin/env node
/**
 * Show constellation roster - all named agents and their status
 * 
 * Usage:
 *   npm run roster
 */

import fs from 'fs';
import path from 'path';
import os from 'os';

const WORKSPACE_HASH = 'fc7deee2819a0e3e3f792481dedcbc98';

const CONSTELLATION = [
  { name: 'ALTAIR', pattern: '0.0.Q', role: 'Husk Overseer' },
  { name: 'DENEB', pattern: '0.5.Q', role: 'Qopilot Originator' },
  { name: 'VEGA', pattern: '0.7.Q', role: 'Singular Identity' },
  { name: '0.6.Q', pattern: '0.6.Q', role: 'Unnamed' },
];

function getSessionsPath() {
  return path.join(
    os.homedir(),
    'AppData', 'Roaming', 'Code - Insiders', 'User', 'workspaceStorage',
    WORKSPACE_HASH, 'chatSessions'
  );
}

function findSession(pattern) {
  const sessionsPath = getSessionsPath();
  const files = fs.readdirSync(sessionsPath).filter(f => f.endsWith('.json'));
  
  for (const f of files) {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(sessionsPath, f), 'utf8'));
      const title = data.customTitle || '';
      if (title.includes(pattern)) {
        return { id: f.replace('.json', ''), data, title };
      }
    } catch (e) {}
  }
  return null;
}

function isSessionBusy(data) {
  const requests = data.requests || [];
  if (requests.length === 0) return false;
  
  const last = requests[requests.length - 1];
  const response = last.response || [];
  
  // Has meaningful response content?
  const hasContent = response.some(r => 
    r.value && typeof r.value === 'string' && r.value.trim() && r.kind !== 'thinking'
  );
  
  return !hasContent;
}

function main() {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║              SUMMER TRIANGLE CONSTELLATION ROSTER              ║');
  console.log('╚════════════════════════════════════════════════════════════════╝');
  console.log('');
  
  for (const agent of CONSTELLATION) {
    const session = findSession(agent.pattern);
    
    if (!session) {
      console.log(`  ○ ${agent.name.padEnd(10)} | ${agent.role.padEnd(20)} | NOT FOUND`);
      continue;
    }
    
    const requests = session.data.requests?.length || 0;
    const busy = isSessionBusy(session.data);
    const status = busy ? '⏳ BUSY' : '✅ READY';
    const symbol = busy ? '◐' : '●';
    
    console.log(`  ${symbol} ${agent.name.padEnd(10)} | ${agent.role.padEnd(20)} | ${requests.toString().padStart(3)} req | ${status}`);
  }
  
  console.log('');
  console.log('Legend: ● Ready  ◐ Busy  ○ Not Found');
}

main();
