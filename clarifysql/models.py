from pydantic import BaseModel


class ClarificationOption(BaseModel):
    label: str
    sql_hint: str


class AmbiguityCheck(BaseModel):
    is_ambiguous: bool
    clarification_question: str = ""
    options: list[ClarificationOption] = []


class SQLResult(BaseModel):
    sql: str
    explanation: str
