"""The evaluation benchmark: questions paired with a hand-written "gold"
SQL query that returns the correct answer.

Unambiguous items only need a gold query. Ambiguous items also have:
- intent:    what the person asking actually meant, in plain words. The
             simulated user in evaluate.py reads this to answer the
             clarification question; it is never shown to the SQL generator.
- other_sql: the competing reading. `python -m evaluation.evaluate --check`
             runs both and confirms they return different results, which
             proves the question really is ambiguous on this data.

Intents deliberately alternate (some "best" questions mean revenue, some
mean order count), the way different real users would. A system that
always guesses the same reading can't score well on them.

Rules every gold query follows:
- cancelled orders are excluded unless the question asks about them (the
  same rule the SQL generator's prompt uses);
- select only the columns that answer the question; extra columns in a
  prediction are allowed, missing ones are not;
- no questions whose answer is a tie, so there is exactly one right answer.
"""

PAID = ("FROM customers c JOIN orders o ON o.customer_id = c.customer_id "
        "JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'")
ORDERED = "FROM customers c JOIN orders o ON o.customer_id = c.customer_id WHERE o.status = 'completed'"


def top_by_revenue(n, column="c.name", desc=True):
    direction = "DESC" if desc else "ASC"
    return f"SELECT {column} {PAID} GROUP BY c.customer_id ORDER BY SUM(p.amount) {direction} LIMIT {n}"


def top_by_orders(n, column="c.name", desc=True):
    direction = "DESC" if desc else "ASC"
    return f"SELECT {column} {ORDERED} GROUP BY c.customer_id ORDER BY COUNT(*) {direction} LIMIT {n}"


LAST_CALENDAR_MONTH = ("o.order_date >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month') "
                       "AND o.order_date < date_trunc('month', CURRENT_DATE)")
LAST_30_DAYS = "o.order_date >= CURRENT_DATE - INTERVAL '30 days'"
REVENUE_TOTAL = f"SELECT SUM(p.amount) {PAID}"
COMPLETED_COUNT = "SELECT COUNT(*) FROM orders o WHERE o.status = 'completed'"
AVG_PER_ORDER = ("SELECT AVG(p.amount) FROM orders o JOIN payments p ON p.order_id = o.order_id "
                 "WHERE o.status = 'completed'")
AVG_PER_CUSTOMER = ("SELECT AVG(total) FROM (SELECT SUM(p.amount) AS total FROM orders o "
                    "JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' "
                    "GROUP BY o.customer_id) t")


def active_customers(days, column="COUNT(DISTINCT c.customer_id)"):
    return f"SELECT {column} {ORDERED} AND o.order_date >= CURRENT_DATE - INTERVAL '{days} days'"


def inactive_customers(days):
    return ("SELECT COUNT(*) FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o "
            "WHERE o.customer_id = c.customer_id AND o.status = 'completed' "
            f"AND o.order_date >= CURRENT_DATE - INTERVAL '{days} days')")


REVENUE_INTENT = "rank customers by the total money they have spent"
ORDERS_INTENT = "rank customers by how many orders they have placed"

