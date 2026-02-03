#!/usr/bin/env node
/**
 * HERMES Node.js Module - AppData Session Reader
 * 
 * Shared code for reading session data from VS Code's AppData storage.
 * Can be used by both HERMES scripts and qopilot extension.
 * 
 * Location: monorepos/hermes/packages/session-reader/
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// AppData path detection (works on Windows)
function getAppDataPath() {
  const isInsiders = process.env.VSCODE_INSIDERS || true; // Default to insiders
  const appName = isInsiders ? 'Code - Insiders' : 'Code';
  return path.join(os.homedir(), 'AppData', 'Roaming', appName, 'User', 'workspaceStorage');
}

// Read session JSON by ID
function readSession(sessionId, workspaceHash) {
  const appData = getAppDataPath();
  const sessionsDir = path.join(appData, workspaceHash, 'chatSessions');
  const sessionFile = path.join(sessionsDir, `${sessionId}.json`);
  
  if (!fs.existsSync(sessionFile)) {
    return null;
  }
  
  return JSON.parse(fs.readFileSync(sessionFile, 'utf8'));
}

// Get last N requests from a session
function getLastRequests(session, n = 3) {
  const requests = session.requests || [];
  return requests.slice(-n).map(req => ({
    userMessage: req.message?.text,
    agentResponse: extractResponse(req.response),
    timestamp: req.timestamp || null,
  }));
}

// Extract text response from response array
function extractResponse(response) {
  if (!response) return null;
  
  const parts = [];
  for (const r of response) {
    // Skip thinking blocks
    if (r.kind === 'thinking') continue;
    
    // Get markdown content
    if (r.kind === 'markdownContent' && r.content?.value) {
      parts.push(r.content.value);
    }
    
    // Get plain value strings (non-thinking)
    if (r.value && typeof r.value === 'string' && r.value.trim()) {
      parts.push(r.value);
    }
  }
  
  return parts.join('\n\n') || null;
}

// Find sessions by title pattern
function findSessionsByTitle(workspaceHash, pattern) {
  const appData = getAppDataPath();
  const sessionsDir = path.join(appData, workspaceHash, 'chatSessions');
  
  if (!fs.existsSync(sessionsDir)) return [];
  
  const files = fs.readdirSync(sessionsDir).filter(f => f.endsWith('.json'));
  const matches = [];
  
  for (const f of files) {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(sessionsDir, f), 'utf8'));
      const title = data.customTitle || '';
      
      if (title.toLowerCase().includes(pattern.toLowerCase())) {
        matches.push({
          id: f.replace('.json', ''),
          title,
          requestCount: (data.requests || []).length,
          lastActivity: data.lastMessageTime || data.creationDate,
        });
      }
    } catch (e) {}
  }
  
  return matches.sort((a, b) => new Date(b.lastActivity) - new Date(a.lastActivity));
}

// Check if session is busy (has incomplete response)
function isSessionBusy(session) {
  const requests = session.requests || [];
  if (requests.length === 0) return false;
  
  const lastReq = requests[requests.length - 1];
  const response = lastReq.response || [];
  
  // If last response has no markdown content, agent may still be processing
  const hasContent = response.some(r => 
    r.kind === 'markdownContent' || 
    (r.value && typeof r.value === 'string' && r.value.trim() && r.kind !== 'thinking')
  );
  
  return !hasContent;
}

// CLI interface
if (require.main === module) {
  const args = process.argv.slice(2);
  const cmd = args[0];
  
  if (cmd === 'read') {
    const [, sessionId, hash] = args;
    if (!sessionId || !hash) {
      console.log('Usage: node session-reader.js read <sessionId> <workspaceHash>');
      process.exit(1);
    }
    const session = readSession(sessionId, hash);
    const last = getLastRequests(session, 1)[0];
    console.log('=== LAST EXCHANGE ===');
    console.log('User:', last?.userMessage?.slice(0, 200));
    console.log('Agent:', last?.agentResponse?.slice(0, 500));
  }
  
  else if (cmd === 'find') {
    const [, pattern, hash] = args;
    if (!pattern || !hash) {
      console.log('Usage: node session-reader.js find <pattern> <workspaceHash>');
      process.exit(1);
    }
    const matches = findSessionsByTitle(hash, pattern);
    console.log(JSON.stringify(matches, null, 2));
  }
  
  else {
    console.log('HERMES Session Reader');
    console.log('Commands:');
    console.log('  read <sessionId> <hash>  - Read last exchange');
    console.log('  find <pattern> <hash>    - Find sessions by title');
  }
}

module.exports = {
  getAppDataPath,
  readSession,
  getLastRequests,
  extractResponse,
  findSessionsByTitle,
  isSessionBusy,
};
