# Zero-Trust MCP Access Control with Diagrid

A live-webinar demo that shows how Diagrid (built on Dapr) enforces
per-tool access policies for an MCP server.

Three agents — **ops**, **analysis**, **supervisor** — all talk to **one**
MCP server backed by a local Postgres database. The MCP server exposes
four tools: `write`, `schema`, `query`, `delete`. Diagrid is the only
thing deciding which agent is allowed to call which tool.

---

## The access-policy matrix

|                       | `schema` | `query` | `write` | `delete` |
| --------------------- | :------: | :-----: | :-----: | :------: |
| **ops-agent**         |    ✓     |    ✓    |    ✓    |    ✗     |
| **analysis-agent**    |    ✓     |    ✓    |    ✗    |    ✗     |
| **supervisor-agent**  |    ✓     |    ✓    |    ✓    |    ✓     |

The supervisor is the **only** agent that can call `delete`.

---

## Architecture (everything runs locally)

```
   ┌─────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
   │   ops-agent     │    │  analysis-agent    │    │  supervisor-agent   │
   │ (App ID)        │    │ (App ID)           │    │ (App ID)            │
   └────────┬────────┘    └─────────┬──────────┘    └──────────┬──────────┘
            │                       │                          │
            │   /v1.0/invoke/mcp-server/method/<tool>/mcp + dapr-api-token
            │                       │                          │
            └───────────────────────┼──────────────────────────┘
                                    ▼
                ┌──────────────────────────────────────────────┐
                │     Diagrid Catalyst Cloud  (control plane)  │
                │  ── enforces Configuration accessControl  ── │
                └─────────────────────┬────────────────────────┘
                                      │   only requests allowed by policy
                                      ▼
                       ┌──────────────────────────────┐
                       │   mcp-server   (App ID)      │
                       │   single Python process,     │
                       │   four MCP endpoints:        │
                       │     /write/mcp               │
                       │     /schema/mcp              │
                       │     /query/mcp               │
                       │     /delete/mcp              │
                       └──────────────┬───────────────┘
                                      │ psycopg
                                      ▼
                              ┌────────────────┐
                              │ Postgres (5432)│
                              │ zerotrust_demo │
                              └────────────────┘
```

Why split the MCP server into four endpoints? Dapr's `accessControl`
matches on the **HTTP path** that comes after `…/method/`. Putting each
tool at its own path lets Diagrid allow `/write/mcp` for one agent and
deny `/delete/mcp` for the same agent, with a single Configuration
resource.

---

## Prerequisites

- **macOS / Linux** shell
- **Diagrid CLI** logged in (`diagrid whoami` should print your org)
- **PostgreSQL 14+** running locally and reachable as your shell user
- **Python 3.11+**

Sanity checks:

```bash
diagrid whoami
psql -d postgres -c '\l' | head -5
python3 --version
```

---

## Files in this directory

```
identity/
├── DEMO.md                    ← you are here
├── README.md
├── setup.sh                   one-time bootstrap (creates project + App IDs + config)
├── requirements.txt
├── sql/init.sql               creates customers + orders tables (seed data)
├── mcp_server/server.py       four-tool MCP server (one Python process)
├── agents/
│   ├── agent_lib.py
│   ├── ops_agent.py
│   ├── analysis_agent.py
│   └── supervisor_agent.py
└── config/
    ├── phase1-deny-all.yaml      mcp-policy = defaultAction: deny
    └── phase2-allow.yaml     mcp-policy = deny + per-agent allows
```

`mcp-policy` is a **single** Diagrid `Configuration` resource. It is
attached to `mcp-server` once at setup time. Both YAMLs declare
`metadata.name: mcp-policy` — applying them rewrites that resource in
place. The audience sees the same name throughout; only the contents
change between phases.

> If you use a different Diagrid project name (default is
> `mcp-access-control`), update `namespace:` inside
> `config/phase2-allow.yaml` to match — Diagrid uses the project
> name as the policy namespace.

---

## Step 0 — one-time setup

```bash
cd /Users/yaronschneider/dev/src/demos/identity

# 1. Python dependencies
pip3 install -r requirements.txt

# 2. Local Postgres database
psql -d postgres -c "CREATE DATABASE zerotrust_demo;"
psql -d zerotrust_demo -f sql/init.sql

# 3. Catalyst project, App IDs, and the initial mcp-policy (deny-all)
./setup.sh
```

`setup.sh` (the only script you ever run) creates / re-uses:

| Resource          | What                                                   |
| ----------------- | ------------------------------------------------------ |
| Project           | `mcp-access-control` (override with `DIAGRID_PROJECT`) |
| App IDs           | `mcp-server`, `ops-agent`, `analysis-agent`, `supervisor-agent` |
| Configuration     | `mcp-policy` — initially deny-all                      |
| App-config link   | `mcp-server` ↦ `mcp-policy`                            |

