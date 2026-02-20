# Contributing to HERMES

**Development process and architectural guidelines.**

Thank you for contributing to HERMES! This document explains our development philosophy, workflow, and technical requirements.

## Table of Contents

- [Philosophy](#philosophy)
- [Development Workflow](#development-workflow)
- [Architecture](#architecture)
- [Ground Truth System](#ground-truth-system)
- [Pure Functional Programming](#pure-functional-programming)
- [Testing Strategy](#testing-strategy)
- [Code Review Process](#code-review-process)
- [Cross-Version Testing](#cross-version-testing)

---

## Philosophy

HERMES is built on three core principles:

### 1. **100% Ground Truth Driven**

**Rule:** Never hardcode VSCode UI identifiers. All must come from `vscode_ground_truth.py` with source citations.

**Anti-pattern ❌:**
```python
# DON'T hardcode button class names
button_class = 'monaco-button small monaco-text-button'
```

**Correct pattern ✅:**
```python
# DO import from ground truth
from vscode_ground_truth import MONACO_BUTTON_PRIMARY_CLASSES

button_class = MONACO_BUTTON_PRIMARY_CLASSES
```

**Why:** When VSCode updates and changes UI structure, we need to update exactly ONE file (`vscode_ground_truth.py`) instead of hunting through the entire codebase.

### 2. **Pure Functional Programming**

**Rule:** All functions in `core/` must be pure - deterministic with no side effects.

**Anti-pattern ❌:**
```python
# DON'T use global state or side effects
global_agents = []

def find_agents():
    global global_agents
    global_agents = detect_from_windows()  # Side effect!
    return global_agents
```

**Correct pattern ✅:**
```python
# DO return new data without modifying globals
def find_agents() -> List[ApprovalRequest]:
    windows = find_windows()  # Pure
    agents = detect_agents_in_windows(windows)  # Pure
    return agents  # New data, no mutation
```

**Why:** Pure functions are:
- Easily testable (same input → same output)
- Composable (can chain together safely)
- Parallelizable (no shared state)
- Debuggable (no hidden dependencies)

### 3. **Modular Architecture**

**Rule:** Keep modules small, focused, and independently testable. No monoliths.

**Anti-pattern ❌:**
```python
# DON'T create God objects with 1000+ lines
class AgentManager:
    def find_windows(self): ...
    def detect_agents(self): ...
    def parse_text(self): ...
    def evaluate_policy(self): ...
    def approve_agent(self): ...
    def skip_agent(self): ...
    # ... 30 more methods
```

**Correct pattern ✅:**
```
core/
├── ui_automation/
│   ├── window_detection.py      # ONLY window finding
│   └── element_detection.py     # ONLY element finding
├── parsers/
│   └── request_text_parser.py   # ONLY text parsing
└── policy/
    └── policy_evaluator.py       # ONLY policy evaluation
```

**Why:** Small modules are:
- Easier to understand
- Easier to test in isolation
- Easier to refactor   
- Can be developed in parallel

---

## Development Workflow

### Feature Branch Model

**Always work in feature branches. Never commit directly to `main`.**

```bash
# 1. Create feature branch
git checkout -b feature/your-feature-name

# 2. Make changes  
# ... edit files ...

# 3. Test locally
python3 -m pytest tests/

# 4. Commit with conventional commit message
git commit -m "feat: add cross-version button detection"

# 5. Push and create PR
git push origin feature/your-feature-name
gh pr create --title "Add cross-version button detection"

# 6. Request code review
gh pr review --request-reviewer theca

# 7. After approval, merge
gh pr merge --squash
```

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring (no behavior change)
- `test`: Adding/updating tests
- `docs`: Documentation only
- `perf`: Performance improvement
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(detection): add support for VSCode Stable 1.88
fix(parser): handle file URIs with spaces
refactor(core): extract button detection to separate module
test(cross-version): add tests for Insider build 2025-12-01
docs(readme): add troubleshooting section for button detection
```

---

## Architecture

### Directory Structure

```
hermes/
├── vscode_ground_truth.py          # 🎯 SINGLE SOURCE OF TRUTH
├── core/                            # Pure function modules
│   ├── __init__.py
│   ├── data_models/                # Immutable data structures
│   │   ├── __init__.py
│   │   └── approval_request.py
│   ├── parsers/                    # Text parsing (pure)
│   │   ├── __init__.py
│   │   └── request_text_parser.py
│   ├── ui_automation/              # UI interaction (pure)
│   │   ├── __init__.py
│   │   ├── window_detection.py
│   │   ├── element_detection.py
│   │   └── element_interaction.py
│   └── policy/                     # Policy evaluation (pure)
│       ├── __init__.py
│       └── policy_evaluator.py
├── detection.py                     # 📡 Public API (declarative wrapper)
├── approval.py                      # ✅ Public API (declarative wrapper)
├── policy.py                        # 📋 Public API (declarative wrapper)
├── tests/                           # Test suite
│   ├── test_detection.py
│   ├── test_approval.py
│   ├── test_parsers.py
│   ├── test_cross_version.py
│   └── test_properties.py
├── scripts/                         # Utility scripts
│   ├── update_ground_truth.py
│   └── test_all_versions.py
├── docs/                            # Additional documentation
├── AGENTS.md                        # Agent guidance (you are here!)
├── README.md                        # Usage documentation
├── CONTRIBUTING.md                  # This file
└── requirements.txt                 # Python dependencies
```

### Module Responsibilities

| Module | Responsibility | Pure? | Dependencies |
|--------|---------------|-------|--------------|
| `vscode_ground_truth.py` | Define all VSCode identifiers | ✅ | None |
| `core/data_models/` | Data structures only | ✅ | None |
| `core/parsers/` | Extract data from text | ✅ | `data_models`, `ground_truth` |
| `core/ui_automation/` | Find/interact with UI | ✅ | `data_models`, `ground_truth`, pywinauto |
| `core/policy/` | Evaluate approval rules | ✅ | `data_models` |
| `detection.py` |  Declarative API wrapper | ❌ | `core/*` |
| `approval.py` | Declarative API wrapper | ❌ | `core/*` |

**Key invariant:** Only public API modules (`detection.py`, `approval.py`, `policy.py`) can have side effects. Everything in `core/` MUST be pure.

---

## Ground Truth System

### What Goes in `vscode_ground_truth.py`

**Include:**
- ✅ VSCode action IDs (from `src/vs/workbench/contrib/chat/browser/actions/*.ts`)
- ✅ Context key names (from `src/vs/workbench/contrib/chat/common/actions/chatContextKeys.ts`)
- ✅ CSS class names (from `src/vs/workbench/contrib/chat/browser/widget/**/media/*.css`)
- ✅ Button class patterns (from `src/base/browser/ui/button/*.ts`)
- ✅ Control type identifiers (from Windows UIA API docs)
- ✅ Keybinding definitions (from action constructors)

**Exclude:**
- ❌ Business logic (belongs in `core/`)
- ❌ Text parsing logic (belongs in `core/parsers/`)
- ❌ UI automation logic (belongs in `core/ui_automation/`)

### Citation Format

Every constant must have a docstring with source citation:

```python
ACCEPT_TOOL_CONFIRMATION_ACTION_ID = 'workbench.action.chat.acceptTool'
"""
Action ID for accepting tool confirmations.

Source: src/vs/workbench/contrib/chat/browser/actions/chatToolActions.ts#45
Export: export const AcceptToolConfirmationActionId = 'workbench.action.chat.acceptTool';
"""
```

**Required fields:**
1. **Description**: What this identifier is used for
2. **Source**: File path in vscode-src
3. **Line number** (optional but recommended)
4. **Export statement** (if from TypeScript)
5. **Version notes** (if identifier changed across versions)

###  Updating Ground Truth

**When to update:**
1. VSCode releases new Insider/Stable build
2. Tests fail with "element not found" errors
3. Adding support for new VSCode feature
4. Community reports compatibility issue

**How to update:**

1. **Clone VSCode source:**
   ```bash
   git clone https://github.com/microsoft/vscode.git
   cd vscode
   git checkout <specific-version-tag>
   ```

2. **Search for changed identifier:**
   ```bash
   # Example: find new action ID
   rg "AcceptToolConfirmationActionId" src/vs/workbench/contrib/chat/
   ```

3. **Update `vscode_ground_truth.py`:**
   ```python
   # OLD (2026-01-01)
   # Source: src/vs/workbench/contrib/chat/browser/actions/chatToolActions.ts#45

   # NEW (2026-02-01) - line number changed!
   # Source: src/vs/workbench/contrib/chat/browser/actions/chatToolActions.ts#48
   ```

4. **Add version note:**
   ```python
   VERSION_COMPATIBILITY = {
       ...
       'changes': [
           {
               'date': '2026-02-01',
               'vscode_version': '1.89.0',
               'change': 'AcceptToolConfirmationActionId moved to line 48 (was 45)',
               'breaking': False
           }
       ]
   }
   ```

5. **Test across versions:**
   ```bash
   python3 scripts/test_all_versions.py
   ```

---

## Pure Functional Programming

### Rules for `core/*` Modules

**1. No global state:**
```python
# ❌ DON'T
_cache = {}

def get_windows():
    if 'windows' in _cache:
        return _cache['windows']
    windows = find_windows_impl()   
    _cache['windows'] = windows
    return windows

# ✅ DO  
def get_windows() -> List[WindowInfo]:
    return find_windows_impl()  # Always returns fresh data
```

**2. No mutation:**
```python
# ❌ DON'T
def add_file(agent: ApprovalRequest, file_path: str):
    agent.files_to_access.append(file_path)  # Mutation!
    return agent

# ✅ DO
def add_file(agent: ApprovalRequest, file_path: str) -> ApprovalRequest:
    new_files = agent.files_to_access + [file_path]
    return dataclasses.replace(agent, files_to_access=new_files)  # New object
```

**3. No I/O (except where necessary):**
```python
# ❌ DON'T (in core/)
def get_policy_rules():
    with open('policy.json') as f:  # I/O side effect!
        return json.load(f)

# ✅ DO (in core/)
def parse_policy_rules(json_string: str) -> dict:
    return json.loads(json_string)  # Pure - input→output

# ✅ DO (in public API)
def load_policy(file_path: str) -> dict:
    with open(file_path) as f:
        json_string = f.read()
    return parse_policy_rules(json_string)  # Wrapper handles I/O
```

**4. Use frozen dataclasses:**
```python
from dataclasses import dataclass

# ✅ Always use frozen=True for immutability
@dataclass(frozen=True)
class ApprovalRequest:
    window_handle: int
    request_type: str
    # ... more fields
```

### Testing Pure Functions

Pure functions are trivial to test:

```python
def test_extract_file_uris():
    text = "Read [](file:///c:/test.txt)"
    result = extract_file_uris_from_text(text)
    assert result == ['c:/test.txt']
    
    # Run again - same input, same output (deterministic)
    result2 = extract_file_uris_from_text(text)
    assert result2 == result
```

No need for:
- Mocks
- Setup/teardown
- Database fixtures
- Network stubs

---

## Testing Strategy

### Test Pyramid

```
        /\
       /  \     E2E Tests (few)
      /----\
     /      \   Integration Tests (some)
    /--------\
   /          \ Unit Tests (many)
  /-----------  
```

**Unit Tests** (70%):
- Test individual pure functions
- Fast, deterministic
- No external dependencies

**Integration Tests** (25%):
- Test composition of modules
- May use real VSCode UI (in test mode)
- Slower but more realistic

**E2E Tests** (5%):
- Full workflow: detect → evaluate → approve
- Requires real VSCode instance
- Run in CI with VSCode Insider/Stable

### Property-Based Testing

We use [Hypothesis](https://hypothesis.readthedocs.io/) for comprehensive testing:

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_extract_file_uris_never_crashes(text):
    """Property: function never raises exception for any string input."""
    result = extract_file_uris_from_text(text)
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)

@given(st.lists(st.text(min_size=1)))
def test_parse_always_returns_same_length(file_list):
    """Property: parsing never loses or creates files."""
    text = ' '.join(f'[](file:///{f})' for f in file_list)
    result = extract_file_uris_from_text(text)
    assert len(result) <= len(file_list)  # May deduplicate
```

### Cross-Version Testing

**Test matrix:**

| VSCode Version | Python Version | OS | Required? |
|----------------|---------------|-----|-----------|
| Insiders (latest) | 3.11 | Windows | ✅ |
| Stable (latest) | 3.11 | Windows | ✅ |
| Insiders (N-1) | 3.11 | Windows | ⚠️ |
| Stable (N-1) | 3.10 | Windows | ⚠️ |

**Run tests:**
```bash
# Test current Insider
python3 -m pytest tests/

# Test specific VSCode version
VSCODE_VARIANT=stable python3 -m pytest tests/test_cross_version.py

# Test all supported versions (CI only)
python3 scripts/test_all_versions.py
```

**Adding version-specific test:**
```python
@pytest.mark.parametrize('vscode_version', [
    ('insiders', '1.89.0'),
    ('stable', '1.88.0'),
])
def test_button_detection_across_versions(vscode_version):
    variant, version = vscode_version
    # ... test logic
```

---

## Code Review Process

### Acceptance Criteria

**Every PR must pass:**

1. **✅ Code Quality ≥ 9.0/10**
   - Run: `python3 scripts/code_review.py`
   - Checks: pure functions, no magic strings, documentation

2. **✅ Tests Pass**
   - Run: `python3 -m pytest tests/`
   - Must pass on both Insider and Stable

3. **✅ Ground Truth Updated**
   - If adding VSCode features, update `vscode_ground_truth.py`
   - Include source citations

4. **✅ Documentation Updated**
   - Update README.md if public API changed
   - Update AGENTS.md if architecture changed
   - Add docstrings to new functions

5. **✅ No Magic Strings/Numbers**
   - Reviewer will flag hardcoded values
   - Must use constants from `vscode_ground_truth.py` or module-level constants

### Review Checklist

**Functional Purity:**
- [ ] All functions in `core/` are pure
- [ ] No global state mutations
- [ ] No side effects in business logic
- [ ] Frozen dataclasses used for data models

**Ground Truth:**
- [ ] No hardcoded VSCode identifiers in logic
- [ ] All constants imported from `vscode_ground_truth.py`
- [ ] New constants have source citations
- [ ] Version notes added if compatibility changed

**Testing:**
- [ ] Unit tests for all new pure functions
- [ ] Integration tests for new workflows
- [ ] Cross-version tests if touching UI detection
- [ ] Property-based tests for text parsing

**Documentation:**
- [ ] Docstrings on all public functions
- [ ] Type hints on all parameters
- [ ] README updated if API changed
- [ ] CHANGELOG entry added

**Code Quality:**
- [ ] No functions > 50 lines  
- [ ] No modules > 500 lines
- [ ] Clear separation of concerns
- [ ] Meaningful variable/function names

### Requesting Review  

1. **Self-review first:**
   ```bash
   python3 scripts/code_review.py --file mychanges.py
   ```

2. **Run full test suite:**
   ```bash
   python3 -m pytest tests/ --cov=hermes
   ```

3. **Create PR with template:**
   ```markdown
   ## Changes
   - Added cross-version button detection
   - Updated ground truth with Stable 1.88 identifiers

   ## Testing
   - [x] Unit tests pass
   - [x] Integration tests pass
   - [x] Cross-version tests pass (Insider + Stable)

   ## Code Quality
   - Quality score: 9.5/10
   - Pure functions: 100%
   - Ground truth citations: 100%

   ## Documentation
   - [x] Docstrings added
   - [x] README updated
   - [x] CHANGELOG updated
   ```

4. **Tag reviewer:**
   ```bash
   gh pr create --reviewer theca --assignee me
   ```

### Review Response  

**If changes requested:**
1. Address each comment
2. Push new commits (don't force-push)
3. Reply to each thread explaining changes
4. Re-request review: `gh pr review --request-changes`

**If approved:**
1. Squash merge: `gh pr merge --squash`
2. Delete feature branch
3. Celebrate! 🎉

---

## Cross-Version Testing

### Why Cross-Version Testing Matters

VSCode changes UI structure frequently:
- Insider builds: Weekly
- Stable releases: Monthly
- Major releases: Quarterly

**Without cross-version testing:**
- Hermes breaks on every VSCode update
- Users forced to pin specific VSCode version
- Ground truth becomes outdated quickly

**With cross-version testing:**
- We detect breaking changes immediately
- Can maintain backward compatibility
- Ground truth stays current

### Test Strategy

**1. Identify Stable vs. Changing Identifiers**

From `vscode_ground_truth.py#VERSION_COMPATIBILITY`:

```python
'stable_identifiers': [
    'VSCODE_WINDOW_CLASS_NAME',  # Electron framework - never changes
    'CONTROL_TYPE_BUTTON',       # Windows UIA - OS-level
    'MONACO_BUTTON_*_CLASSES',   # Monaco core - rarely changes
],
'potentially_changing': [
    'CONTEXT_KEY_*',             # May rename in major versions
    'CHAT_CONFIRMATION_*',       # UI refactors may change classes
]
```

**Test stable identifiers** once per major version.  
**Test changing identifiers** on every minor release.

**2. Set Up Test Matrix**

```python
# tests/conftest.py
import pytest

@pytest.fixture(params=[
    {'variant': 'insiders', 'version': '1.89.0'},
    {'variant': 'stable', 'version': '1.88.0'},
])
def vscode_instance(request):
    """Provides VSCode instance for testing."""
    return launch_vscode(
        variant=request.param['variant'],
        version=request.param['version']
    )
```

**3. Write Version-Agnostic Tests**

```python
def test_button_detection_is_version_agnostic(vscode_instance):
    """Button detection should work regardless of VSCode version."""
    # Given: A paused agent in any VSCode version
    agent = create_test_agent(vscode_instance)
   
    # When: We detect buttons
    buttons = detect_buttons(agent.window_handle)
    
    # Then: We find both Allow and Skip buttons
    assert buttons['allow'] is not None
    assert buttons['skip'] is not None
```

**4. Handle Version-Specific Differences**

```python
from vscode_ground_truth import VERSION_COMPATIBILITY

def get_button_class_for_version(vscode_version: str) -> str:
    """Get button class name for specific VSCode version."""
    if vscode_version < '1.88':
        # Old class format
        return 'monaco-button'
    else:
        # New class format (added 'small' modifier)
        return 'monaco-button small monaco-text-button'
```

**5. Run Tests in CI**

```yaml
# .github/workflows/test.yml
name: Cross-Version Tests

on: [push, pull_request]

jobs:
  test:
    strategy:
      matrix:
        vscode-variant: [insiders, stable]
        python-version: [3.10, 3.11, 3.12]
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Install VSCode ${{ matrix.vscode-variant }}
        run: choco install vscode-${{ matrix.vscode-variant }}
      
      - name: Run tests
        run: |
          pytest tests/test_cross_version.py \
            --vscode-variant=${{ matrix.vscode-variant }}
```

### Debugging Version Issues

**When tests fail on specific VSCode version:**

1. **Capture UI snapshot:**
   ```bash
   python3 scripts/capture_ui_tree.py --variant insiders --output ui_tree.json
   ```

2. **Compare with working version:**
   ```bash
   diff ui_tree_stable.json ui_tree_insiders.json
   ```

3. **Identify changed identifiers:**
   - Look for missing/renamed elements
   - Check if class names changed
   - Verify control types unchanged

4. **Update ground truth:**
   - Add version-specific constants if needed
   - Update `VERSION_COMPATIBILITY` notes
   - Add fallback logic for compatibility

5. **Add regression test:**
   ```python
   @pytest.mark.skipif(vscode_version < '1.89', reason="Feature added in 1.89")
   def test_new_vscode_feature():
       # Test the new VSCode 1.89 feature
       pass
   ```

---

## Adding a New Feature

**Example: Add support for detecting elicitation requests (not just tool confirmations)**

### 1. Update Ground Truth

```python
# vscode_ground_truth.py

CONTEXT_KEY_HAS_ELICITATION_REQUEST = 'chatHasElicitationRequest'
"""
Context key that is true when a chat elicitation request is pending.

Source: src/vs/workbench/contrib/chat/common/actions/chatContextKeys.ts#114
Export: hasElicitationRequest: new RawContextKey<boolean>('chatHasElicitationRequest', false, ...)
"""
```

### 2. Add Data Model

```python
# core/data_models/elicitation_request.py

@dataclass(frozen=True)
class ElicitationRequest:
    """Immutable representation of an elicitation request."""
    window_handle: int
    elicitation_type: str
    options: List[str]
```

### 3. Add Parser

```python
# core/parsers/elicitation_parser.py

def parse_elicitation_text(text: str) -> dict:
    """
    Extract elicitation options from dialog text.
   
    Pure function - no side effects.
    """
    # ... parsing logic using regex constants ...
    return {'type': elicit_type, 'options': options}
```

### 4. Add UI Detection

```python
# core/ui_automation/element_detection.py

def find_elicitation_dialog(window: WindowInfo) -> Optional[UIElement]:
    """
    Find elicitation dialog in window.
    
    Pure function - returns element info, doesn't interact.
    """
    from vscode_ground_truth import CONTEXT_KEY_HAS_ELICITATION_REQUEST
    # ... detection logic using ground truth ...
```

### 5. Add Public API

```python
# detection.py

def find_pending_elicitations() -> List[ElicitationRequest]:
    """
    Find all pending elicitation requests in VSCode windows.
    
    Declarative wrapper around core modules.
    """
    windows = window_detection.find_vscode_windows()
    return [
        parse_elicitation(win)
        for win in windows
        if has_elicitation(win)
    ]
```

### 6. Add Tests

```python
# tests/test_elicitation_detection.py

def test_find_elicitations():
    """Integration test for elicitation detection."""
    # Given: A VSCode window with pending elicitation
    setup_test_elicitation()
    
    # When: We detect elicitations
    elicitations = detection.find_pending_elicitations()
    
    # Then: We find the elicitation with correct options
    assert len(elicitations) == 1
    assert elicitations[0].elicitation_type == 'choice'
    assert len(elicitations[0].options) > 0

@given(st.text())
def test_parse_elicitation_never_crashes(text):
    """Property: parser never crashes on any input."""
    result = parse_elicitation_text(text)
    assert isinstance(result, dict)
```

### 7. Update Documentation

```markdown
# README.md

## Detecting Elicitations

```python
from hermes import detection

elicitations = detection.find_pending_elicitations()
for elicit in elicitations:
    print(f"Type: {elicit.elicitation_type}")
    print(f"Options: {elicit.options}")
```
```

### 8. Submit PR

```bash
git checkout -b feature/elicitation-detection
git add .
git commit -m "feat(detection): add elicitation request detection"
git push origin feature/elicitation-detection
gh pr create --title "Add elicitation request detection"
```

---

## Questions?

- **Architecture questions**: See [AGENTS.md](AGENTS.md)
- **Usage questions**: See [README.md](README.md)  
- **Stuck on something**: Open a [Discussion](https://github.com/VGM9/hermes/discussions)

---

**Maintainer**: Theca.0.0.Q  
**Last Updated**: 2026-02-04  
**Code Quality Standard**: 9.5/10
