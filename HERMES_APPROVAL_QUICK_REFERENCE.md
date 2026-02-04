# HERMES Approval Workflow - Quick Reference Guide

## One-Minute Overview

The approval workflow has **4 stages**:

| Stage | Module | Role | Deterministic? |
|-------|--------|------|:-------------:|
| 1️⃣ **Discovery** | `hermes_agent_discovery.py` | Find paused agents in VSCode | ✅ Yes |
| 2️⃣ **Decision** | `hermes_approval_decision.py` | Decide approve/skip/review | ⚖️ Inference |
| 3️⃣ **Audit** | `hermes_approval_log.py` | Record decision to log | ✅ Yes |
| 4️⃣ **Action** | `hermes_wake.py` | Click buttons in VSCode | ✅ Yes |

**Orchestrator**: `hermes_approval_orchestrator.py` (coordinates all 4 stages)

---

## Running the System

### See what agents are paused
```bash
python hermes_agent_discovery.py --json
```

### Make a decision about one agent
```bash
python hermes_approval_decision.py \
  --session SESSION_ID \
  --action ACTION_NAME \
  --json
```

### Full workflow (discover → decide → audit → execute)
```bash
# Dry-run first (see what would happen)
python hermes_approval_orchestrator.py run --dry-run

# Live mode (actually click buttons)
python hermes_approval_orchestrator.py run
```

### View the audit trail
```bash
# Recent decisions
python hermes_approval_log.py --tail 5

# Statistics
python hermes_approval_log.py --summary

# All decisions for a session
python hermes_approval_log.py --session SESSION_ID

# Verify integrity
python hermes_approval_log.py --verify
```

---

## How to Customize

### Add a new approval rule

Edit `hermes_approval_policy.json`:

```json
{
  "id": "APPROVE_MY_CUSTOM_OPERATION",
  "description": "My safe operation",
  "match": {
    "action_name_contains": ["my_tool", "my_command"],
    "action_name_not_contains": ["dangerous"]
  },
  "decision": "APPROVE",
  "reason": "My operation is safe because..."
}
```

Then test:
```bash
python hermes_approval_decision.py \
  --session test-session \
  --action "my_tool_read"
# Should return: APPROVE
```

### Change default behavior

In `hermes_approval_policy.json`, modify the fallback:

```json
{
  "fallback": {
    "default_decision": "REQUEST_REVIEW",  // Or "SKIP" for safe-by-default
    "reason": "Unknown action - require human review"
  }
}
```

---

## Integration Examples

### From another Python script
```python
from hermes_approval_orchestrator import ApprovalOrchestrator

orchestrator = ApprovalOrchestrator()
result = orchestrator.run_workflow(agent_nonce="HERMES_NONCE_xyz123")

# Results
print(f"Decisions made: {len(result['actions_taken'])}")
for action in result['actions_taken']:
    print(f"  {action['decision']['decision']}")
```

### From bash
```bash
#!/bin/bash

# Discover paused agents
AGENTS=$(python hermes_agent_discovery.py --json)

# Process them
python hermes_approval_orchestrator.py run --nonce "$MY_NONCE"

# Check results
python hermes_approval_log.py --tail 1 --json
```

### With traceability (nonce)

From your calling code:
```python
MY_NONCE = "HERMES_NONCE_abc123def456"

# Generate the nonce in your thinking
# Include it in your command
run_in_terminal(f"echo {MY_NONCE} && my_command")

# Later, run workflow with nonce for traceability
orchestrator.run_workflow(agent_nonce=MY_NONCE)

# All decisions logged with this nonce for audit trail
```

---

## Understanding Decisions

### Decision Types

| Type | Meaning | Action |
|------|---------|--------|
| `APPROVE` | Safe to auto-approve | Clicks Allow button |
| `REQUEST_REVIEW` | Needs human decision | Does nothing (waits) |
| `SKIP` | Should be rejected | Clicks Skip button |

### Example Decision Output
```json
{
  "agent_session_id": "3c8d9862...",
  "agent_action": "grep_search",
  "decision": "APPROVE",
  "decision_reason": "Read-only operations pose no risk",
  "policy_rule_matched": "ALWAYS_APPROVE_READ_OPERATIONS",
  "confidence": 0.95,
  "alternative_decision": "REQUEST_REVIEW (more cautious)"
}
```

---

## Audit Trail

### What gets logged

Every decision record contains:
- **timestamp**: ISO 8601 UTC time
- **agent_session_id**: Which session made the request
- **agent_action**: What the agent wanted to do
- **decision**: APPROVE | REQUEST_REVIEW | SKIP
- **decision_reason**: Why this decision
- **policy_rule_matched**: Which rule applied
- **confidence**: 0.0-1.0 (how sure was the decision?)
- **entry_hash**: SHA256 hash (tamper detection)

