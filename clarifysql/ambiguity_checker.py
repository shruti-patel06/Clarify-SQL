"""Decides whether a question could mean different things (e.g. "best
customer" could mean highest revenue or most orders) before any SQL is
written.

Two detectors are combined ("hybrid" mode):

- keyword_check: a hand-written list of known vague words. Instant, free
  and predictable, with clarification options written by hand. But it only
  knows the words on the list, and it can't read context: it flags "top 3
  customers by number of orders" even though the metric is stated.
- llm_check: asks the LLM to judge the question in context. It catches
  vague wording the list has never seen ("biggest", "lately", "active"),
  and it can tell when the question already settles the ambiguity.

In hybrid mode the LLM decides whether to ask, and if the keyword list
also matched, its hand-written options are shown instead of the LLM's
(same meaning, but deterministic wording). If the LLM call fails, the
keyword verdict is used so the app still works.
"""
import re

from groq import GroqError

from clarifysql.llm import chat_json
from clarifysql.models import AmbiguityCheck, ClarificationOption
from clarifysql.schema import SCHEMA_DESCRIPTION

NOT_AMBIGUOUS = AmbiguityCheck(is_ambiguous=False)

REVENUE_OR_ORDERS = [
    ClarificationOption(label="Total money spent (revenue)", sql_hint="rank by SUM(payments.amount)"),
    ClarificationOption(label="Number of orders placed", sql_hint="rank by COUNT(orders.order_id)"),
]

# Regex -> verdict. \b (word boundary) stops "top" matching "stop" or
# "laptop", which a plain `"top" in question` check would.
KEYWORD_RULES = {
    r"\bbest\b": AmbiguityCheck(
        is_ambiguous=True,
        clarification_question="When you say 'best', what should customers be ranked by?",
        options=REVENUE_OR_ORDERS,
        source="keyword",
    ),
    r"\btop\b": AmbiguityCheck(
        is_ambiguous=True,
        clarification_question="'Top' by what measure — revenue or number of orders?",
        options=REVENUE_OR_ORDERS,
        source="keyword",
    ),
    r"\brecent(ly)?\b": AmbiguityCheck(
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
        source="keyword",
    ),
}

LLM_PROMPT = f"""You review questions about a PostgreSQL database before SQL is written for them.
Schema:
{SCHEMA_DESCRIPTION}
Cancelled orders are always excluded unless the question says otherwise; that is a fixed rule, not an ambiguity.

A question is ambiguous only if two reasonable readings would return DIFFERENT results. Typical cases:
- a ranking word (best, top, biggest, ...) with no metric, when customers could be ranked by revenue or by number of orders
- a vague time window (recent, lately, past month, ...) with no exact period
- a business term with more than one reasonable definition in this schema (e.g. "active customer")
If the question already states the metric or period, or only one reading makes sense, it is NOT ambiguous.
Never ask about formatting, which columns to show, or how to break ties.

Respond with ONLY JSON in this shape:
{{"is_ambiguous": true or false,
  "clarification_question": "<one short question for the user, or empty>",
  "options": [{{"label": "<short plain-English choice>", "sql_hint": "<how that choice is written in SQL>"}}]}}
Give 2 or 3 options when ambiguous, otherwise an empty list.
"""


def keyword_check(question: str) -> AmbiguityCheck:
    for pattern, verdict in KEYWORD_RULES.items():
        if re.search(pattern, question, re.IGNORECASE):
            return verdict
    return NOT_AMBIGUOUS


def llm_check(question: str) -> AmbiguityCheck:
    reply = chat_json([
        {"role": "system", "content": LLM_PROMPT},
        {"role": "user", "content": question},
    ])
    verdict = AmbiguityCheck.model_validate({**reply, "source": "llm"})
    # "Ambiguous" with fewer than two options gives the user nothing to pick.
    if not verdict.is_ambiguous or len(verdict.options) < 2:
        return NOT_AMBIGUOUS
    return verdict


def combine(keyword: AmbiguityCheck, llm: AmbiguityCheck) -> AmbiguityCheck:
    if not llm.is_ambiguous:
        return NOT_AMBIGUOUS
    return keyword if keyword.is_ambiguous else llm


def check_ambiguity(question: str, mode: str = "hybrid") -> AmbiguityCheck:
    keyword = keyword_check(question)
    if mode == "keyword":
        return keyword
    try:
        llm = llm_check(question)
    except (GroqError, ValueError, TypeError):  # API down, or a reply that isn't valid JSON / doesn't fit the model
        return keyword
    return combine(keyword, llm)


def apply_clarification(question: str, option: ClarificationOption) -> str:
    """Folds the user's choice into the question that is sent to the SQL generator."""
    return f"{question} (use this definition: {option.label} — {option.sql_hint})"
