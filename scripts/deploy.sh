#!/usr/bin/env bash
# deploy.sh — Deploy hermes from hermes-dev to software/hermes
#
# Usage:
#   ./scripts/deploy.sh               # deploy current main branch
#   ./scripts/deploy.sh --restart     # deploy + restart the daemon
#   ./scripts/deploy.sh --check       # show what would be deployed (dry run)
#
# This script is the ONLY sanctioned path from hermes-dev to production.
# Agents: do not copy files manually. Run this script.

set -euo pipefail

HERMES_DEV="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_PROD="$(cd "$HERMES_DEV/../../.." && pwd)/_/software/hermes"

if [[ ! -d "$HERMES_PROD/.git" ]]; then
    echo "ERROR: production hermes not found at $HERMES_PROD" >&2
    exit 1
fi

DEV_HEAD=$(cd "$HERMES_DEV" && git rev-parse --short HEAD)
PROD_HEAD=$(cd "$HERMES_PROD" && git rev-parse --short HEAD)

echo "[deploy] hermes-dev HEAD:  $DEV_HEAD"
echo "[deploy] software/hermes:  $PROD_HEAD"

if [[ "$1" == "--check" ]]; then
    if [[ "$DEV_HEAD" == "$PROD_HEAD" ]]; then
        echo "[deploy] Production is up to date."
    else
        echo "[deploy] GAP DETECTED — the following commits are not in production:"
        cd "$HERMES_PROD" && git log --oneline HEAD.."origin/main" 2>/dev/null || \
            echo "(run: git fetch origin in $HERMES_PROD to see gap)"
    fi
    exit 0
fi

# Stop running daemon if present
PID_FILE="$HERMES_PROD/hermes_daemon.pid"
if [[ -f "$PID_FILE" ]]; then
    echo "[deploy] Stopping running daemon..."
    cd "$HERMES_PROD" && python3 hermes_daemon.py --stop || true
    sleep 1
fi

# Pull main into production
echo "[deploy] Pulling main into $HERMES_PROD..."
cd "$HERMES_PROD" && git fetch origin && git checkout main && git merge --ff-only origin/main

NEW_HEAD=$(cd "$HERMES_PROD" && git rev-parse --short HEAD)
echo "[deploy] Deployed: $PROD_HEAD → $NEW_HEAD"

if [[ "$1" == "--restart" ]]; then
    echo "[deploy] Restarting daemon..."
    cd "$HERMES_PROD" && python3 hermes_daemon.py &
    disown
    sleep 1
    if [[ -f "$PID_FILE" ]]; then
        echo "[deploy] Daemon running (PID $(cat $PID_FILE))"
    else
        echo "[deploy] WARNING: PID file not found after restart" >&2
    fi
fi

echo "[deploy] Done."
