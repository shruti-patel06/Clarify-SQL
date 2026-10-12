from pydantic import BaseModel


class ClarificationOption(BaseModel):
    label: str
    sql_hint: str


class AmbiguityCheck(BaseModel):
    is_ambiguous: bool
    clarification_question: str = ""
    options: list[ClarificationOption] = []
    source: str = "none"  # which detector produced the verdict: "keyword", "llm" or "none"


class Attempt(BaseModel):
    """A generated query that was rejected, and why."""
    sql: str
    error: str


class SQLResult(BaseModel):
    sql: str
    explanation: str
    failed_attempts: list[Attempt] = []  # earlier tries the self-correction loop fixed
    error: str = ""  # set only if every attempt failed

    @property
    def ok(self) -> bool:
        return not self.error
