"""Basic safety net: only a single SELECT statement is ever allowed to run,
since this project touches customer and payment data.
"""
import re

# \b = word boundary, so a column like "updated_at" or the word "deleted"
# no longer trips the check the way a plain substring search did.
BLOCKED_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|copy)\b",
    re.IGNORECASE,
)


def safety_error(sql: str):
    """Returns None if the query is allowed, otherwise the reason it isn't."""
    statement = sql.strip().rstrip(";").strip()
    first_word = statement.split(maxsplit=1)[0].lower() if statement else ""
    if first_word not in ("select", "with"):
        return "Only SELECT queries are allowed."
    if ";" in statement:
        return "Only a single statement is allowed."
    match = BLOCKED_KEYWORDS.search(statement)
    if match:
        return f"The keyword {match.group(0).upper()} is not allowed."
    return None


def is_safe(sql: str) -> bool:
    return safety_error(sql) is None