### Example audit entry
```json
{
  "timestamp": "2026-02-04T08:55:30Z",
  "log_index": 42,
  "nonce": "HERMES_NONCE_abc123",
  "decision": {
    "agent_session_id": "3c8d9862-404a...",
    "agent_action": "grep_search",
    "policy_rule_matched": "ALWAYS_APPROVE_READ_OPERATIONS",
    "decision": "APPROVE",
    "decision_reason": "Read-only operations pose no risk",
    "confidence": 0.95
  },
  "entry_hash": "ab3f7e2c..."
}
```

---

## Troubleshooting

### No paused agents found
```bash
python hermes_agent_discovery.py --verbose

# Check:
# 1. Are there actually VSCode windows with approval buttons?
# 2. Is VSCode UI automation enabled?
# 3. Try clicking a button manually to verify it works
```

### Decision is REQUEST_REVIEW but you expected APPROVE
```bash
# Check which rule matched
python hermes_approval_decision.py \
  --action "my_action" \
  --json | grep policy_rule_matched

# Review the matching rule in hermes_approval_policy.json
# Add a new rule for your action
```

### Action didn't execute (buttons still showing)
```bash
# Check for errors
python hermes_approval_orchestrator.py run --verbose

# Dry-run to see what would happen
python hermes_approval_orchestrator.py run --dry-run

# Verify window is accessible
python hermes_agent_discovery.py --verbose
```

### Verify audit log integrity
```bash
python hermes_approval_log.py --verify

# Output: "Audit log integrity verified (N entries)"
# If fails: log may have been corrupted
```

---

## Architecture at a Glance

```
┌─────────────────────────────────────────┐
│         PAUSED AGENT IN VSCODE          │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────▼─────────┐
        │  DISCOVERY        │  Reads VSCode state
        │  (Deterministic)  │  → PausedAgent
        └─────────┬─────────┘
                  │
        ┌─────────▼──────────────────┐
        │  DECISION (Inference)      │  Evaluates policy
        │  + POLICY CONFIG           │  → ApprovalDecision
        └─────────┬──────────────────┘
                  │
        ┌─────────▼─────────┐
        │  AUDIT            │  Records decision
        │  (Deterministic)  │  → Immutable log
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │  ACTION           │  Executes decision
        │  (Deterministic)  │  → Click button
        └─────────┬─────────┘
                  │
        ┌─────────▼──────────────┐
        │  AGENT CONTINUES       │
        │  OR WAITS FOR HUMAN    │
        └────────────────────────┘
```

---

## Key Files

### Run these
```bash
# Discovery
python hermes_agent_discovery.py

# Decision  
python hermes_approval_decision.py

# Full workflow
python hermes_approval_orchestrator.py

# Audit
python hermes_approval_log.py
```

### Edit this
```bash
# Customize approval rules
vim hermes_approval_policy.json
```

### Read these (documentation)
```bash
# Architecture deep-dive
cat APPROVAL_WORKFLOW_ARCHITECTURE.md

# Quest summary
cat QUEST_APPROVAL_WORKFLOW_COMPLETE.md

# This guide
cat HERMES_APPROVAL_QUICK_REFERENCE.md
```

---

## Typical Workflow

1. **Agent runs and hits an approval dialog**
   ```
   VSCode agent: "Allow this command?"
   ```

2. **You want to auto-approve it**
   ```bash
   python hermes_approval_orchestrator.py run
   ```

3. **System discovers what's paused**
   ```
   Found 1 paused agent: "grep_search"
   ```

4. **System decides based on policy**
   ```
   Policy rule ALWAYS_APPROVE_READ_OPERATIONS matched
   Decision: APPROVE (confidence 95%)
   ```

5. **System logs the decision**
   ```
   Audit entry ab3f7e2c... logged
   ```

6. **System clicks the button**
   ```
   Clicked Allow button ✓
   ```

7. **Agent continues**
   ```
   VSCode agent: Command executing...
   ```

---

## Remember

- ✅ **Deterministic tasks** (discovery, action) are reliable and repeatable
- ⚖️ **Inference tasks** (decision) are based on policy and reasoning
- 📝 **Everything is audited** - can see what decided and why
- 🔒 **Audit log is tamper-proof** - SHA256 hashing detects changes
- 🧪 **Always use `--dry-run` first** to see what would happen
- 📊 **Monitor the audit trail** to learn approval patterns
- 🎛️ **Control via policy, not code** - edit JSON to change behavior

---

**Need help?** Check [APPROVAL_WORKFLOW_ARCHITECTURE.md](APPROVAL_WORKFLOW_ARCHITECTURE.md) for architectural details.
