#!/usr/bin/env node
/**
 * Find sessions by title pattern
 * 
 * Usage:
 *   npm run find -- 0.5
 *   npm run find -- VEGA
 *   node bin/find-sessions.js AS/
 */

import fs from 'fs';
import path from 'path';
import os from 'os';

const WORKSPACE_HASH = 'fc7deee2819a0e3e3f792481dedcbc98';

function getSessionsPath() {
  return path.join(
    os.homedir(),
    'AppData', 'Roaming', 'Code - Insiders', 'User', 'workspaceStorage',
    WORKSPACE_HASH, 'chatSessions'
  );
}

function main() {
  const pattern = process.argv[2] || '';
  const sessionsPath = getSessionsPath();
  
  if (!fs.existsSync(sessionsPath)) {
    console.log('Sessions path not found:', sessionsPath);
    process.exit(1);
  }
  
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
  
  // Sort by last activity
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

main();
