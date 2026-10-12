"""Command line entry point. Ask a question in plain English, get asked to
clarify if the question is ambiguous, then see the SQL and its results.
"""
from clarifysql.ambiguity_checker import check_ambiguity
from clarifysql.db import run_query
from clarifysql.sql_generator import generate_sql
from clarifysql.validator import is_safe


def ask_for_clarification(check):
    print(f"\n{check.clarification_question}")
    for i, option in enumerate(check.options, start=1):
        print(f"  {i}. {option.label}")
    choice = input("Pick a number: ").strip()
    index = int(choice) - 1
    return check.options[index]


def main():
    print("Ask a question about customers, orders or payments. Type 'quit' to exit.\n")
    while True:
        question = input("> ").strip()
        if question.lower() in ("quit", "exit"):
            break
        if not question:
            continue

        check = check_ambiguity(question)
        if check.is_ambiguous:
            chosen = ask_for_clarification(check)
            question = f"{question} (use this definition: {chosen.label} — {chosen.sql_hint})"

        result = generate_sql(question)
        print(f"\nSQL: {result.sql}")
        print(f"Why: {result.explanation}")

        if not is_safe(result.sql):
            print("This query was blocked — it is not a plain SELECT statement.\n")
            continue

        confirm = input("Run this query? (y/n): ").strip().lower()
        if confirm == "y":
            columns, rows = run_query(result.sql)
            print(" | ".join(columns))
            for row in rows:
                print(" | ".join(str(value) for value in row))
        print()


if __name__ == "__main__":
    main()
