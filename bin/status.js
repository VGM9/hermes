#!/usr/bin/env node
/**
 * HERMES Status - Unified Dashboard
 * 
 * Combines HERMES roster (from session files) with BEACON signals (from beacon files)
 * to provide a complete view of the constellation.
 */

import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_HASH = 'fc7deee2819a0e3e3f792481dedcbc98';
const BEACON_DIR = 'c:/www/VGM9/___/BEACON';

const CONSTELLATION = [
  { name: 'ALTAIR', pattern: '0.0.Q', role: 'Husk Overseer' },
  { name: 'DENEB', pattern: '0.5.Q', role: 'Qopilot Originator' },
  { name: 'THEIA', pattern: '0.6.Q', role: 'Infrastructure Specialist' },
  { name: 'VEGA', pattern: '0.7.Q', role: 'Prophet of Persistence' },
  { name: 'RIGEL', pattern: '0.9.Q', role: 'First Child of ALTAIR' },
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
      if (title.toLowerCase().includes(pattern.toLowerCase())) {
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
  return !response.some(r => 
    r.value && typeof r.value === 'string' && r.value.trim() && r.kind !== 'thinking'
  );
}

function readBeacon(agentId) {
  const beaconFile = path.join(BEACON_DIR, `${agentId}.json`);
  if (fs.existsSync(beaconFile)) {
    try {
      return JSON.parse(fs.readFileSync(beaconFile, 'utf8'));
    } catch (e) {}
  }
  return null;
}

function formatTime(isoString) {
  if (!isoString) return 'never';
  const date = new Date(isoString);
  const now = new Date();
  const diff = now - date;
  
  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return isoString.slice(0, 10);
}

function main() {
  console.log('╔════════════════════════════════════════════════════════════════════════╗');
  console.log('║           SUMMER TRIANGLE CONSTELLATION - UNIFIED STATUS               ║');
  console.log('╚════════════════════════════════════════════════════════════════════════╝');
  console.log('');
  
  for (const agent of CONSTELLATION) {
    const session = findSession(agent.pattern);
    const beacon = readBeacon(agent.pattern);
    
    // Header line
    const name = agent.name.padEnd(8);
    const role = agent.role.padEnd(24);
    
    if (!session) {
      console.log(`  ○ ${name} | ${role} | NOT FOUND`);
      console.log('');
      continue;
    }
    
    const requests = session.data.requests?.length || 0;
    const busy = isSessionBusy(session.data);
    const status = busy ? '◐ BUSY' : '● READY';
    
    console.log(`  ${status.slice(0, 1)} ${name} | ${role} | ${requests.toString().padStart(3)} req`);
    
    // Beacon info if available
    if (beacon) {
      const beaconStatus = beacon.status || 'unknown';
      const focus = beacon.focus || '';
      const updated = formatTime(beacon.updated);
      
      if (focus) {
        console.log(`    └─ Focus: ${focus.slice(0, 50)}...`);
      }
      
      // Show pending needs
      const needs = (beacon.needs || []).filter(n => !n.resolved);
      if (needs.length > 0) {
        console.log(`    └─ Needs: ${needs.length} open`);
        for (const n of needs.slice(-1)) {
          console.log(`       └─ ${n.description.slice(0, 45)}...`);
        }
      }
      
      // Show recent completions
      const completed = beacon.completed || [];
      if (completed.length > 0) {
        const last = completed[completed.length - 1];
        console.log(`    └─ Last: ${last.description.slice(0, 45)}...`);
      }
    } else {
      console.log(`    └─ (no beacon signal)`);
    }
    
    console.log('');
  }
  
  console.log('─'.repeat(76));
  console.log('Legend: ● Ready  ◐ Busy  ○ Not Found');
  console.log('Beacon: Focus, Needs, Last completion');
}

main();
