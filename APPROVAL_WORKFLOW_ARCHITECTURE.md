# HERMES Approval Workflow Architecture

This document explains the **separation of concerns** between deterministic (machine) operations and inference (LLM reasoning) operations in the agent approval system.

## The Quest

The challenge: How do you coordinate approval decisions between multiple concurrent AI agents without creating monolithic scripts that try to do everything at once?

**Answer**: Separate **deterministic tasks** (facts, state reading, button clicking) from **inference tasks** (policy evaluation, judgments, decisions).

## Workflow Architecture

The approval workflow is divided into **4 discrete stages**, each with a single responsibility:

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: DISCOVERY (Deterministic)                          │
│ hermes_agent_discovery.py                                   │
│                                                              │
│ RESPONSIBILITY: Find all paused agents awaiting approval   │
│ METHOD: Read VSCode window state via UIAutomation          │
│ OUTPUT: List of PausedAgent objects with facts             │
│ PURITY: Pure function - no side effects                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2: DECISION (Inference - LLM Reasoning)               │
│ hermes_approval_decision.py                                 │
│                                                              │
│ RESPONSIBILITY: Evaluate each agent request                 │
│ METHOD: Match discovered facts against policy rules        │
│ INPUT: (agent_action, policy_framework)                    │
│ OUTPUT: ApprovalDecision (what to do + why)                │
│ LOGIC: Rule matching, confidence scoring, alternatives     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3: AUDIT (Recording)                                  │
│ hermes_approval_log.py                                      │
│                                                              │
│ RESPONSIBILITY: Immutable record of all decisions           │
│ METHOD: Append-only JSONL audit trail                       │
│ INPUT: ApprovalDecision → stored with hash verification    │
│ OUTPUT: entry_hash (for verification)                       │
│ GUARANTEE: Tamper detection via SHA256 hashing             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4: ACTION (Deterministic Execution)                   │
│ hermes_wake.py (approve_agent / skip_agent)                 │
│                                                              │
│ RESPONSIBILITY: Execute the decision                        │
│ METHOD: Click Allow/Skip buttons via UIAutomation          │
│ IDEMPOTENT: Clicking twice is safe                         │
│ ROLLBACK: Can't undo - but fully audited                   │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. **Deterministic ↔ Inference Boundaries**

Each stage either:
- **Reads state** (discovery, observation) → Fully deterministic
- **Evaluates policy** (decision making) → Can involve reasoning/inference
- **Records facts** (audit) → Deterministic append-only
- **Takes action** (execution) → Deterministic button clicks

### 2. **Data Flow - Immutable Between Stages**

Each stage receives **read-only** data from the previous stage:

```
PausedAgent (immutable) 
    → ApprovalDecision (immutable)
        → audit_entry (immutable hash)
            → Action result
```

Stages never modify upstream data.

### 3. **Auditable Decision Trail**

Every decision is recorded with:
- **What**: The specific action being approved/rejected
- **Why**: Policy rule that matched + reasoning
- **Who**: Which agent made the decision
- **When**: Exact timestamp
- **Where**: Session ID + window handle
- **Proof**: SHA256 hash of decision entry

Example audit entry:
```json
{
  "timestamp": "2026-02-04T08:55:00Z",
  "policy_rule_matched": "ALWAYS_APPROVE_READ_OPERATIONS",
  "decision": "APPROVE",
  "decision_reason": "Read-only operations pose no risk",
  "confidence": 0.95,
  "session_id": "3c8d9862-404a-46c0-9681-21559f9c09e4",
  "entry_hash": "a3d7f2e..."
}
```

### 4. **Policy-Driven Decisions**

All decisions are made through **explicit policy rules**, not arbitrary code:

```json
{
  "id": "ALWAYS_APPROVE_READ_OPERATIONS",
  "match": {"action_name_contains": ["read", "grep", "file_search"]},
  "decision": "APPROVE",
  "reason": "Read-only operations pose no risk"
}
```

This allows:
- ✅ Non-technical review of approval rules
- ✅ Easy adjustment of policy without code changes
- ✅ Clear audit of what policy governs what decision
- ✅ Debate/discussion about rules is decoupled from code

## Usage Examples

### Example 1: Find and approve all safe operations

```bash
# Discover what agents are paused
python hermes_agent_discovery.py --json

# Make decisions automatically
python hermes_approval_decision.py \
  --session 3c8d9862-404a-46c0-9681-21559f9c09e4 \
  --action "grep_search" \
  --json

# Full workflow (discover → decide → log → execute)
python hermes_approval_orchestrator.py run
```

### Example 2: Review audit trail of decisions

```bash
# Show recent decisions
python hermes_approval_log.py --tail 10

# Stats on approval patterns
python hermes_approval_log.py --summary

# Verify no tampering
python hermes_approval_log.py --verify
```

