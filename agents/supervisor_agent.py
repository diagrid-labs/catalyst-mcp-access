"""supervisor-agent — full database access including delete.

Authorized for: write, schema, query, delete.
"""

from agent_lib import run_scenario


PLAN = [
    ("schema", "Inspect the schema", {}),
    ("query",  "Find rows worth cleaning up",
        {"sql": "SELECT id, name, email FROM customers WHERE email LIKE '%example.com' ORDER BY id"}),
    ("write",  "Add a flagged-for-review customer",
        {"table": "customers", "row": {"name": "Eve Reviewer", "email": "eve@example.com"}}),
    ("delete", "Delete an order (privileged operation)",
        {"table": "orders", "row_id": 4}),
]


if __name__ == "__main__":
    run_scenario("supervisor-agent", "full access incl. delete", PLAN)
