#!/usr/bin/env bash
# Sets up the Catalyst project, App IDs, and the access-control configuration
# (`mcp-policy`) for the zero-trust MCP demo. The single `mcp-policy`
# resource gets rewritten between phases — see run_demo.sh.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PROJECT="${DIAGRID_PROJECT:-mcp-access-control}"

echo "================================================================"
echo "  Zero-Trust MCP Access Control — Catalyst setup"
echo "  Project: $PROJECT"
echo "================================================================"

# 1. Project ---------------------------------------------------------------
echo ""
echo ">>> Selecting Catalyst project..."
if ! diagrid project get "$PROJECT" >/dev/null 2>&1; then
    diagrid project create "$PROJECT" --wait
fi
diagrid project use "$PROJECT"

# 2. App IDs ---------------------------------------------------------------
echo ""
echo ">>> Creating App IDs (idempotent)..."
for appid in mcp-server ops-agent analysis-agent supervisor-agent; do
    if ! diagrid appid get "$appid" --project "$PROJECT" >/dev/null 2>&1; then
        diagrid appid create "$appid" --project "$PROJECT" --wait
    else
        echo "  (exists) $appid"
    fi
done

# 3. Initial access-control state: lock everything down -------------------
echo ""
echo ">>> Applying mcp-policy (initial state: deny-all)..."
diagrid apply --project "$PROJECT" -f config/phase1-deny-all.yaml

# 4. Attach to mcp-server -------------------------------------------------
echo ""
echo ">>> Attaching mcp-policy to mcp-server..."
diagrid appid update mcp-server --project "$PROJECT" --app-config mcp-policy

echo ""
echo "================================================================"
echo "  Setup complete. Follow DEMO.md from here on."
echo "================================================================"
