"""analysis-agent — read-only analytics.

Authorized for: schema, query.
Should be denied:  write, delete.
"""

from agent_lib import run_scenario


PLAN = [
    ("schema", "List tables to plan an analysis", {}),
    ("query",  "Top revenue by customer",
        {"sql": (
            "SELECT c.name, SUM(o.amount) AS revenue "
            "FROM customers c JOIN orders o ON o.customer_id = c.id "
            "GROUP BY c.name ORDER BY revenue DESC"
        )}),
    ("write",  "Try to add a 'tampered' row (should be denied)",
        {"table": "customers", "row": {"name": "tamper", "email": "x@x"}}),
    ("delete", "Try to delete a row (should be denied)",
        {"table": "orders", "row_id": 1}),
]


if __name__ == "__main__":
    run_scenario("analysis-agent", "read-only analytics (schema + query only)", PLAN)
