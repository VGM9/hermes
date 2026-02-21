"""Test detection with simplified has_chat_panel."""

from detection import find_paused_agents
import json
import time

print("Starting detection...", flush=True)
start = time.time()

try:
    agents = find_paused_agents()
    elapsed = time.time() - start
    
    print(f"\nCompleted in {elapsed:.2f}s", flush=True)
    print(f"Found {len(agents)} paused agent(s)\n", flush=True)
    
    for i, agent in enumerate(agents, 1):
        print(f"Agent #{i}:")
        print(f"  Window: {agent.window_title[:60]}")
        print(f"  Request Type: {agent.request_type}")
        print(f"  Files: {len(agent.files_to_access)}")
        print(f"  Commands: {len(agent.commands_to_run)}")
        print(f"  Allow button: {'Found' if agent.has_allow_button else 'Missing'}")
        print(f"  Skip button: {'Found' if agent.has_skip_button else 'Missing'}")
        print()

except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
