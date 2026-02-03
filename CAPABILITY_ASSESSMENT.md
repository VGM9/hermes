# HERMES Capability Assessment

**Date:** 2026-01-23  
**Assessor:** ALTAIR/6 (Q-33)  

## Current Status

HERMES v2 exists at: `_/AS/0.0.Q/_/software/hermes/hermes_v2.py`

## Core Capabilities

| Capability | Status | Notes |
|------------|--------|-------|
| Find open chat inputs | ✅ Works | Scans all VS Code windows |
| Send to chat by pattern | ✅ Works | Matches window title, input name, or content |
| List all open chats | ✅ Works | Returns accessible names |
| Message closed sessions | ❌ Cannot | Chat input must be visible |
| Open/activate sessions | ❌ Cannot | No programmatic session activation |

## Key Limitation

**HERMES cannot message agents whose chats are not already open.**

The Chat Input control only exists when the chat panel/tab is visible. If a session exists in AppData but has no open UI element, HERMES cannot:
1. Open the session
2. Send messages to it
3. Trigger the agent to wake

This is a fundamental limitation of UI automation - you can only interact with visible controls.

## MCP Server Feasibility

### Technical Requirements

1. **Python MCP SDK:** The official SDK supports Python: `pip install mcp`
2. **pywinauto:** Works from background processes
3. **Stdio Transport:** Standard MCP pattern

### Architecture

```
┌─────────────────────┐      ┌────────────────────┐
│   Agent (Copilot)   │      │   HERMES MCP       │
│                     │      │                    │
│   hermes_list()     │─────▶│   scan windows     │
│   hermes_send()     │◀─────│   type & send      │
└─────────────────────┘      └────────────────────┘
```

### Proposed Tools

```json
{
  "tools": [
    {
      "name": "hermes_list_chats",
      "description": "List all open VS Code chat inputs with their accessible names"
    },
    {
      "name": "hermes_send_message", 
      "description": "Send a message to a chat matching the pattern",
      "parameters": {
        "pattern": "String to match against window title or chat name",
        "message": "Message text to send"
      }
    },
    {
      "name": "hermes_inspect",
      "description": "Debug tool to inspect UI element tree"
    }
  ]
}
```

### Implementation Path

1. Create `monorepos/mcp-servers/packages/hermes/`
2. Implement Python MCP server using `mcp` SDK
3. Port existing pywinauto logic
4. Add to `.vscode/mcp.json` configuration
5. Test inter-agent messaging

### Caveats

- **Windows-only:** pywinauto doesn't work on Mac/Linux
- **Same limitation:** Still requires target chat to be open
- **Timing sensitivity:** UI automation can be flaky
- **Security:** Arbitrary message injection is powerful

## Alternative: Session Activation

To message closed sessions, we would need:

1. **VS Code Extension API:** An extension that can programmatically open chat sessions
2. **Command Protocol:** `vscode.commands.executeCommand('workbench.panel.chat.view.copilot.focus')`?
3. **Session Selection:** No known API for selecting which session to show

This would require either:
- A custom VS Code extension (Qopilot)
- Discovery of hidden VS Code commands
- Modification of Copilot's extension behavior

## Recommendation

1. **Proceed with MCP server conversion** - Makes HERMES accessible as a tool
2. **Document the closed-session limitation** - Future work
3. **Explore VS Code Extension approach** - Via Qopilot project

## Related

- [00_CC0/04_extensions/qopilot/](../../../00_CC0/04_extensions/qopilot/) - Potential extension for session control
- [monorepos/mcp-servers/](../../../monorepos/mcp-servers/) - MCP server patterns
- [___/protocols/](../../../___/protocols/) - Protocol documentation
