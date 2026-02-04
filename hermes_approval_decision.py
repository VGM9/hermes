#!/usr/bin/env python3
"""
HERMES Approval Decision - Inference layer for evaluating agent requests

ARCHITECTURE (Separation of Concerns):
- hermes_agent_discovery.py → Deterministic facts (what agents are paused?)
- THIS MODULE → Inference logic (should we approve based on policy?)
- hermes_approval_log.py → Auditable recording of decisions  
- hermes_approval_orchestrator.py → Action layer (click button)

This module is INFERENCE - it uses LLM-like reasoning to match policy rules.
It takes discovered agents + policy framework and outputs decisions with reasoning.

INPUT: PausedAgent, ApprovalPolicy
OUTPUT: ApprovalDecision (with full reasoning trail)
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum
import re

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Decision outcome options."""
    APPROVE = "APPROVE"                # Auto-approve this request
    REQUEST_REVIEW = "REQUEST_REVIEW"  # Wait for human decision
    SKIP = "SKIP"                      # Auto-reject this request


@dataclass
class PolicyRule:
    """Represents a single policy rule."""
    id: str
    description: str
    match: Dict[str, List[str]]
    decision: str
    reason: str


@dataclass
class ApprovalDecision:
    """Record of an agent approval decision."""
    agent_session_id: str
    agent_action: Optional[str]
    policy_rule_matched: str           # Which policy rule fired
    decision: DecisionType
    decision_reason: str
    confidence: float                   # 0.0-1.0
    alternative_decision: Optional[str] # What we could have decided
    timestamp: float
    deciding_agent_id: str = "HERMES"  # This LLM making the decision
    approving_agent_id: Optional[str] = None  # Agent doing the approving (if different)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent_session_id': self.agent_session_id,
            'agent_action': self.agent_action,
            'policy_rule_matched': self.policy_rule_matched,
            'decision': self.decision.value,
            'decision_reason': self.decision_reason,
            'confidence': self.confidence,
            'alternative_decision': self.alternative_decision,
            'timestamp': self.timestamp,
            'deciding_agent_id': self.deciding_agent_id,
            'approving_agent_id': self.approving_agent_id
        }


