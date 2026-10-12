"""Command line entry point. Ask a question in plain English, get asked to
clarify if the question is ambiguous, then see the SQL and its results.
"""
from groq import GroqError

from clarifysql.ambiguity_checker import apply_clarification, check_ambiguity
from clarifysql.db import run_query
from clarifysql.sql_generator import generate_sql


def ask_for_clarification(check):
    print(f"\n{check.clarification_question}")
    for i, option in enumerate(check.options, start=1):
        print(f"  {i}. {option.label}")
    while True:
        choice = input("Pick a number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(check.options):
            return check.options[int(choice) - 1]
        print(f"Please enter a number from 1 to {len(check.options)}.")


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
            question = apply_clarification(question, ask_for_clarification(check))

        try:
            result = generate_sql(question)
        except GroqError as e:
            print(f"\nThe LLM service is busy or unreachable, please try again. ({type(e).__name__})\n")
            continue
        for attempt in result.failed_attempts:
            print(f"\n(Retried after an error: {attempt.error.splitlines()[0]})")
        if not result.ok:
            print(f"\nCould not produce a valid query: {result.error}\n")
            continue

        print(f"\nSQL: {result.sql}")
        print(f"Why: {result.explanation}")
        confirm = input("Run this query? (y/n): ").strip().lower()
        if confirm == "y":
            try:
                columns, rows = run_query(result.sql)
            except Exception as e:
                print(f"The query failed: {e}")
                continue
            print(" | ".join(columns))
            for row in rows:
                print(" | ".join(str(value) for value in row))
        print()


if __name__ == "__main__":
    main()
