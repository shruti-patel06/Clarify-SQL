"""Fills the database with fake customers, orders and payments so there is
something to query. Run this once after creating the tables:
    python -m scripts.seed_data
"""
import random
from datetime import timedelta

from faker import Faker

from clarifysql.db import get_connection

fake = Faker()
random.seed(42)
Faker.seed(42)

NUM_CUSTOMERS = 25


def seed():
    conn = get_connection()
    cur = conn.cursor()

    customer_ids = []
    for _ in range(NUM_CUSTOMERS):
        signup_date = fake.date_between(start_date="-2y", end_date="-3M")
        cur.execute(
            "INSERT INTO customers (name, email, city, signup_date) "
            "VALUES (%s, %s, %s, %s) RETURNING customer_id",
            (fake.name(), fake.unique.email(), fake.city(), signup_date),
        )
        customer_ids.append(cur.fetchone()[0])

    # Two customers are made deliberately "ambiguous winners":
    # one has the highest total revenue, another has the most orders,
    # so "best customer" genuinely depends on how you define "best".
    high_revenue_customer = customer_ids[0]
    high_frequency_customer = customer_ids[1]

    for customer_id in customer_ids:
        if customer_id == high_revenue_customer:
            num_orders = random.randint(3, 5)
        elif customer_id == high_frequency_customer:
            num_orders = random.randint(15, 20)
        else:
            num_orders = random.randint(1, 8)

        for _ in range(num_orders):
            order_date = fake.date_between(start_date="-90d", end_date="today")
            status = random.choices(["completed", "cancelled"], weights=[9, 1])[0]
            cur.execute(
                "INSERT INTO orders (customer_id, order_date, status) "
                "VALUES (%s, %s, %s) RETURNING order_id",
                (customer_id, order_date, status),
            )
            order_id = cur.fetchone()[0]

            if customer_id == high_revenue_customer:
                amount = round(random.uniform(500, 1200), 2)
            elif customer_id == high_frequency_customer:
                amount = round(random.uniform(10, 40), 2)
            else:
                amount = round(random.uniform(20, 300), 2)

            payment_date = order_date + timedelta(days=random.randint(0, 3))
            cur.execute(
                "INSERT INTO payments (order_id, amount, payment_date) "
                "VALUES (%s, %s, %s)",
                (order_id, amount, payment_date),
            )

    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded {NUM_CUSTOMERS} customers with orders and payments.")


if __name__ == "__main__":
    seed()