UNAMBIGUOUS = [
    {"question": "How many customers are there?",
     "gold_sql": "SELECT COUNT(*) FROM customers"},
    {"question": "How many orders were cancelled?",
     "gold_sql": "SELECT COUNT(*) FROM orders WHERE status = 'cancelled'"},
    {"question": "How many completed orders are there?",
     "gold_sql": COMPLETED_COUNT},
    {"question": "What is the total revenue from completed orders?",
     "gold_sql": REVENUE_TOTAL},
    {"question": "Which customer has placed the most completed orders?",
     "gold_sql": top_by_orders(1)},
    {"question": "Which customer has spent the most money in total?",
     "gold_sql": top_by_revenue(1)},
    # The next four contain "top" or "recent", so the keyword detector
    # flags them, but the wording already settles the meaning.
    {"question": "Show the top 3 customers by total amount spent.",
     "gold_sql": top_by_revenue(3)},
    {"question": "Give me the top customer by number of orders.",
     "gold_sql": top_by_orders(1)},
    {"question": "List the dates of the 5 most recent completed orders.",
     "gold_sql": "SELECT order_date FROM orders WHERE status = 'completed' ORDER BY order_date DESC LIMIT 5"},
    {"question": "What is the name of the customer who signed up most recently?",
     "gold_sql": "SELECT name FROM customers ORDER BY signup_date DESC LIMIT 1"},
    {"question": "What is the average payment amount for completed orders?",
     "gold_sql": AVG_PER_ORDER},
    {"question": "How many orders are there with each status?",
     "gold_sql": "SELECT status, COUNT(*) FROM orders GROUP BY status"},
    {"question": "How many customers signed up in 2025?",
     "gold_sql": "SELECT COUNT(*) FROM customers WHERE EXTRACT(YEAR FROM signup_date) = 2025"},
    {"question": "List the names of customers who signed up before 2025.",
     "gold_sql": "SELECT name FROM customers WHERE signup_date < '2025-01-01'"},
    {"question": "How much revenue came from completed orders placed in the last 7 days?",
     "gold_sql": f"{REVENUE_TOTAL} AND o.order_date >= CURRENT_DATE - INTERVAL '7 days'"},
    {"question": "How many completed orders were placed in each calendar month? Sort by month.",
     "gold_sql": ("SELECT COUNT(*) FROM orders WHERE status = 'completed' "
                  "GROUP BY date_trunc('month', order_date) ORDER BY date_trunc('month', order_date)")},
    {"question": "Among customers with at least one completed order, what is the average number of completed orders per customer?",
     "gold_sql": ("SELECT AVG(n) FROM (SELECT COUNT(*) AS n FROM orders "
                  "WHERE status = 'completed' GROUP BY customer_id) t")},
    {"question": "Which city does the customer with the most completed orders live in?",
     "gold_sql": top_by_orders(1, column="c.city")},
    {"question": "What is the email of the customer who has spent the most?",
     "gold_sql": top_by_revenue(1, column="c.email")},
    {"question": "How many payments over 500 were made for completed orders?",
     "gold_sql": f"SELECT COUNT(*) {PAID} AND p.amount > 500"},
    {"question": "What is the largest single payment amount for a completed order?",
     "gold_sql": f"SELECT MAX(p.amount) {PAID}"},
    {"question": "List each customer's name with their number of completed orders, for customers who have at least one.",
     "gold_sql": f"SELECT c.name, COUNT(*) {ORDERED} GROUP BY c.customer_id, c.name"},
    {"question": "How many distinct customers placed a completed order in the last 30 days?",
     "gold_sql": active_customers(30)},
    {"question": "How many customers have placed more than 5 completed orders?",
     "gold_sql": ("SELECT COUNT(*) FROM (SELECT customer_id FROM orders WHERE status = 'completed' "
                  "GROUP BY customer_id HAVING COUNT(*) > 5) t")},
    {"question": "What is the total amount paid by the customer with the most completed orders?",
     "gold_sql": (f"SELECT SUM(p.amount) {PAID} AND c.customer_id = "
                  f"({top_by_orders(1, column='c.customer_id')})")},
    {"question": "How many completed orders has the highest-spending customer placed?",
     "gold_sql": (f"SELECT COUNT(*) {ORDERED} AND c.customer_id = "
                  f"({top_by_revenue(1, column='c.customer_id')})")},
    {"question": "Show the total amount spent by each of the 5 highest-spending customers.",
     "gold_sql": top_by_revenue(5, column="SUM(p.amount)")},
    {"question": "How many completed orders were paid more than 2 days after the order date?",
     "gold_sql": f"SELECT COUNT(*) {PAID} AND p.payment_date - o.order_date > 2"},
    {"question": "What is the earliest signup date of any customer?",
     "gold_sql": "SELECT MIN(signup_date) FROM customers"},
    {"question": "What is the city of the customer who signed up first?",
     "gold_sql": "SELECT city FROM customers ORDER BY signup_date LIMIT 1"},
]

