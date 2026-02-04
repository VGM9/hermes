#!/usr/bin/env python3
"""
HERMES Approval Orchestrator - Workflow coordinator for agent approval decisions

ARCHITECTURE (Complete Workflow):

Step 1: DISCOVERY (Deterministic)
  → hermes_agent_discovery.discover_paused_agents()
  → Returns: List of PausedAgent objects with facts

Step 2: DECISION (Inference)  
  → hermes_approval_decision.ApprovalDecisionMaker.evaluate()
  → Takes facts + policy → Returns decision with reasoning

Step 3: AUDIT (Recording)
  → hermes_approval_log.ApprovalAuditLog.log_decision()
  → Records decision to immutable log

Step 4: ACTION (Deterministic Execution)
  → hermes_wake.approve_agent() or skip_agent()
  → Clicks the button

This orchestrator is the "glue" between deterministic and inference layers.
"""

import json
import logging
import argparse
import sys
from typing import Dict, List, Optional, Any
from pathlib import Path
import time

# Import the layered components
try:
    import hermes_agent_discovery
except ImportError:
    print("ERROR: hermes_agent_discovery not found")
    sys.exit(1)

try:
    import hermes_approval_decision
except ImportError:
    print("ERROR: hermes_approval_decision not found")
    sys.exit(1)

try:
    import hermes_approval_log
except ImportError:
    print("ERROR: hermes_approval_log not found")
    sys.exit(1)

try:
    import hermes_wake
except ImportError:
    print("ERROR: hermes_wake not found")
    sys.exit(1)

logger = logging.getLogger(__name__)