After this, the MCP server is locked down — no agent can reach any tool
until you start the demo.

---

## Step 1 — start the MCP server (Terminal A)

```bash
diagrid dev run \
    --project mcp-access-control \
    --app-id mcp-server --app-port 8000 \
    --yes --skip-default-resiliency \
    -- python3 mcp_server/server.py
```

Leave Terminal A alone for the rest of the demo. You'll see the server
log each request Diagrid *allows through* (phase 1 will be quiet —
every request is blocked at Diagrid, never reaches the server).

---

## Step 2 — the demo (Terminal B)

Everything below is just `diagrid` and `python3` invocations. Run them
one at a time so you can narrate.

### Phase 1 — zero trust, no exceptions

**(a) Attach the deny-all policy.** This is already the starting state
after `setup.sh`, but applying it explicitly is fine — it makes the
demo idempotent.

```bash
diagrid apply --project mcp-access-control -f config/phase1-deny-all.yaml
sleep 15   # give Catalyst a few seconds to propagate the policy
```

What you're applying:

```yaml
spec:
  accessControl:
    defaultAction: deny     # nothing else
    trustDomain: public
```

**(b) Run each agent.** Each command runs the agent under its own
Diagrid App ID. Diagrid sees the App ID, looks at `mcp-policy`, and
blocks everything.

```bash
diagrid dev run --project mcp-access-control --app-id ops-agent \
    --yes --skip-default-resiliency -- python3 agents/ops_agent.py
# wait for the "ops-agent summary" line, then Ctrl+C to exit dev run

diagrid dev run --project mcp-access-control --app-id analysis-agent \
    --yes --skip-default-resiliency -- python3 agents/analysis_agent.py
# wait for the summary, Ctrl+C

diagrid dev run --project mcp-access-control --app-id supervisor-agent \
    --yes --skip-default-resiliency -- python3 agents/supervisor_agent.py
# wait for the summary, Ctrl+C
```

> **About the Ctrl+C:** `diagrid dev run` keeps the local-app tunnel
> open even after the Python script exits. Once you see the agent's
> "summary: X allowed   Y denied" line, hit Ctrl+C to close the tunnel
> and move on. Nothing is lost.

**Expected phase-1 output (every agent):**

```
┌─ ops-agent ─ day-to-day operations (read/write, no delete)
│ Inspect the schema before doing any work  (tool: schema)
│   ✗ DENIED  BLOCKED by Diagrid access policy (HTTP 403)
│ Register a new customer  (tool: write)
│   ✗ DENIED  BLOCKED by Diagrid access policy (HTTP 403)
│ Confirm the customer was inserted  (tool: query)
│   ✗ DENIED  BLOCKED by Diagrid access policy (HTTP 403)
│ Try to delete customer id=1  (should be denied)  (tool: delete)
│   ✗ DENIED  BLOCKED by Diagrid access policy (HTTP 403)
└─
ops-agent summary:  0 allowed   4 denied
```

All three agents end with `0 allowed   4 denied`. This is the
*starting* posture of any zero-trust system: assume nothing, allow
nothing.

### Phase 2 — zero trust with explicit per-agent allows

**(a) Apply the per-agent allow rules.** Same `mcp-policy` resource,
new contents.

```bash
diagrid apply --project mcp-access-control -f config/phase2-allow.yaml
sleep 15   # let the new policy propagate
```

What you're applying:

```yaml
spec:
  accessControl:
    defaultAction: deny           # still deny by default
    trustDomain: public
    policies:
      - appId: ops-agent
        defaultAction: deny
        namespace: mcp-access-control
        operations:
          - { name: /write/mcp,  httpVerb: ['POST','GET','DELETE'], action: allow }
          - { name: /schema/mcp, httpVerb: ['POST','GET','DELETE'], action: allow }
          - { name: /query/mcp,  httpVerb: ['POST','GET','DELETE'], action: allow }
      - appId: analysis-agent
        defaultAction: deny
        namespace: mcp-access-control
        operations:
          - { name: /schema/mcp, httpVerb: ['POST','GET','DELETE'], action: allow }
          - { name: /query/mcp,  httpVerb: ['POST','GET','DELETE'], action: allow }
      - appId: supervisor-agent
        defaultAction: deny
        namespace: mcp-access-control
        operations:
          - { name: /write/mcp,  httpVerb: ['POST','GET','DELETE'], action: allow }
          - { name: /schema/mcp, httpVerb: ['POST','GET','DELETE'], action: allow }
          - { name: /query/mcp,  httpVerb: ['POST','GET','DELETE'], action: allow }
          - { name: /delete/mcp, httpVerb: ['POST','GET','DELETE'], action: allow }
```

**(b) Run the same three agent commands as in phase 1.** Same code,
same App IDs — only the policy attached to `mcp-server` has changed.

