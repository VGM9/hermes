# HERMES Roadmap

## Vision
HERMES: **H**armonic **E**xtensible **R**eslient **M**essaging **E**ngine for **S**essions  
Production-grade inter-session messaging system for VSCode agents with source-verified reliability and zero hallucination.

---

## Phase 1: Core Refactoring (Sprint 1) ✅ COMPLETED
**Goal**: Clean, maintainable foundation with proper error handling and modular design  
**Start**: 2026-02-03  
**Target**: 2026-02-05  
**Actual**: 2026-02-03 (same day!)

### Tasks
1. **Refactor hermes_direct.py** ✅ COMPLETE
   - ✅ Extract pure functions: `window_ops`, `chat_ops`, `session_verify` modules
   - ✅ Add type hints (Python 3.9+)
   - ✅ Implement proper logging with structured format
   - ✅ Add error handling and retry logic
   - Branch: `feature/core-refactor-direct`
   - Status: APPROVED by subagent code review

2. **Fix blocking issues** ✅ COMPLETE
   - ✅ Replace hardcoded workspace hashes with declarative discovery
   - ✅ Replace Windows-only paths with cross-platform support
   - ✅ Fix vague `object` type hints with proper UIAElementInfo types
   - ✅ Create qopilot VSCode extension hook (vscode-extension-hook.ts)
   - ✅ Implement hermes_session_discovery.py (qopilot + fallback)
   - Branch: `feature/core-fix-blocking-issues`
   - Status: READY FOR REVIEW

3. **Documentation** ⏳ IN PROGRESS
   - README.md with architecture diagram
   - ARCHITECTURE_DECISIONS.md for technical choices
   - API.md for public interface
   - Status: Next task after code review approval

---

## Phase 2: VSCode API Integration (Sprint 2)
**Goal**: Replace fragile keybindings with robust VSCode command execution  
**Target**: 2026-02-10  

### Tasks
1. **Implement chat command executor**
   - `executeCommand('workbench.action.chat.open')` via VSCode API
   - Remove hardcoded `Ctrl+Shift+I` dependency
   - Handle Agent/Ask/Edit mode selection
   - Branch: `feature/api-command-executor`

2. **Environment detection**
   - Query `vscode.commands.getCommands()` for available chat commands
   - Read user keybindings.json (Windows, macOS, Linux)
   - Detect Copilot Chat extension version
   - Branch: `feature/api-env-detection`

3. **Fallback chain**
   - Try command API first
   - Fall back to user keybinding if command unavailable
   - Fall back to hardcoded keybinding if no user binding
   - Fail gracefully with diagnostic info
   - Branch: `feature/api-fallback-chain`

---

## Phase 3: Resilience Layer (Sprint 3)
**Goal**: Handle all VSCode configurations and daily Insiders updates  
**Target**: 2026-02-17  

### Tasks
1. **Settings stack resolver**
   - Read 5-level hierarchy: folder > workspace > profile > user > system
   - Evaluate `github.copilot.chat.agentEnabled` setting
   - Evaluate `when` clauses for context awareness
   - Branch: `feature/resilience-settings`

2. **Chat UI state machine**
   - Detect: chat open/closed, docked/floating, input focused
   - Detect: terminal focus vs editor focus
   - Detect: chat mode (Agent/Ask/Edit) currently active
   - Handle: pre-opening, sending during open, post-send cleanup
   - Branch: `feature/resilience-state-machine`

3. **Telemetry & diagnostics**
   - Structured logging of all operations
   - Success/failure metrics per session
   - Diagnostic report: "Why chat opening failed"
   - Branch: `feature/resilience-telemetry`

---

## Phase 4: Production Packaging (Sprint 4)
**Goal**: Distributable Python package with CLI tool  
**Target**: 2026-02-24  

### Tasks
1. **Python package setup**
   - `setup.py` with entry points
   - Package metadata, versioning, dependencies
   - PyPI readiness (metadata, long_description)
   - Branch: `feature/pkg-python-setup`

2. **CLI tool**
   - `hermes` command-line interface
   - `hermes send --session-id <id> --message "text"` command
   - `hermes inspect --session-id <id>` command  
   - `hermes status` for diagnostics
   - Branch: `feature/pkg-cli-tool`

3. **Integration & deployment**
   - Integration into vgm9 monorepo
   - GitHub Copilot Chat plugin integration
   - Automated testing in CI/CD
   - Branch: `feature/pkg-integration`

---

## Development Workflow

### Per-Feature Cycle
```
1. Create feature branch: git checkout -b feature/[name]
2. Implement code with tests
3. Self-review & lint
4. Request subagent code review
5. Incorporate feedback
6. Create PR/merge to main
```

### Subagent Review Checklist
- [ ] Code follows Python style guide (PEP 8)
- [ ] Type hints added (3.9+ compatible)
- [ ] Error handling: try/except/logging
- [ ] No hardcodes; use config/environment
- [ ] Pure functions extracted (testable)
- [ ] Unit tests with >80% coverage
- [ ] Documentation: docstrings, comments
- [ ] No external dependencies added without discussion

---

## Success Metrics
- [ ] Zero hallucinated facts (all from source code)
- [ ] Works on Windows, macOS, Linux
- [ ] Survives VSCode daily Insiders updates
- [ ] Works in all user configurations (folder/workspace/profile/user/system)
- [ ] 80%+ test coverage
- [ ] <500ms per message send
- [ ] Clear error messages for all failure modes