class ApprovalOrchestrator:
    """Coordinates the complete approval workflow."""
    
    def __init__(self, policy_path: Optional[str] = None, log_path: Optional[str] = None, dry_run: bool = False):
        """
        Initialize orchestrator.
        
        Args:
            policy_path: Path to approval policy JSON
            log_path: Path to audit log
            dry_run: If True, don't actually click buttons
        """
        self.decision_maker = hermes_approval_decision.ApprovalDecisionMaker(policy_path)
        self.audit_log = hermes_approval_log.ApprovalAuditLog(log_path)
        self.dry_run = dry_run
        
        if dry_run:
            logger.warning("DRY RUN MODE - No buttons will be clicked")
    
    def run_workflow(self, agent_nonce: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the complete approval workflow.
        
        Steps:
        1. Discover paused agents
        2. For each: decide (policy-based reasoning)
        3. Log decision
        4. Execute action (or skip in dry-run)
        
        Args:
            agent_nonce: Optional nonce from requesting agent
        
        Returns:
            Result summary
        """
        logger.info("=== HERMES Approval Orchestrator Starting ===")
        
        # STEP 1: DISCOVERY (Deterministic)
        logger.info("STEP 1: Discovering paused agents...")
        discovery_report = hermes_agent_discovery.discover_paused_agents()
        
        logger.info(f"Found {discovery_report.total_paused} paused agent(s)")
        
        if discovery_report.total_paused == 0:
            logger.info("No paused agents found. Exiting.")
            return {
                'success': True,
                'paused_agents': 0,
                'actions_taken': []
            }
        
        actions_taken = []
        
        # Process each paused agent
        for agent in discovery_report.paused_agents:
            logger.info(f"\nProcessing paused agent: {agent.session_id}")
            
            # STEP 2: DECISION (Inference)
            logger.info("STEP 2: Making approval decision...")
            decision = self.decision_maker.evaluate(
                agent.session_id,
                agent.action_name
            )
            
            logger.info(f"Decision: {decision.decision.value} (confidence: {decision.confidence*100:.0f}%)")
            logger.info(f"Reason: {decision.decision_reason}")
            logger.info(f"Policy Rule: {decision.policy_rule_matched}")
            
            # STEP 3: AUDIT (Record)
            logger.info("STEP 3: Logging decision to audit trail...")
            entry_hash = self.audit_log.log_decision(decision.to_dict(), nonce=agent_nonce)
            logger.info(f"Audit entry: {entry_hash[:8]}...")
            
            # STEP 4: ACTION (Execute or record)
            logger.info("STEP 4: Executing action...")
            
            if self.dry_run:
                logger.warning(f"[DRY RUN] Would execute: {decision.decision.value}")
                action_result = {
                    'window_handle': agent.window_handle,
                    'action': decision.decision.value,
                    'dry_run': True,
                    'success': True
                }
            else:
                action_result = self._execute_action(agent, decision)
            
            actions_taken.append({
                'agent': agent.to_dict(),
                'decision': decision.to_dict(),
                'audit_hash': entry_hash,
                'action_result': action_result
            })
            
            # Brief pause between actions
            if len(actions_taken) < discovery_report.total_paused:
                time.sleep(0.5)
        
        logger.info(f"\n=== Workflow Complete ===")
        logger.info(f"Processed {len(actions_taken)} agent(s)")
        
        return {
            'success': True,
            'paused_agents': discovery_report.total_paused,
            'actions_taken': actions_taken
        }
    
    def _execute_action(self, agent: hermes_agent_discovery.PausedAgent,
                        decision: hermes_approval_decision.ApprovalDecision) -> Dict[str, Any]:
        """Execute the approval action (click button)."""
        try:
            from pywinauto import Application
            
            # Connect to the window
            app = Application(backend="uia").connect(handle=agent.window_handle)
            win = app.window(handle=agent.window_handle)
            
            if decision.decision == hermes_approval_decision.DecisionType.APPROVE:
                logger.info(f"Executing APPROVE on window {agent.window_handle}...")
                
                # Determine if we should click "Always Allow" or just "Allow"
                always = agent.is_split_button  # If split button available, use Always
                
                success = hermes_wake.approve_agent(win, always=always)
                
                return {
                    'window_handle': agent.window_handle,
                    'action': 'APPROVE',
                    'always': always,
                    'success': success
                }
            
            elif decision.decision == hermes_approval_decision.DecisionType.SKIP:
                logger.info(f"Executing SKIP on window {agent.window_handle}...")
                
                success = hermes_wake.skip_agent(win)
                
                return {
                    'window_handle': agent.window_handle,
                    'action': 'SKIP',
                    'success': success
                }
            
            else:  # REQUEST_REVIEW
                logger.info(f"Decision is REQUEST_REVIEW - not taking action")
                return {
                    'window_handle': agent.window_handle,
                    'action': 'REQUEST_REVIEW',
                    'success': True,
                    'note': 'Awaiting human decision'
                }
        
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return {
                'window_handle': agent.window_handle,
                'action': decision.decision.value,
                'success': False,
                'error': str(e)
            }
    
    def run_audit_report(self):
        """Generate and print audit report."""
        logger.info("=== Approval Audit Report ===")
        hermes_approval_log.print_audit_summary(self.audit_log)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="HERMES Approval Orchestrator - Workflow coordinator for agent approval decisions"
    )
    
    parser.add_argument(
        'action',
        choices=['run', 'audit', 'verify'],
        help='Action to perform'
    )
    
    parser.add_argument(
        '--policy',
        help='Path to approval policy JSON'
    )
    
    parser.add_argument(
        '--log',
        help='Path to audit log'
    )
    
    parser.add_argument(
        '--nonce',
        help='Nonce from requesting agent (for audit trail)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate actions without clicking buttons'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    # Create orchestrator
    orchestrator = ApprovalOrchestrator(
        policy_path=args.policy,
        log_path=args.log,
        dry_run=args.dry_run
    )
    
    try:
        if args.action == 'run':
            result = orchestrator.run_workflow(agent_nonce=args.nonce)
            
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\nWorkflow Result:")
                print(f"  Success: {result['success']}")
                print(f"  Paused Agents: {result['paused_agents']}")
                print(f"  Actions Taken: {len(result['actions_taken'])}")
        
        elif args.action == 'audit':
            orchestrator.run_audit_report()
        
        elif args.action == 'verify':
            ok = orchestrator.audit_log.verify_integrity()
            if args.json:
                print(json.dumps({'integrity_ok': ok}))
            else:
                status = "✓ PASS" if ok else "✗ FAIL"
                print(f"Audit Log Integrity: {status}")
            sys.exit(0 if ok else 1)
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
