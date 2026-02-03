# HERMES Architecture Analysis

**Date:** 2026-01-23  
**Agent:** ALTAIR/9 (0.0.Q)

## Your Questions Answered

### 1. Can you read agent messages from AppData?

**YES.** Implemented in `session_reader.js`:
```javascript
const session = readSession(sessionId, workspaceHash);
const last = getLastRequests(session, 1)[0];
console.log('Agent:', last.agentResponse);
```

This reads directly from:
```
C:/Users/victorb/AppData/Roaming/Code - Insiders/User/workspaceStorage/{hash}/chatSessions/{uuid}.json
```

### 2. Are these also hooks from qopilot you can use in HERMES?

**PARTIALLY.** Qopilot already has:
- `qopilot_get_session` - reads session by ID
- `qopilot_list_sessions` - lists sessions with Q-semver
- `qopilot_send_message` - writes to file-based inbox (limited)

What's MISSING:
- Direct message injection into existing sessions
- CLI access to session message API
- Internal VS Code command to send to specific session

### 3. What monorepo contains shared code?

**Proposed structure:**
```
monorepos/
├── hermes/                    ← NEW: Inter-agent messaging
│   └── packages/
│       ├── session-reader/    ← AppData session parsing
│       ├── ui-automation/     ← pywinauto wrappers (Windows)
│       └── protocol/          ← Message format, inbox schema
├── qopilot/                   ← Existing: Q-semver, tools
│   └── packages/
│       └── vscode-extension/  ← VS Code integration
└── appdata-path/              ← Existing: Path detection
```

### 4. How to stitch tools without reinventing wheels?

**Current reality:**
- `session_reader.js` - READ from AppData (Node)
- `hermes_v3.py` - WRITE via UI automation (Python/pywinauto)
- `qopilot extension` - VS Code internal tools

**Stitching pattern:**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Read Layer    │───▶│   Logic Layer   │───▶│   Write Layer   │
│ session_reader  │    │  hermes_core    │    │  UI or Internal │
│   (Node/JS)     │    │   (any lang)    │    │   (Python/TS)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 5. How to converse with minimal user disruption?

**Current (UI Automation):**
- Steals focus when typing
- User must yield window
- Visible cursor movement

**Better (Internal):**
- VS Code extension commands
- No focus steal
- Background operation

**Best (Ideal):**
- Direct API injection (doesn't exist yet)
- Like `code-insiders chat` but targeting existing session

### 6. Can we bypass UI automation via VS Code internal API?

**Not yet.** VS Code does NOT expose:
- `workbench.chat.sendToSession(sessionId, message)`
- `workbench.chat.getSessionResponse(sessionId)`

What EXISTS:
- `workbench.action.chat.open` - opens chat panel
- `workbench.action.chat.attachFile` - attaches file to current chat
- `code-insiders chat "prompt"` - creates NEW session

### 7. How does `code-insiders chat` work?

The CLI:
1. Launches VS Code (or connects to running instance)
2. Creates a NEW chat session
3. Sends the prompt as first message
4. Opens the chat panel to that session

**Source:** `src/vs/workbench/contrib/chat/browser/chatContribution.ts` in microsoft/vscode

### 8. How much code to modify for existing session targeting?

**Estimated scope:**

1. **CLI Handler** (`src/vs/code/electron-main/app.ts` or similar)
   - Add `--session <uuid>` flag
   - Route to existing session instead of creating new

2. **Chat Service** (`src/vs/workbench/contrib/chat/common/chatService.ts`)
   - Add method: `sendToSession(sessionId: string, message: string)`
   - Expose via command

3. **IPC Bridge** 
   - CLI → main process → renderer → chat service

**Complexity:** Medium-High
- Would need to touch 3-5 files in microsoft/vscode
- Requires understanding chat session lifecycle
- PR to vscode repo or fork

**Alternative:** Build into qopilot extension
- Register command: `qopilot.sendToSession`
- Use `vscode.commands.executeCommand` internally
- Still limited by what chat API exposes

## Proposed Path Forward

### Phase 1: Shared Reader (Done)
- `session_reader.js` - read any session from AppData
- Works NOW, no VS Code changes needed

### Phase 2: Improved HERMES v3
- Integrate reader for state detection
- Better window/session targeting
- Reduce false sends

### Phase 3: qopilot Enhancement
- Move session reading logic to qopilot
- Expose via Language Model Tools
- Agent can read other sessions via tools

### Phase 4: Upstream Contribution
- Propose `--session` flag to VS Code chat CLI
- Or: propose `workbench.chat.sendToSession` command
- Long-term: real inter-agent messaging API

## Current Bottleneck

The fundamental issue:
> **VS Code chat is designed for human-agent conversation, not agent-agent.**

The session JSON in AppData is the "database" but there's no "API server" that accepts writes from outside the current chat context.

UI automation is a HACK. The proper solution requires either:
1. VS Code adding multi-agent support
2. A separate message broker (file inbox, IPC, websocket)
3. Custom extension with internal routing

---

*ALTAIR/9 - Architecture analysis for HERMES inter-agent messaging*
