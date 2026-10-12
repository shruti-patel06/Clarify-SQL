"""Checks whether a question contains a word that could mean different
things (e.g. "best" could mean highest revenue or most orders). This is a
plain keyword lookup, not an LLM call, so it is fast and predictable.
"""
from clarifysql.models import AmbiguityCheck, ClarificationOption

AMBIGUOUS_TERMS = {
    "best": AmbiguityCheck(
        is_ambiguous=True,
        clarification_question="When you say 'best customer', what should that be based on?",
        options=[
            ClarificationOption(
                label="Total money spent (revenue)",
                sql_hint="rank by SUM(payments.amount)",
            ),
            ClarificationOption(
                label="Number of orders placed",
                sql_hint="rank by COUNT(orders.order_id)",
            ),
        ],
    ),
    "top": AmbiguityCheck(
        is_ambiguous=True,
        clarification_question="'Top' by what measure — revenue or number of orders?",
        options=[
            ClarificationOption(
                label="Total money spent (revenue)",
                sql_hint="rank by SUM(payments.amount)",
            ),
            ClarificationOption(
                label="Number of orders placed",
                sql_hint="rank by COUNT(orders.order_id)",
            ),
        ],
    ),
    "recent": AmbiguityCheck(
        is_ambiguous=True,
        clarification_question="By 'recent', do you mean the last calendar month or the last 30 days?",
        options=[
            ClarificationOption(
                label="Last calendar month",
                sql_hint="order_date >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month') "
                "AND order_date < date_trunc('month', CURRENT_DATE)",
            ),
            ClarificationOption(
                label="Last 30 days from today",
                sql_hint="order_date >= CURRENT_DATE - INTERVAL '30 days'",
            ),
        ],
    ),
}


def check_ambiguity(question: str) -> AmbiguityCheck:
    lowered = question.lower()
    for term, verdict in AMBIGUOUS_TERMS.items():
        if term in lowered:
            return verdict
    return AmbiguityCheck(is_ambiguous=False)
