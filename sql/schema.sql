-- Run this once against a fresh database to create the tables.
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id  SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    email        VARCHAR(100) UNIQUE NOT NULL,
    city         VARCHAR(50),
    signup_date  DATE NOT NULL
);

CREATE TABLE orders (
    order_id     SERIAL PRIMARY KEY,
    customer_id  INTEGER REFERENCES customers(customer_id),
    order_date   DATE NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'completed'  -- completed or cancelled
);

CREATE TABLE payments (
    payment_id    SERIAL PRIMARY KEY,
    order_id      INTEGER REFERENCES orders(order_id),
    amount        NUMERIC(10, 2) NOT NULL,
    payment_date  DATE NOT NULL
);
