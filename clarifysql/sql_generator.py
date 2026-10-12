"""Turns a natural language question (already clarified, if it needed to be)
into a SQL query by asking an LLM and parsing its answer into a fixed
structure with Pydantic.
"""
import json

from groq import Groq

from clarifysql.config import GROQ_API_KEY, GROQ_MODEL
from clarifysql.models import SQLResult

client = Groq(api_key=GROQ_API_KEY)

SCHEMA_DESCRIPTION = """
Table: customers(customer_id, name, email, city, signup_date)
Table: orders(order_id, customer_id, order_date, status)   -- status is 'completed' or 'cancelled'
Table: payments(payment_id, order_id, amount, payment_date)

orders.customer_id references customers.customer_id
payments.order_id references orders.order_id
"""

SYSTEM_PROMPT = f"""You are a SQL assistant for a PostgreSQL database with this schema:
{SCHEMA_DESCRIPTION}

Write exactly one SELECT query that answers the user's question.
Only use SELECT. Never write INSERT, UPDATE, DELETE, DROP or ALTER.
Exclude orders with status = 'cancelled' unless the question says otherwise.

Respond with ONLY valid JSON in this exact shape, nothing else:
{{"sql": "<the SQL query as one line>", "explanation": "<one short sentence>"}}
"""


def generate_sql(question: str) -> SQLResult:
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return SQLResult(**data)
