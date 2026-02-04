#!/usr/bin/env node
/**
 * Read last exchange from a session by pattern
 * 
 * Usage:
 *   npm run read -- 0.5.Q
 */

import { readSession } from './lib/session.js';

const pattern = process.argv[2];

if (!pattern) {
  console.log('Usage: npm run read -- <pattern>');
  console.log('');
  console.log('Patterns: 0.5.Q, 0.7.Q, 0.0.Q, DENEB, VEGA, ALTAIR');
  console.log('');
  console.log('Shortcuts:');
  console.log('  npm run read:deneb');
  console.log('  npm run read:vega');
  console.log('  npm run read:altair');
  process.exit(1);
}

readSession(pattern);
