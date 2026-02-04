# Code Review Request: HERMES Core Refactor

**Branch**: `feature/core-refactor-direct`  
**Commit**: e978f21  
**Date**: 2026-02-03  
**Task**: Phase 1 - Core Refactoring (Task 1/3)

---

## Summary of Changes

Refactored `hermes_direct.py` into 4 modular files with production-grade structure:

1. **hermes_window_ops.py** - Window management
   - `find_vscode_windows()` - List all VS Code windows
   - `find_agent_window(pattern)` - Match agent by title
   - `focus_window(window, delay)` - Focus with delay safety
   - Custom `WindowNotFoundError` exception

2. **hermes_chat_ops.py** - Chat panel operations
   - `open_chat(keybinding, delays)` - Open with custom key
   - `type_message(text, delays)` - Type with char delays
   - `send_message(delay)` - Send via Enter
   - `type_without_send()` - Defer mode for manual send
   - Custom `ChatOperationError` exception

3. **hermes_session_verify.py** - AppData verification
   - `get_appdata_sessions_dir(hashes)` - Find session directories
   - `find_session_file(pattern, hashes)` - Locate JSONL by agent
   - `get_session_request_count(pattern, hashes)` - Current count
   - `verify_message_delivery(pattern, before, hashes, timeout)` - Polling verification
   - Custom exceptions for session errors

4. **hermes_direct_v2.py** - Main orchestrator
   - `send_message_to_agent()` - Coordinate all operations with error handling
   - `main()` - CLI with improved argument parsing
   - Structured logging instead of print()
   - Better exit codes (0=success, 1=usage, 2=window, 3=operation, 4=chat, 5=verify)
   - Support for --no-enter, --no-verify, --timeout, --verbose flags

---

## Code Quality Improvements

### Type Hints
- Added comprehensive type hints to all functions (Python 3.9+ compatible)
- Return types explicitly documented
- Parameter types validated

### Error Handling
- Custom exception classes per module (WindowNotFoundError, ChatOperationError, SessionVerificationError)
- try/except blocks with logging at each layer
- Graceful degradation (e.g., continue without verification if session not found)
- Detailed error messages with context

### Logging
- Replaced print() with structured logging.getLogger()
- Log levels: DEBUG, INFO, WARNING, ERROR
- Timestamped output with [LEVEL] NAME format
- --verbose flag enables DEBUG level

### Modularity
- Pure functions with no hidden state
- Each module has single responsibility
- Easy to test (minimal dependencies on window state)
- Easy to extend (add new operations in respective module)

### Documentation
- Docstrings for all functions (Args, Returns, Raises, Note)
- Comments for non-obvious logic
- CLI help text with examples

---

## Testing Checklist

Before approval, verify:

- [ ] **Python 3.9+ compatibility** - All type hints valid
- [ ] **No new dependencies** - Still requires: pywinauto, pathlib
- [ ] **Imports work** - Can import all 4 modules without errors
- [ ] **Error handling** - Each exception caught and logged
- [ ] **Logging** - Configure_logging() sets up correctly
- [ ] **Pure functions** - No reliance on global state
- [ ] **Backwards compatibility** - hermes_direct_v2.py CLI same as original
- [ ] **Edge cases**:
  - Multiple VS Code windows (should pick matching one)
  - No matching window (proper error message)
  - Session not found (graceful skip verify)
  - AppData missing (proper handling)
  - JSONL format variation (robust parsing)

---

## Architecture Decisions

1. **Pure functions over classes** - Easier to test, compose, and understand
2. **Custom exceptions** - Type-safe error handling vs generic Exception
3. **Structured logging** - Better debugging and monitoring
4. **Modular files instead of package** - Avoids pyproject.toml complexity for v2
5. **Backward keybinding default** - `^+i` (Ctrl+Shift+I) matches known working behavior

---

## Next Steps (Not in this PR)

- Unit tests with pytest (target: >80% coverage)
- Integration tests against live VS Code instance
- Performance profiling (target: <500ms per message)
- CLI added to PATH via setup.py (separate feature branch)
- VSCode command API integration (Phase 2)

---

## Reviewer Notes

This is the first of 3 tasks in Phase 1 (Core Refactoring). Subsequent tasks will:

1. Create `pyproject.toml`, `requirements.txt`, package structure (Task 2)
2. Write README.md and architecture documentation (Task 3)

All follow this same pattern: feature branch → refactored code → subagent review → merge.

**Questions for reviewer:**
1. Are the module boundaries (window / chat / session) correct?
2. Should logging be more verbose or less verbose by default?
3. Any edge cases I'm missing in error handling?
4. Is the type hint style (using `list[T]` vs `List[T]`) appropriate?
