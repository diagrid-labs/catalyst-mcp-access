-- Demo database for the Diagrid zero-trust MCP demo.
-- Creates two small tables that the agents will read/write/delete.

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id      SERIAL PRIMARY KEY,
    name    TEXT NOT NULL,
    email   TEXT NOT NULL UNIQUE,
    created TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    id          SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    item        TEXT NOT NULL,
    amount      NUMERIC(10,2) NOT NULL,
    created     TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO customers (name, email) VALUES
    ('Alice Chen',    'alice@example.com'),
    ('Bob Martinez',  'bob@example.com'),
    ('Carol Singh',   'carol@example.com');

INSERT INTO orders (customer_id, item, amount) VALUES
    (1, 'Pro Plan',     99.00),
    (1, 'Add-on Seats', 49.50),
    (2, 'Starter Plan', 19.00),
    (3, 'Pro Plan',     99.00);
