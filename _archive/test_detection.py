"""
Test script for detection functionality.
"""

from detection import find_paused_agents
import json
import sys

print("Searching for paused agents...", flush=True)
sys.stdout.flush()

try:
    agents = find_paused_agents()
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\nFound {len(agents)} paused agent(s)\n")

for i, agent in enumerate(agents, 1):
    print(f"Agent #{i}:")
    print(f"  Window: {agent.window_title}")
    print(f"  Request Type: {agent.request_type}")
    print(f"  Files: {len(agent.files_to_access)}")
    if agent.files_to_access:
        for f in agent.files_to_access[:3]:
            print(f"    - {f}")
        if len(agent.files_to_access) > 3:
            print(f"    ... and {len(agent.files_to_access) - 3} more")
    
    print(f"  Commands: {len(agent.commands_to_run)}")
    if agent.commands_to_run:
        for cmd in agent.commands_to_run[:2]:
            print(f"    - {cmd[:80]}...")
    
    print(f"  Allow button: {'Found' if agent.has_allow_button else 'Missing'}")
    print(f"  Skip button: {'Found' if agent.has_skip_button else 'Missing'}")
    print(f"  Command safety: {agent.command_safety}")
    print(f"  Read-only: {agent.is_read_only_request()}")
    print()

# Export first agent as JSON for inspection
if agents:
    print("\nFirst agent as JSON:")
    print(json.dumps(agents[0].to_dict(), indent=2))
