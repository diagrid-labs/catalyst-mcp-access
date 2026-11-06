"""MCP server with four tools backed by a local Postgres database.

Each tool is mounted at its own HTTP path so Diagrid can enforce per-tool
access policies via Dapr Configuration's operation-level rules:

    /write/mcp    -> write tool
    /schema/mcp   -> schema tool
    /query/mcp    -> query tool
    /delete/mcp   -> delete tool
"""

import contextlib
import json
import os

import psycopg
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

# Diagrid's tunnel uses a "Host: localhost" header that doesn't match the
# server's listening host, which trips FastMCP's DNS-rebinding protection
# (HTTP 421). Disable it for this demo — Diagrid is already authenticating
# every request via the dapr-api-token plus mTLS, so the extra Host check
# offers nothing on top.
_NO_HOST_CHECK = TransportSecuritySettings(enable_dns_rebinding_protection=False)

PG_USER = os.environ.get("PGUSER") or os.environ.get("USER", "postgres")
PG_DSN = os.environ.get(
    "PG_DSN",
    f"host=localhost port=5432 dbname=zerotrust_demo user={PG_USER}",
)


def _connect():
    return psycopg.connect(PG_DSN)


# ── write tool ───────────────────────────────────────────────────────────────
write_mcp = FastMCP("write-tool", stateless_http=True, transport_security=_NO_HOST_CHECK)


@write_mcp.tool()
def write(table: str, row: dict) -> str:
    """Insert a row into a table. `row` is a dict of column → value."""
    cols = ", ".join(row.keys())
    placeholders = ", ".join(["%s"] * len(row))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING id"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, list(row.values()))
        new_id = cur.fetchone()[0]
        conn.commit()
    return f"inserted into {table}, id={new_id}"


# ── schema tool ──────────────────────────────────────────────────────────────
schema_mcp = FastMCP("schema-tool", stateless_http=True, transport_security=_NO_HOST_CHECK)


@schema_mcp.tool()
def schema() -> str:
    """Return a JSON description of all user tables and their columns."""
    sql = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """
    out: dict = {}
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        for table, col, dtype in cur.fetchall():
            out.setdefault(table, []).append({"column": col, "type": dtype})
    return json.dumps(out, indent=2)


# ── query tool ───────────────────────────────────────────────────────────────
query_mcp = FastMCP("query-tool", stateless_http=True, transport_security=_NO_HOST_CHECK)


@query_mcp.tool()
def query(sql: str) -> str:
    """Run a read-only SQL query and return rows as JSON."""
    if not sql.strip().lower().startswith("select"):
        return "error: query tool only accepts SELECT statements"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return json.dumps(rows, default=str, indent=2)


# ── delete tool ──────────────────────────────────────────────────────────────
delete_mcp = FastMCP("delete-tool", stateless_http=True, transport_security=_NO_HOST_CHECK)


@delete_mcp.tool()
def delete(table: str, row_id: int) -> str:
    """Delete a row from a table by id."""
    sql = f"DELETE FROM {table} WHERE id = %s"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (row_id,))
        deleted = cur.rowcount
        conn.commit()
    return f"deleted {deleted} row(s) from {table} where id={row_id}"


# ── combined lifespan for all mounted FastMCP instances ──────────────────────
@contextlib.asynccontextmanager
async def lifespan(app):
    async with contextlib.AsyncExitStack() as stack:
        for sub in (write_mcp, schema_mcp, query_mcp, delete_mcp):
            await stack.enter_async_context(sub.session_manager.run())
        yield


app = Starlette(
    lifespan=lifespan,
    routes=[
        Mount("/write",  app=write_mcp.streamable_http_app()),
        Mount("/schema", app=schema_mcp.streamable_http_app()),
        Mount("/query",  app=query_mcp.streamable_http_app()),
        Mount("/delete", app=delete_mcp.streamable_http_app()),
    ],
)


if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
