"""Schema description shared by every prompt that needs to know what the
database looks like (SQL generation and ambiguity detection).
"""
SCHEMA_DESCRIPTION = """
Table: customers(customer_id, name, email, city, signup_date)
Table: orders(order_id, customer_id, order_date, status)   -- status is 'completed' or 'cancelled'
Table: payments(payment_id, order_id, amount, payment_date)

orders.customer_id references customers.customer_id
payments.order_id references orders.order_id
"""