```bash
diagrid dev run --project mcp-access-control --app-id ops-agent \
    --yes --skip-default-resiliency -- python3 agents/ops_agent.py
# Ctrl+C after the summary

diagrid dev run --project mcp-access-control --app-id analysis-agent \
    --yes --skip-default-resiliency -- python3 agents/analysis_agent.py
# Ctrl+C after the summary

diagrid dev run --project mcp-access-control --app-id supervisor-agent \
    --yes --skip-default-resiliency -- python3 agents/supervisor_agent.py
# Ctrl+C after the summary
```

**Expected phase-2 output:**

```
ops-agent summary:        3 allowed   1 denied   (delete denied)
analysis-agent summary:   2 allowed   2 denied   (write + delete denied)
supervisor-agent summary: 4 allowed   0 denied
```

Same MCP server. Same agents. The only thing that changed is the
**contents** of one Configuration resource.

---

## (Optional) Reset between dry runs

Phase 2's `ops-agent` inserts a row with `email = dana@example.com` and
the `supervisor-agent` inserts `eve@example.com`. Both emails are
`UNIQUE` in the schema, so if you re-run the demo without resetting,
the second run's writes will return a Postgres duplicate-key error
*from inside* an otherwise-ALLOWED tool call. Diagrid still let the
request through; it's just that the row already existed.

Before any repeat run, reset both pieces:

```bash
# 1. policy back to deny-all
diagrid apply --project mcp-access-control -f config/phase1-deny-all.yaml

# 2. database back to the seed data
psql -d zerotrust_demo -f sql/init.sql
```

## (Optional) Inspect Diagrid state live during the demo

```bash
# Show the current mcp-policy contents:
diagrid configuration get mcp-policy --project mcp-access-control --output yaml

# Show which config is attached to mcp-server:
diagrid appid get mcp-server --project mcp-access-control --output yaml | grep appConfig
```

---

## Talking points for the live walk-through

1. **Show the access-policy table.** "ops has no delete. analysis is
   read-only. supervisor has everything."
2. **Start Terminal A** (`diagrid dev run … mcp-server …`). "One process,
   one MCP server, four tools. The server has zero idea who's calling —
   all the access decisions happen one hop earlier, in Diagrid."
3. **Phase 1, apply deny-all** and run all three agents. → Everything is
   `DENIED`. → "Day one of zero trust: nothing works until you write
   down what's allowed."
4. **Show the Phase-2 YAML.** Highlight that each agent gets a tiny
   allow-list of operations. The default is still `deny`. Only the
   `supervisor-agent` block contains `/delete/mcp`.
5. **Phase 2, apply zerotrust** and run the same three agent commands.
   → ops 3/1, analysis 2/2, supervisor 4/0. "Same MCP server. Same
   agents. The only thing that changed was the contents of the
   Configuration attached to the mcp-server App ID."
6. **Inspect live** (optional `diagrid configuration get` / `diagrid
   appid get` commands above).

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `psql: connection refused` | `brew services start postgresql@14` |
| `Error: max number of projects reached` | Reuse an existing project: `export DIAGRID_PROJECT=<your-project>` and rerun `setup.sh` |
| `Error: max number of appids reached` | Delete unused App IDs: `echo Y \| diagrid appid delete <name> --project <project>` |
| Phase 2 keeps denying calls that should pass | Policies need a few seconds to propagate; bump the `sleep 15` to `sleep 30` and retry. |
| `diagrid dev run` hangs after the agent prints its summary | Expected — hit Ctrl+C. The tunnel doesn't close on inner-process exit. |
| `failed to start tunnel … stale session cleanup` | A previous dev-run is still registered: `diagrid dev stop --app-id mcp-server --project mcp-access-control` then retry |
| `address already in use` on port 8000 | `lsof -i :8000`, kill the holder, or set `MCP_PORT=8010` and re-launch |
| Want to start from scratch | Drop the DB (`psql -d postgres -c "DROP DATABASE zerotrust_demo;"`), delete the App IDs (`echo Y \| diagrid appid delete <name> --project mcp-access-control`) and the config (`echo Y \| diagrid configuration delete mcp-policy --project mcp-access-control`), then re-run setup. |

---

## Cleanup

```bash
# Stop any open Catalyst tunnels
diagrid dev stop --app-id mcp-server      --project mcp-access-control
diagrid dev stop --app-id ops-agent       --project mcp-access-control
diagrid dev stop --app-id analysis-agent  --project mcp-access-control
diagrid dev stop --app-id supervisor-agent --project mcp-access-control

# Drop App IDs and the policy
for a in mcp-server ops-agent analysis-agent supervisor-agent; do
    echo Y | diagrid appid delete "$a" --project mcp-access-control
done
echo Y | diagrid configuration delete mcp-policy --project mcp-access-control

# Drop the local DB
psql -d postgres -c "DROP DATABASE IF EXISTS zerotrust_demo;"
```
