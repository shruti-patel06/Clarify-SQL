"""Basic safety net: only SELECT statements are ever allowed to run,
since this project touches customer and payment data.
"""
BLOCKED_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "truncate", "grant"]


def is_safe(sql: str) -> bool:
    lowered = sql.strip().lower()
    if not lowered.startswith("select"):
        return False
    return not any(word in lowered for word in BLOCKED_KEYWORDS)
