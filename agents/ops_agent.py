"""ops-agent — handles day-to-day database operations.

Authorized for: write, schema, query.
Should be denied:  delete  (only the supervisor can delete).
"""

from agent_lib import run_scenario


PLAN = [
    ("schema", "Inspect the schema before doing any work", {}),
    ("write",  "Register a new customer",
        {"table": "customers", "row": {"name": "Dana Wright", "email": "dana@example.com"}}),
    ("query",  "Confirm the customer was inserted",
        {"sql": "SELECT id, name, email FROM customers ORDER BY id DESC LIMIT 3"}),
    ("delete", "Try to delete customer id=1  (should be denied)",
        {"table": "customers", "row_id": 1}),
]


if __name__ == "__main__":
    run_scenario("ops-agent", "day-to-day operations (read/write, no delete)", PLAN)