### Example 3: Dry-run before actually clicking buttons

```bash
# See what WOULD happen without taking action
python hermes_approval_orchestrator.py run --dry-run
```

### Example 4: Integrate into another workflow

```python
from hermes_agent_discovery import discover_paused_agents
from hermes_approval_decision import ApprovalDecisionMaker
from hermes_approval_log import ApprovalAuditLog

# Discovery (deterministic)
agents = discover_paused_agents()

# Decision (inference)
maker = ApprovalDecisionMaker()
for agent in agents.paused_agents:
    decision = maker.evaluate(agent.session_id, agent.action_name)
    
    # Audit (recording)
    log = ApprovalAuditLog()
    log.log_decision(decision.to_dict())
    
    # Action (execution)
    if decision.decision == DecisionType.APPROVE:
        execute_approval(agent)
```

## Policy Framework

The policy file (`hermes_approval_policy.json`) defines all approval rules:

```json
{
  "approval_rules": {
    "rules": [
      {
        "id": "rule_name",
        "description": "Human-readable description",
        "match": {
          "action_name_contains": ["grep", "read"],
          "action_name_not_contains": ["delete"]
        },
        "decision": "APPROVE | REQUEST_REVIEW | SKIP",
        "reason": "Why this decision"
      }
    ]
  }
}
```

### Decision Types

| Decision | Meaning | Action |
|----------|---------|--------|
| `APPROVE` | Auto-approve (safe operation) | Click Allow button |
| `REQUEST_REVIEW` | Needs human decision | Leave pending for human |
| `SKIP` | Auto-reject (dangerous operation) | Click Skip button |

## File Inventory

| File | Purpose | Type |
|------|---------|------|
| `hermes_agent_discovery.py` | Enumerate paused agents | Deterministic |
| `hermes_approval_decision.py` | Evaluate requests against policy | Inference |
| `hermes_approval_policy.json` | Policy rules (data, not code) | Configuration |
| `hermes_approval_log.py` | Audit trail (immutable JSONL) | Recording |
| `hermes_approval_orchestrator.py` | Workflow coordinator | Orchestration |
| `hermes_wake.py` | Click buttons in VSCode | Deterministic |

## Key Insights

### 1. **Stages are Independently Testable**

Each stage only depends on the previous one's output:

```python
# Test discovery alone
agents = discover_paused_agents()

# Test decision alone (no UI needed)
decision = maker.evaluate(session_id, action_name)

# Test audit alone (no UI needed)
log.log_decision(decision)

# Test action alone (with mock window)
approve_agent(mock_window)
```

### 2. **Decisions are Explainable**

The decision module outputs why it decided what:
- Which policy rule matched?
- How confident is the decision?
- What could have been decided alternatively?

This creates accountability and enables learning.

### 3. **Parallelism is Possible**

Since each agent's decision is independent:

```python
# Process multiple paused agents in parallel
from concurrent.futures import ThreadPoolExecutor

agents = discover_paused_agents()

with ThreadPoolExecutor() as executor:
    decisions = executor.map(
        lambda a: maker.evaluate(a.session_id, a.action_name),
        agents.paused_agents
    )
```

### 4. **Approval Bottlenecks are Observable**

Because every decision is logged, you can see:
- How many agents are in REQUEST_REVIEW (waiting for human)?
- Which rules trigger most often?
- Are certain sessions always approved/rejected?

## Next Steps

1. **Customize the policy** (`hermes_approval_policy.json`) for your use case
2. **Run the discovery** to see what agents are currently paused
3. **Test decisions** with `--dry-run` before enabling live mode
4. **Monitor the audit log** to learn what patterns emerge
5. **Adjust policy** based on audit insights

## Anti-Patterns to Avoid

❌ **Don't**: Embed approval logic in the decision code
✅ **Do**: Put all rules in the JSON policy file

❌ **Don't**: Make decisions without auditing them
✅ **Do**: Always log to the audit trail

❌ **Don't**: Try to do discovery + decision + action in one script
✅ **Do**: Chain small, single-responsibility modules

❌ **Don't**: Modify the audit log
✅ **Do**: Treat it as immutable truth

## Integration with Other Agents

When another agent needs approval:

1. It calls `run_in_terminal()` with a nonce
2. As an LLM, you generate the nonce and include it in the command
3. Later, you call the discovery module to find paused agents
4. You pass the nonce to the audit log for traceability:

```python
# From another agent
nonce = "HERMES_NONCE_abc123"
run_in_terminal(f"ls {nonce}")

# Later, when reviewing approvals
report = discover_paused_agents()
orchestrator.run_workflow(agent_nonce=nonce)
```

The nonce ties the approval back to your original decision.
