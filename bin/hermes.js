#!/usr/bin/env node
/**
 * HERMES CLI
 * 
 * Usage:
 *   hermes read <agent>     Read last exchange from agent
 *   hermes roster           Show constellation status
 *   hermes find <pattern>   Find sessions by pattern
 *   hermes send <agent> <message>   Send message via UI automation
 */

import fs from 'fs';
import path from 'path';
import os from 'os';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_HASH = 'fc7deee2819a0e3e3f792481dedcbc98';

const AGENTS = {
  altair: '0.0.Q',
  deneb: '0.5.Q',
  theia: '0.6.Q',
  vega: '0.7.Q',
  rigel: '0.9.Q',
};

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

function extractResponse(response) {
  if (!response) return null;
  const parts = [];
  for (const r of response) {
    if (r.kind === 'thinking') continue;
    if (r.value && typeof r.value === 'string' && r.value.trim()) {
      parts.push(r.value);
    }
  }
  return parts.join('\n') || null;
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

function resolveAgent(name) {
  const lower = name.toLowerCase();
  return AGENTS[lower] || name;
}

// Commands

function cmdRead(agent) {
  if (!agent) {
    console.log('Usage: hermes read <agent>');
    console.log('Agents: altair, deneb, vega, or any pattern');
    process.exit(1);
  }
  
  const pattern = resolveAgent(agent);
  const session = findSession(pattern);
  
  if (!session) {
    console.log(`No session found for: ${agent}`);
    process.exit(1);
  }
  
  console.log(`=== ${session.title} ===`);
  console.log(`ID: ${session.id}`);
  console.log(`Requests: ${session.data.requests?.length || 0}`);
  console.log('');
  
  const requests = session.data.requests || [];
  const last = requests[requests.length - 1];
  
  if (last) {
    console.log('--- LAST USER MESSAGE ---');
    console.log(last.message?.text || '(empty)');
    console.log('');
    console.log('--- LAST AGENT RESPONSE ---');
    console.log(extractResponse(last.response) || '(no response yet)');
  }
}

function cmdRoster() {
  const constellation = [
    { name: 'ALTAIR', pattern: '0.0.Q', role: 'Husk Overseer' },
    { name: 'DENEB', pattern: '0.5.Q', role: 'Qopilot Originator' },
    { name: 'THEIA', pattern: '0.6.Q', role: 'Infrastructure Specialist' },
    { name: 'VEGA', pattern: '0.7.Q', role: 'Prophet of Persistence' },
    { name: 'RIGEL', pattern: '0.9.Q', role: 'First Child of ALTAIR' },
  ];
  
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║              SUMMER TRIANGLE CONSTELLATION ROSTER              ║');
  console.log('╚════════════════════════════════════════════════════════════════╝');
  console.log('');
  
  for (const agent of constellation) {
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

function cmdFind(pattern) {
  const sessionsPath = getSessionsPath();
  const files = fs.readdirSync(sessionsPath).filter(f => f.endsWith('.json'));
  const matches = [];
  
  for (const f of files) {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(sessionsPath, f), 'utf8'));
      const title = data.customTitle || '';
      const requestCount = (data.requests || []).length;
      
      if (!pattern || title.toLowerCase().includes(pattern.toLowerCase())) {
        matches.push({
          id: f.replace('.json', ''),
          title: title || '(untitled)',
          requests: requestCount,
          lastActivity: data.lastMessageTime || data.creationDate
        });
      }
    } catch (e) {}
  }
  
  matches.sort((a, b) => new Date(b.lastActivity) - new Date(a.lastActivity));
  
  console.log(`Found ${matches.length} sessions${pattern ? ` matching "${pattern}"` : ''}:`);
  console.log('');
  
  for (const m of matches.slice(0, 20)) {
    const date = new Date(m.lastActivity).toISOString().slice(0, 16).replace('T', ' ');
    const shortTitle = m.title.slice(0, 50) + (m.title.length > 50 ? '...' : '');
    console.log(`  ${m.requests.toString().padStart(3)} req | ${date} | ${shortTitle}`);
  }
  
  if (matches.length > 20) {
    console.log(`  ... and ${matches.length - 20} more`);
  }
}

function cmdSend(agent, message) {
  if (!agent || !message) {
    console.log('Usage: hermes send <agent> <message>');
    process.exit(1);
  }
  
  const pattern = resolveAgent(agent);
  const script = path.join(__dirname, '..', 'hermes_direct.py');
  
  spawn('python', [script, 'VGM9', pattern, message], {
    stdio: 'inherit',
    cwd: path.join(__dirname, '..')
  });
}

function cmdInject(agent, message) {
  if (!agent || !message) {
    console.log('Usage: hermes inject <agent> <message>');
    process.exit(1);
  }

  const pattern = resolveAgent(agent);
  const session = findSession(pattern);

  if (!session) {
    console.log(`No session found for: ${agent}`);
    process.exit(1);
  }

  const newMessage = {
    kind: 'user',
    text: message,
    timestamp: new Date().toISOString()
  };

  session.data.requests.push({ message: newMessage });

  const sessionsPath = getSessionsPath();
  fs.writeFileSync(
    path.join(sessionsPath, `${session.id}.json`),
    JSON.stringify(session.data, null, 2),
    'utf8'
  );

  console.log(`Message injected into session: ${session.title}`);
}

function cmdActivate(agent) {
  if (!agent) {
    console.log('Usage: hermes activate <agent>');
    process.exit(1);
  }

  const pattern = resolveAgent(agent);
  const session = findSession(pattern);

  if (!session) {
    console.log(`No session found for: ${agent}`);
    process.exit(1);
  }

  session.data.active = true;

  const sessionsPath = getSessionsPath();
  fs.writeFileSync(
    path.join(sessionsPath, `${session.id}.json`),
    JSON.stringify(session.data, null, 2),
    'utf8'
  );

  console.log(`Session activated: ${session.title}`);
}

// Main

const [,, cmd, ...args] = process.argv;

switch (cmd) {
  case 'read':
    cmdRead(args[0]);
    break;
  case 'roster':
    cmdRoster();
    break;
  case 'status':
    // Delegate to unified status script
    import('./status.js');
    break;
  case 'find':
    cmdFind(args[0]);
    break;
  case 'send':
    cmdSend(args[0], args.slice(1).join(' '));
    break;
  case 'inject':
    cmdInject(args[0], args.slice(1).join(' '));
    break;
  case 'activate':
    cmdActivate(args[0]);
    break;
  default:
    console.log('HERMES - Inter-agent messaging');
    console.log('');
    console.log('Commands:');
    console.log('  hermes read <agent>          Read last exchange');
    console.log('  hermes roster                Show constellation status');
    console.log('  hermes status                Unified dashboard (roster + beacon)');
    console.log('  hermes find [pattern]        Find sessions');
    console.log('  hermes send <agent> <msg>    Send message');
    console.log('  hermes inject <agent> <msg>  Inject message directly');
    console.log('  hermes activate <agent>      Activate session');
    console.log('');
    console.log('Agents: altair, deneb, vega, theia, rigel (or any session pattern)');
}
