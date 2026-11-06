# Zero-Trust MCP Access Control — Diagrid Demo

A live-webinar demo showing how Diagrid (built on Dapr) enforces per-tool
access policies for an MCP server. Three agents — **ops**, **analysis**,
**supervisor** — share one MCP server and one Postgres database; Diagrid
decides who can call which tool.

> **Full walkthrough:** see [DEMO.md](./DEMO.md).

## TL;DR

```bash
# One-time setup
pip3 install -r requirements.txt
psql -d postgres -c "CREATE DATABASE zerotrust_demo;"
psql -d zerotrust_demo -f sql/init.sql
./setup.sh

# Terminal A — keep the MCP server running through Catalyst
diagrid dev run --project mcp-access-control --app-id mcp-server \
    --app-port 8000 --yes --skip-default-resiliency \
    -- python3 mcp_server/server.py

# Terminal B — phase 1 (deny-all): everything is denied
diagrid apply --project mcp-access-control -f config/phase1-deny-all.yaml
sleep 15
diagrid dev run --project mcp-access-control --app-id ops-agent        --yes --skip-default-resiliency -- python3 agents/ops_agent.py        # then Ctrl+C
diagrid dev run --project mcp-access-control --app-id analysis-agent   --yes --skip-default-resiliency -- python3 agents/analysis_agent.py   # then Ctrl+C
diagrid dev run --project mcp-access-control --app-id supervisor-agent --yes --skip-default-resiliency -- python3 agents/supervisor_agent.py # then Ctrl+C

# Terminal B — phase 2 (per-agent allows): only supervisor can delete
diagrid apply --project mcp-access-control -f config/phase2-zerotrust.yaml
sleep 15
diagrid dev run --project mcp-access-control --app-id ops-agent        --yes --skip-default-resiliency -- python3 agents/ops_agent.py        # then Ctrl+C
diagrid dev run --project mcp-access-control --app-id analysis-agent   --yes --skip-default-resiliency -- python3 agents/analysis_agent.py   # then Ctrl+C
diagrid dev run --project mcp-access-control --app-id supervisor-agent --yes --skip-default-resiliency -- python3 agents/supervisor_agent.py # then Ctrl+C
```

Full walkthrough: see [DEMO.md](./DEMO.md).

## Access matrix

|                       | schema | query | write | delete |
| --------------------- | :----: | :---: | :---: | :----: |
| **ops-agent**         |   ✓    |   ✓   |   ✓   |   ✗    |
| **analysis-agent**    |   ✓    |   ✓   |   ✗   |   ✗    |
| **supervisor-agent**  |   ✓    |   ✓   |   ✓   |   ✓    |

## Two-phase demo

A single Diagrid `Configuration` named `mcp-policy` is attached to
`mcp-server`. The demo rewrites its contents between phases:

| Phase | YAML applied                  | Result |
| ----- | ----------------------------- | ------ |
| 1 — Zero trust | `config/phase1-deny-all.yaml`    | `mcp-policy.defaultAction=deny`, no policies. Every call from every agent is denied. |
| 2 — Explicit allows | `config/phase2-zerotrust.yaml` | `mcp-policy.defaultAction=deny` + per-agent per-tool allows. Each agent reaches only its authorised tools; only the supervisor can `delete`. |

## Cleanup

See the cleanup section in [DEMO.md](./DEMO.md).
