# ClarifySQL

Text-to-SQL that **asks before it guesses**. Most text-to-SQL tools quietly
choose one meaning for an ambiguous question ("best customer": by revenue or
by order count?) and return an answer that looks confident but may be wrong.
ClarifySQL spots the ambiguity first, asks the user which meaning they want,
writes the SQL, and repairs the SQL itself if the database rejects it.

## How it works

```
question ─► ambiguity check (keyword + LLM) ─► clarify with user ─► LLM → SQL ─► validate + EXPLAIN ─► run (read-only)
                                                                       ▲                │ error
                                                                       └── fix it ◄─────┘   (self-correction, ≤2 retries)
```

| Module | Role |
|---|---|
| `clarifysql/ambiguity_checker.py` | **Hybrid detection.** A keyword list (fast, with hand-written options) plus an LLM that judges the question in context. It catches wording the list has never seen and skips questions that already state their meaning. |
| `clarifysql/sql_generator.py` | Question → SQL as Pydantic-validated JSON. **Self-correction loop:** an unsafe or invalid query is sent back to the LLM with the Postgres error message to fix. |
| `clarifysql/validator.py` | Allows a single `SELECT`/`WITH` statement only |
| `clarifysql/db.py` | Runs queries in a read-only transaction with a 5 s timeout. `EXPLAIN` checks a query without running it. |
| `clarifysql/llm.py`, `schema.py` | Shared Groq client (with rate-limit backoff) and schema description |
| `cli.py` / `app.py` | Terminal and Streamlit front ends |
| `evaluation/` | Benchmark and execution-accuracy evaluation (below) |

The seed data plants two different "best" customers on purpose (one has the
highest revenue, another the most orders), so the meaning you pick really
changes the answer.

## Evaluation

`evaluation/benchmark.py` holds 58 questions (30 unambiguous, 28 ambiguous
across 7 kinds of ambiguity), each with a hand-written gold SQL query.
Ambiguous items also record what the asker *meant*. Intents deliberately
vary, so a system that always guesses the same reading can't score well.

- **Execution accuracy:** the generated SQL and the gold SQL both run, and
  their result rows are compared (the metric Spider and BIRD use). Extra
  columns and differences in formatting are tolerated.
- **Simulated user:** when the system asks a clarification question, an LLM
  that knows the true intent picks one of the *system's own* options. The
  gold answer never reaches the SQL generator.
- **Benchmark check:** `--check` confirms every gold query returns rows and
  that both readings of every ambiguous question really give different
  answers on this data.

Results on all 58 questions (Groq `qwen/qwen3.8-27b`, one run; expect a
few points of variation between runs):

| | Baseline<br>(no clarification) | Keyword<br>clarification | **Hybrid<br>clarification** |
|---|---|---|---|
| Execution accuracy, all | 70.7% | 75.9% | **89.7%** |
| Execution accuracy, ambiguous | 39.3% | 50.0% | **78.6%** |
| Execution accuracy, unambiguous | 100% | 100% | 100% |
| Ambiguity detection F1 | – | 27.0% | **96.4%** |
| Unnecessary questions asked | – | 4 | 1 |
| Invalid first-try SQL fixed by self-correction | – | 3 / 3 | 0 / 0 |

What's left to fix: hybrid asked on all 6 ambiguous questions it still
gets wrong, but:
- in 4, none of the LLM's options matched what the user meant (e.g. "new
  customer" = signed up in the last 6 months);
- in 1, it asked about the time window of "total sales last week" instead
  of money vs. order count;
- in 1 ("revenue over the past month"), the user picked the right option,
  but the SQL filtered by payment date instead of order date.

Self-correction rarely triggers on this small schema;
it matters most when a question names something that doesn't exist (e.g.
a phone number column).

```bash
python -m evaluation.evaluate --check     # validate the benchmark (no LLM calls)
python -m evaluation.evaluate             # ~25 min on Groq's free tier
python -m evaluation.evaluate --configs baseline hybrid --limit 5   # quick run
```

Per-question results are saved to `evaluation/results/latest.json`.

## Quickstart

```bash
docker compose up -d                 # PostgreSQL on localhost:5432
pip install -r requirements.txt
cp .env.example .env                 # add a free Groq key from console.groq.com
python -m scripts.init_db            # create tables
python -m scripts.seed_data          # load sample data (dates relative to today)

python cli.py                        # terminal UI
streamlit run app.py                 # web UI at http://localhost:8501
```

Troubleshooting: `python -m scripts.check_db` shows which database and tables
the app can see. `python -m scripts.list_models` lists the Groq models your
key can use (set `GROQ_MODEL` in `.env`).

## Example

```
> Who is our biggest customer?          ("biggest" isn't on the keyword list; the LLM catches it)
How should we define 'biggest' customer?
  1. By total revenue
  2. By number of orders
Pick a number: 2

SQL: SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.customer_id
     WHERE o.status = 'completed' GROUP BY c.customer_id, c.name ORDER BY COUNT(*) DESC LIMIT 1
```

## Limitations

- The benchmark is hand-written for this schema (in-domain), not a public dataset.
- The full schema goes into every prompt, which won't scale to large databases.
- Clarification choices are not remembered between questions.
