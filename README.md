# ClarifySQL

Text-to-SQL that **asks before it guesses**. Most text-to-SQL tools quietly
choose one meaning for an ambiguous question ("best customer": by revenue or
by order count?) and return an answer that looks confident but may be wrong.
ClarifySQL spots the ambiguity first, asks the user which meaning they want,
and only then writes the SQL.

## How it works

```
question ─► ambiguity check ─► (clarify with user) ─► LLM → SQL (JSON, Pydantic) ─► SELECT-only guard ─► PostgreSQL
```

| Module | Role |
|---|---|
| `clarifysql/ambiguity_checker.py` | Flags terms like "best", "top" and "recent" and offers concrete definitions |
| `clarifysql/sql_generator.py` | Sends the schema and question to a Groq LLM; parses the JSON reply into a `SQLResult` |
| `clarifysql/validator.py` | Lets only plain `SELECT` statements run |
| `clarifysql/db.py` | Runs the query on PostgreSQL |
| `cli.py` / `app.py` | Terminal and Streamlit front ends |
| `evaluation/evaluate.py` | Measures accuracy with and without clarification |

The seed data plants two different "best" customers on purpose (one has the
highest revenue, another the most orders), so the meaning you pick really
changes the answer.

## Quickstart

```bash
docker compose up -d                 # PostgreSQL on localhost:5432
pip install -r requirements.txt
cp .env.example .env                 # add a free Groq key from console.groq.com
python -m scripts.init_db            # create tables
python -m scripts.seed_data          # load sample data

python cli.py                        # terminal UI
streamlit run app.py                 # web UI at http://localhost:8501
python -m evaluation.evaluate        # before/after accuracy
```

Troubleshooting: `python -m scripts.check_db` shows which database and tables
the app can see. `python -m scripts.list_models` lists the Groq models your
key can use (set `GROQ_MODEL` in `.env`).

## Example

```
> Who is our best customer?
When you say 'best customer', what should that be based on?
  1. Total money spent (revenue)
  2. Number of orders placed
Pick a number: 1

SQL: SELECT c.name, SUM(p.amount) AS total_spent FROM customers c
     JOIN orders o ON o.customer_id = c.customer_id
     JOIN payments p ON p.order_id = o.order_id
     WHERE o.status = 'completed'
     GROUP BY c.name ORDER BY total_spent DESC LIMIT 1;
Why: Ranks customers by total amount paid across completed orders.
```

## Limitations

- Ambiguity detection uses a fixed keyword list, so it misses phrasings that
  are not on the list.
- The full schema goes into every prompt, which won't scale to large databases.
- Clarification choices are not remembered between questions.
