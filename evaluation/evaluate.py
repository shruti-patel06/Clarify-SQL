"""Measures the effect of the clarification step on accuracy.

For each ambiguous test question, we already know which aggregate function
(SUM for revenue, COUNT for order count) a correct query must use. We run
every question twice: once letting the model guess on its own, and once
after supplying the clarification a user would have given. Comparing how
many queries used the right aggregate each time gives a concrete
before/after accuracy number.
"""
from clarifysql.sql_generator import generate_sql

TEST_QUESTIONS = [
    # Unambiguous questions the model should get right either way.
    {"question": "List all customers who signed up in the last 6 months", "expects": "signup_date", "clarification": None},
    {"question": "Show total revenue collected last week", "expects": "SUM", "clarification": None},
    {"question": "How many orders were cancelled?", "expects": "cancelled", "clarification": None},
    {"question": "List customers from Mumbai", "expects": "city", "clarification": None},
    {"question": "Show the number of orders placed by each customer", "expects": "COUNT", "clarification": None},

    # Ambiguous questions — "expects" is the aggregate a correct answer needs.
    {"question": "Who is our best customer?", "expects": "SUM", "clarification": "use this definition: Total money spent (revenue) — rank by SUM(payments.amount)"},
    {"question": "Show me the top customer this year", "expects": "SUM", "clarification": "use this definition: Total money spent (revenue) — rank by SUM(payments.amount)"},
    {"question": "Which customer orders the most?", "expects": "COUNT", "clarification": "use this definition: Number of orders placed — rank by COUNT(orders.order_id)"},
    {"question": "Give me the top 3 customers by number of orders", "expects": "COUNT", "clarification": "use this definition: Number of orders placed — rank by COUNT(orders.order_id)"},
    {"question": "Show revenue from recent orders", "expects": "30 days", "clarification": "use this definition: Last 30 days from today — order_date >= CURRENT_DATE - INTERVAL '30 days'"},
]


def contains_expected(sql, expects):
    return expects.lower() in sql.lower()


def run_pass(use_clarification):
    correct = 0
    for item in TEST_QUESTIONS:
        question = item["question"]
        if use_clarification and item["clarification"]:
            question = f"{question} ({item['clarification']})"
        result = generate_sql(question)
        if contains_expected(result.sql, item["expects"]):
            correct += 1
    return correct, len(TEST_QUESTIONS)


if __name__ == "__main__":
    baseline_correct, total = run_pass(use_clarification=False)
    clarified_correct, _ = run_pass(use_clarification=True)

    print(f"Without clarification: {baseline_correct}/{total} correct "
          f"({baseline_correct / total * 100:.0f}%)")
    print(f"With clarification:    {clarified_correct}/{total} correct "
          f"({clarified_correct / total * 100:.0f}%)")