class ApprovalDecisionMaker:
    """Evaluates agent requests against policy using rule matching."""
    
    def __init__(self, policy_path: Optional[str] = None):
        """Initialize decision maker with policy rules."""
        self.policy = self._load_policy(policy_path)
        self.rules = self._parse_policy_rules()
    
    def _load_policy(self, policy_path: Optional[str]) -> Dict[str, Any]:
        """Load approval policy from JSON file."""
        if policy_path is None:
            # Use default location
            policy_path = Path(__file__).parent / "hermes_approval_policy.json"
        
        try:
            with open(policy_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Policy file not found: {policy_path}. Using empty policy.")
            return self._default_policy()
    
    def _default_policy(self) -> Dict[str, Any]:
        """Minimal policy if file not found."""
        return {
            "approval_rules": {"rules": []},
            "approval_rules": {"fallback": {"default_decision": "REQUEST_REVIEW"}}
        }
    
    def _parse_policy_rules(self) -> List[PolicyRule]:
        """Parse policy JSON into rule objects."""
        rules = []
        try:
            for rule_data in self.policy.get('approval_rules', {}).get('rules', []):
                rule = PolicyRule(
                    id=rule_data['id'],
                    description=rule_data['description'],
                    match=rule_data['match'],
                    decision=rule_data['decision'],
                    reason=rule_data['reason']
                )
                rules.append(rule)
        except Exception as e:
            logger.error(f"Error parsing policy: {e}")
        
        return rules
    
    def evaluate(self, agent_session_id: str, agent_action: Optional[str]) -> ApprovalDecision:
        """
        Evaluate whether to approve or skip an agent request.
        
        Args:
            agent_session_id: Session UUID of the requesting agent
            agent_action: Name/description of the action being requested
        
        Returns:
            ApprovalDecision with reasoning
        """
        import time
        
        action_lower = (agent_action or "").lower()
        matched_rule = None
        matched_decision = None
        
        # Try to match each policy rule
        for rule in self.rules:
            if self._rule_matches(action_lower, rule):
                matched_rule = rule
                matched_decision = rule.decision
                break
        
        # If no rule matched, use fallback
        if matched_rule is None:
            fallback = self.policy.get('approval_rules', {}).get('fallback', {})
            matched_decision = fallback.get('default_decision', 'REQUEST_REVIEW')
            matched_reason = fallback.get('reason', 'No policy rules matched')
            matched_rule_id = 'FALLBACK'
        else:
            matched_reason = matched_rule.reason
            matched_rule_id = matched_rule.id
        
        # Convert decision string to enum
        decision_type = DecisionType[matched_decision]
        
        # Calculate confidence based on rule specificity
        confidence = self._calculate_confidence(matched_rule, action_lower)
        
        # Determine reason text
        if matched_decision == 'SKIP':
            reason_template = self.policy.get('approval_options', {}).get('SKIP', {}).get('reason_format', '{reason}')
            reason = reason_template.format(reason=matched_reason)
        else:
            reason = matched_reason
        
        # Alternative decision logic
        alternative = self._suggest_alternative(decision_type)
        
        decision = ApprovalDecision(
            agent_session_id=agent_session_id,
            agent_action=agent_action,
            policy_rule_matched=matched_rule_id,
            decision=decision_type,
            decision_reason=reason,
            confidence=confidence,
            alternative_decision=alternative,
            timestamp=time.time(),
            approving_agent_id=self._detect_approving_agent(agent_session_id)
        )
        
        return decision
    
    def _rule_matches(self, action_lower: str, rule: PolicyRule) -> bool:
        """Check if action matches a policy rule."""
        match_spec = rule.match
        
        # Check positive matches (contains)
        contains = match_spec.get('action_name_contains', [])
        if contains:
            if not any(c.lower() in action_lower for c in contains):
                return False
        
        # Check negative matches (not contains)
        not_contains = match_spec.get('action_name_not_contains', [])
        if not_contains:
            if any(c.lower() in action_lower for c in not_contains):
                return False
        
        return True
    
    def _calculate_confidence(self, rule: Optional[PolicyRule], action: str) -> float:
        """Calculate confidence in the decision (0.0-1.0)."""
        if rule is None:
            return 0.5  # Low confidence for fallback
        
        # Higher confidence if more specific match
        specificity = len(rule.match.get('action_name_contains', []))
        if specificity == 0:
            return 0.6
        elif specificity == 1:
            return 0.8
        else:
            return 0.95
    
    def _suggest_alternative(self, decision: DecisionType) -> Optional[str]:
        """Suggest what could have been decided instead."""
        if decision == DecisionType.APPROVE:
            return "REQUEST_REVIEW (more cautious)"
        elif decision == DecisionType.REQUEST_REVIEW:
            return "APPROVE (more permissive) or SKIP (more restrictive)"
        else:  # SKIP
            return "REQUEST_REVIEW (less restrictive)"
    
    def _detect_approving_agent(self, session_id: str) -> Optional[str]:
        """Detect which agent called this session if possible."""
        # Could integrate with agent registry
        return None


def print_decision(decision: ApprovalDecision):
    """Pretty-print a decision."""
    print(f"\n=== HERMES Approval Decision ===")
    print(f"Session: {decision.agent_session_id}")
    print(f"Action: {decision.agent_action}")
    print(f"Decision: {decision.decision.value}")
    print(f"Confidence: {decision.confidence * 100:.0f}%")
    print(f"Reason: {decision.decision_reason}")
    print(f"Policy Rule: {decision.policy_rule_matched}")
    print(f"Alternative: {decision.alternative_decision}")
    print()


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Evaluate agent approval requests")
    parser.add_argument('--session', required=True, help='Agent session ID')
    parser.add_argument('--action', help='Agent action name')
    parser.add_argument('--policy', help='Policy file path')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    maker = ApprovalDecisionMaker(args.policy)
    decision = maker.evaluate(args.session, args.action)
    
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
    else:
        print_decision(decision)
    
    sys.exit(0)