AMBIGUOUS = [
    # Ranking word with no metric: revenue or number of orders?
    {"question": "Who is our best customer?", "intent": REVENUE_INTENT,
     "gold_sql": top_by_revenue(1), "other_sql": top_by_orders(1)},
    {"question": "Who is our top customer?", "intent": ORDERS_INTENT,
     "gold_sql": top_by_orders(1), "other_sql": top_by_revenue(1)},
    {"question": "Who is our biggest customer?", "intent": ORDERS_INTENT,
     "gold_sql": top_by_orders(1), "other_sql": top_by_revenue(1)},
    {"question": "Name our star customer.", "intent": REVENUE_INTENT,
     "gold_sql": top_by_revenue(1), "other_sql": top_by_orders(1)},
    {"question": "Which customer is the most important to us?", "intent": ORDERS_INTENT,
     "gold_sql": top_by_orders(1), "other_sql": top_by_revenue(1)},
    {"question": "Who is our number one customer?", "intent": REVENUE_INTENT,
     "gold_sql": top_by_revenue(1), "other_sql": top_by_orders(1)},
    {"question": "Show me our top 3 customers.", "intent": REVENUE_INTENT,
     "gold_sql": top_by_revenue(3), "other_sql": top_by_orders(3)},
    {"question": "Which customer leads the pack?", "intent": ORDERS_INTENT,
     "gold_sql": top_by_orders(1), "other_sql": top_by_revenue(1)},
    {"question": "Who is our leading customer?", "intent": REVENUE_INTENT,
     "gold_sql": top_by_revenue(1), "other_sql": top_by_orders(1)},
    {"question": "Which customer brings in the most business?", "intent": ORDERS_INTENT,
     "gold_sql": top_by_orders(1), "other_sql": top_by_revenue(1)},
    {"question": "Who is our worst customer?", "intent": "the customer who has spent the least money",
     "gold_sql": top_by_revenue(1, desc=False), "other_sql": top_by_orders(1, desc=False)},

    # Vague time window: last calendar month or last 30 days?
    {"question": "How much revenue did we make recently?", "intent": "orders placed in the last 30 days",
     "gold_sql": f"{REVENUE_TOTAL} AND {LAST_30_DAYS}",
     "other_sql": f"{REVENUE_TOTAL} AND {LAST_CALENDAR_MONTH}"},
    {"question": "How many orders were placed recently?", "intent": "orders placed in the previous calendar month",
     "gold_sql": f"{COMPLETED_COUNT} AND {LAST_CALENDAR_MONTH}",
     "other_sql": f"{COMPLETED_COUNT} AND {LAST_30_DAYS}"},
    {"question": "Which customers ordered lately?", "intent": "customers with an order in the last 30 days",
     "gold_sql": f"SELECT DISTINCT c.name {ORDERED} AND {LAST_30_DAYS}",
     "other_sql": f"SELECT DISTINCT c.name {ORDERED} AND {LAST_CALENDAR_MONTH}"},
    {"question": "What was our revenue over the past month?", "intent": "the previous calendar month",
     "gold_sql": f"{REVENUE_TOTAL} AND {LAST_CALENDAR_MONTH}",
     "other_sql": f"{REVENUE_TOTAL} AND {LAST_30_DAYS}"},
    {"question": "How many orders came in over the last month?", "intent": "the last 30 days up to today",
     "gold_sql": f"{COMPLETED_COUNT} AND {LAST_30_DAYS}",
     "other_sql": f"{COMPLETED_COUNT} AND {LAST_CALENDAR_MONTH}"},
    {"question": "How many customers ordered in the past month?", "intent": "the last 30 days up to today",
     "gold_sql": f"SELECT COUNT(DISTINCT c.customer_id) {ORDERED} AND {LAST_30_DAYS}",
     "other_sql": f"SELECT COUNT(DISTINCT c.customer_id) {ORDERED} AND {LAST_CALENDAR_MONTH}"},

    # "Active" customer: ordered in the last 30 days, or the last 90?
    {"question": "How many active customers do we have?",
     "intent": "customers with a completed order in the last 30 days",
     "gold_sql": active_customers(30), "other_sql": active_customers(90)},
    {"question": "List our active customers.",
     "intent": "customers with a completed order in the last 90 days",
     "gold_sql": active_customers(90, column="DISTINCT c.name"),
     "other_sql": active_customers(30, column="DISTINCT c.name")},
    {"question": "How many inactive customers do we have?",
     "intent": "customers with no completed order in the last 30 days",
     "gold_sql": inactive_customers(30), "other_sql": inactive_customers(90)},

    # "New" customer: signed up in the last 6 months, or this calendar year?
    {"question": "How many new customers do we have?", "intent": "customers who signed up in the last 6 months",
     "gold_sql": "SELECT COUNT(*) FROM customers WHERE signup_date >= CURRENT_DATE - INTERVAL '6 months'",
     "other_sql": "SELECT COUNT(*) FROM customers WHERE signup_date >= date_trunc('year', CURRENT_DATE)"},
    {"question": "List our new customers.", "intent": "customers who signed up this calendar year",
     "gold_sql": "SELECT name FROM customers WHERE signup_date >= date_trunc('year', CURRENT_DATE)",
     "other_sql": "SELECT name FROM customers WHERE signup_date >= CURRENT_DATE - INTERVAL '6 months'"},

    # Average spend: per order, or per customer?
    {"question": "What's the average spend?", "intent": "the average total spent per customer",
     "gold_sql": AVG_PER_CUSTOMER, "other_sql": AVG_PER_ORDER},
    {"question": "How much is spent on average?", "intent": "the average amount paid per order",
     "gold_sql": AVG_PER_ORDER, "other_sql": AVG_PER_CUSTOMER},

    # "Loyal": most orders, or longest-standing?
    {"question": "Who is our most loyal customer?", "intent": ORDERS_INTENT,
     "gold_sql": top_by_orders(1),
     "other_sql": "SELECT name FROM customers ORDER BY signup_date LIMIT 1"},
    {"question": "List our 3 most loyal customers.", "intent": "the customers who signed up earliest",
     "gold_sql": "SELECT name FROM customers ORDER BY signup_date LIMIT 3",
     "other_sql": top_by_orders(3)},

    # "Sales": money, or number of orders?
    {"question": "What were our total sales last week?",
     "intent": "the number of completed orders in the last 7 days",
     "gold_sql": f"{COMPLETED_COUNT} AND o.order_date >= CURRENT_DATE - INTERVAL '7 days'",
     "other_sql": f"{REVENUE_TOTAL} AND o.order_date >= CURRENT_DATE - INTERVAL '7 days'"},
    {"question": "Show total sales.", "intent": "the total money collected",
     "gold_sql": REVENUE_TOTAL, "other_sql": COMPLETED_COUNT},
]

BENCHMARK = UNAMBIGUOUS + AMBIGUOUS
