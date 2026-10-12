"""Turns a natural language question (already clarified, if it needed to be)
into a SQL query by asking an LLM and parsing its answer into a fixed
structure with Pydantic.

Every generated query is checked before it is returned: first by the
safety validator, then by asking Postgres to EXPLAIN it, which catches
wrong column names, bad joins and syntax errors without running anything.
If a check fails, the error is sent back to the LLM as a follow-up message
and it gets another try (the self-correction loop).
"""
import json

from groq import BadRequestError
from pydantic import ValidationError

from clarifysql.db import explain_error
from clarifysql.llm import chat_json
from clarifysql.models import Attempt, SQLResult
from clarifysql.schema import SCHEMA_DESCRIPTION
from clarifysql.validator import safety_error

MAX_RETRIES = 2

SYSTEM_PROMPT = f"""You are a SQL assistant for a PostgreSQL database with this schema:
{SCHEMA_DESCRIPTION}

Write exactly one SELECT query that answers the user's question.
Only use SELECT. Never write INSERT, UPDATE, DELETE, DROP or ALTER.
Exclude orders with status = 'cancelled' unless the question says otherwise.

Respond with ONLY valid JSON in this exact shape, nothing else:
{{"sql": "<the SQL query as one line>", "explanation": "<one short sentence>"}}
"""


def find_problem(sql: str):
    """None if the query is safe and valid, otherwise a description of what's wrong."""
    return safety_error(sql) or explain_error(sql)


def generate_sql(question: str, max_retries: int = MAX_RETRIES) -> SQLResult:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    failed_attempts = []

    for _ in range(max_retries + 1):
        reply = None
        try:
            reply = chat_json(messages)
            result = SQLResult(sql=reply["sql"], explanation=reply.get("explanation", ""))
            problem = find_problem(result.sql)
        except (BadRequestError, json.JSONDecodeError, ValidationError, KeyError, TypeError, AttributeError):
            # Groq rejects output that isn't valid JSON with a BadRequestError;
            # the others cover JSON that is missing "sql" or has the wrong types.
            result = SQLResult(sql="", explanation="")
            problem = 'The response was not JSON of the form {"sql": ..., "explanation": ...}.'

        if problem is None:
            return result.model_copy(update={"failed_attempts": failed_attempts})

        failed_attempts.append(Attempt(sql=result.sql, error=problem))
        # Show the model its own answer and the error, the way a person
        # would paste a stack trace back into a chat.
        messages.append({"role": "assistant", "content": json.dumps(reply) if reply else "(invalid response)"})
        messages.append({
            "role": "user",
            "content": f"That query failed with this error:\n{problem}\n"
                       "Fix the query and respond with the same JSON shape.",
        })

    last = failed_attempts.pop()
    return SQLResult(sql=last.sql, explanation="", failed_attempts=failed_attempts, error=last.error)
