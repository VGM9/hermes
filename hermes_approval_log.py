#!/usr/bin/env python3
"""
HERMES Approval Audit Log - Immutable record of all approval decisions

ARCHITECTURE:
This module maintains an append-only audit trail of all approval decisions.
Used for:
- Compliance & accountability
- Learning from past decisions
- Debugging approval bot behavior
- Detecting approval patterns/anomalies

The log is IMMUTABLE - decisions are never deleted, only appended.
Format: JSONL (one decision per line, newline-delimited JSON)

Each entry includes:
- What was decided and why
- Who made the decision
- When the decision was made
- What could have been decided instead (alternative)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class ApprovalAuditLog:
    """Immutable append-only audit log for approval decisions."""
    
    def __init__(self, log_path: Optional[str] = None):
        """
        Initialize audit log.
        
        Args:
            log_path: Path to JSONL audit log file. 
                      If None, uses default: ~/.vscode/hermes/approval_audit.jsonl
        """
        if log_path is None:
            from pathlib import Path
            import hermes_config
            appdata = hermes_config.get_appdata_path()
            log_dir = appdata.parent / 'hermes'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / 'approval_audit.jsonl'
        
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Audit log: {self.log_path}")
    
    def log_decision(self, decision: Dict[str, Any], nonce: Optional[str] = None) -> str:
        """
        Append a decision to the audit log.
        
        Args:
            decision: ApprovalDecision.to_dict() output
            nonce: Optional nonce from the requesting agent's tool call
        
        Returns:
            entry_hash: Hash of the log entry (for verification)
        """
        try:
            # Add metadata
            entry = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'log_index': self._next_index(),
                'nonce': nonce,
                'decision': decision
            }
            
            # Calculate entry hash
            entry_hash = self._calculate_hash(entry)
            entry['entry_hash'] = entry_hash
            
            # Append to JSONL file
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')
            
            logger.info(f"Decision logged: {entry_hash[0:8]}... → {decision.get('decision', 'UNKNOWN')}")
            
            return entry_hash
            
        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
            raise
    
    def _next_index(self) -> int:
        """Get next log index."""
        try:
            if self.log_path.exists():
                with open(self.log_path, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last = json.loads(lines[-1])
                        return last.get('log_index', 0) + 1
            return 0
        except:
            return 0
    
    def _calculate_hash(self, entry: Dict[str, Any]) -> str:
        """Calculate SHA256 hash of entry."""
        # Create deterministic JSON for hashing
        entry_copy = {k: v for k, v in entry.items() if k != 'entry_hash'}
        json_str = json.dumps(entry_copy, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def read_entries(self, limit: Optional[int] = None, reverse: bool = False) -> List[Dict[str, Any]]:
        """
        Read audit log entries.
        
        Args:
            limit: Maximum number of entries to read
            reverse: If True, read in reverse order (newest first)
        
        Returns:
            List of audit entries
        """
        try:
            if not self.log_path.exists():
                return []
            
            entries = []
            with open(self.log_path, 'r') as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
            
            if reverse:
                entries.reverse()
            
            if limit:
                entries = entries[:limit]
            
            return entries
            
        except Exception as e:
            logger.error(f"Error reading audit log: {e}")
            return []
    
    def get_decision_stats(self) -> Dict[str, Any]:
        """Get statistics about decisions in the log."""
        entries = self.read_entries()
        
        stats = {
            'total_decisions': len(entries),
            'approve_count': 0,
            'skip_count': 0,
            'request_review_count': 0,
            'by_session': {},
            'by_policy_rule': {}
        }
        
        for entry in entries:
            decision = entry.get('decision', {})
            decision_type = decision.get('decision', 'UNKNOWN')
            session = decision.get('agent_session_id', 'UNKNOWN')
            rule = decision.get('policy_rule_matched', 'UNKNOWN')
            
            if decision_type == 'APPROVE':
                stats['approve_count'] += 1
            elif decision_type == 'SKIP':
                stats['skip_count'] += 1
            elif decision_type == 'REQUEST_REVIEW':
                stats['request_review_count'] += 1
            
            # Count by session
            stats['by_session'][session] = stats['by_session'].get(session, 0) + 1
            
            # Count by rule
            stats['by_policy_rule'][rule] = stats['by_policy_rule'].get(rule, 0) + 1
        
        return stats
    
    def get_session_decisions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all decisions for a specific session."""
        entries = self.read_entries()
        return [e for e in entries if e.get('decision', {}).get('agent_session_id') == session_id]
    
    def verify_integrity(self) -> bool:
        """Verify audit log integrity by checking entry hashes."""
        try:
            entries = self.read_entries()
            for entry in entries:
                stored_hash = entry.get('entry_hash')
                calculated_hash = self._calculate_hash(entry)
                if stored_hash != calculated_hash:
                    logger.error(f"Hash mismatch in entry {entry.get('log_index')}")
                    return False
            
            logger.info(f"Audit log integrity verified ({len(entries)} entries)")
            return True
                
        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            return False


def print_audit_summary(log: ApprovalAuditLog):
    """Pretty-print audit log summary."""
    stats = log.get_decision_stats()
    
    print(f"\n=== HERMES Approval Audit Summary ===")
    print(f"Total Decisions: {stats['total_decisions']}")
    print(f"  APPROVE:       {stats['approve_count']}")
    print(f"  SKIP:          {stats['skip_count']}")  
    print(f"  REQUEST_REVIEW: {stats['request_review_count']}")
    print()
    print(f"Decisions by Policy Rule:")
    for rule, count in sorted(stats['by_policy_rule'].items(), key=lambda x: -x[1])[:5]:
        print(f"  {rule}: {count}")
    print()


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="View approval audit log")
    parser.add_argument('--log', help='Audit log path')
    parser.add_argument('--summary', action='store_true', help='Show summary stats')
    parser.add_argument('--session', help='Filter by session ID')
    parser.add_argument('--verify', action='store_true', help='Verify log integrity')
    parser.add_argument('--tail', type=int, help='Show last N entries')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    log = ApprovalAuditLog(args.log)
    
    if args.verify:
        ok = log.verify_integrity()
        sys.exit(0 if ok else 1)
    
    if args.summary:
        print_audit_summary(log)
    
    if args.session:
        entries = log.get_session_decisions(args.session)
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            print(f"Decisions for session {args.session}:")
            for e in entries:
                print(f"  {e['timestamp']}: {e['decision'].get('decision')}")
    
    if args.tail:
        entries = log.read_entries(limit=args.tail, reverse=True)
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            for e in entries:
                d = e['decision']
                print(f"{e['timestamp']}: {d.get('decision')} - {d.get('policy_rule_matched')}")
    
    sys.exit(0)
