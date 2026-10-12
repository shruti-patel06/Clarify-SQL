"""End-to-end evaluation on the benchmark in evaluation/benchmark.py.

Each configuration answers every benchmark question the way the real app
would, and the answer is scored by *execution accuracy*: run the generated
SQL and the gold SQL against the database and compare the result rows.
This is the metric text-to-SQL benchmarks such as Spider and BIRD use. It
doesn't care how the SQL is written, only whether it returns the right
answer.

Configurations:
- baseline: no clarification, no self-correction (plain text-to-SQL)
- keyword:  keyword clarification + self-correction
- hybrid:   keyword + LLM clarification + self-correction (the full app)

When a configuration asks a clarification question, a *simulated user*
answers it: an LLM that is told what the person really meant (the
benchmark item's "intent") and picks the matching option, or none. So
the SQL generator only ever sees the system's own options, never the
gold answer.

Usage:
    python -m evaluation.evaluate                     # all configurations
    python -m evaluation.evaluate --configs baseline hybrid --limit 10
    python -m evaluation.evaluate --check             # sanity-check the benchmark (no LLM calls)
"""
import argparse
import json
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from itertools import product
from pathlib import Path

from groq import GroqError

from clarifysql.ambiguity_checker import NOT_AMBIGUOUS, apply_clarification, check_ambiguity
from clarifysql.db import run_query
from clarifysql.llm import chat_json
from clarifysql.sql_generator import MAX_RETRIES, generate_sql
from evaluation.benchmark import BENCHMARK

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "latest.json"

CONFIGS = {
    "baseline": {"clarify": None, "retries": 0},
    "keyword": {"clarify": "keyword", "retries": MAX_RETRIES},
    "hybrid": {"clarify": "hybrid", "retries": MAX_RETRIES},
}

UNAMBIGUOUS_INTENT = "exactly what the question says, nothing more"

SIMULATED_USER_PROMPT = """You are role-playing a user of a database app. You asked a question and the app
asked you to clarify it. Pick the option that matches what you meant.
Respond with ONLY JSON: {"choice": <option number>} or {"choice": null} if no option matches."""


# ---------- comparing results ----------

def normalize(value):
    """Makes equal answers compare equal: 2.50 (Decimal) == 2.5 (float),
    a midnight timestamp == the same date, averages rounded to 2 places."""
    if isinstance(value, datetime):
        value = value.date() if value.time() == datetime.min.time() else value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return round(float(value), 2)
    return value


def results_match(gold_rows, pred_rows, ordered):
    """True if the prediction contains the gold answer.

    Column names and order are ignored and extra predicted columns are
    allowed (e.g. a query returning name *and* total for "who is our best
    customer?" is still right). Row order only matters if the gold query
    has an ORDER BY.
    """
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True
    gold = [tuple(normalize(v) for v in row) for row in gold_rows]
    pred = [tuple(normalize(v) for v in row) for row in pred_rows]

    def same(a, b):
        return list(a) == list(b) if ordered else Counter(a) == Counter(b)

    # For each gold column, find predicted columns holding the same values...
    gold_cols, pred_cols = list(zip(*gold)), list(zip(*pred))
    candidates = [[j for j, pc in enumerate(pred_cols) if same(gc, pc)] for gc in gold_cols]
    # ...then check that some choice of them also lines up row by row.
    for mapping in product(*candidates):
        if len(set(mapping)) == len(mapping):
            projected = [tuple(row[j] for j in mapping) for row in pred]
            if same(gold, projected):
                return True
    return False


# ---------- running one question ----------

def simulated_user_choice(item, check):
    """Returns the option the simulated user picks, or None."""
    options = "\n".join(f"{i}. {o.label}" for i, o in enumerate(check.options, start=1))
    prompt = (f"Your question: {item['question']}\n"
              f"What you meant: {item.get('intent', UNAMBIGUOUS_INTENT)}\n"
              f"The app asked: {check.clarification_question}\n"
              f"Options:\n{options}")
    try:
        choice = chat_json([
            {"role": "system", "content": SIMULATED_USER_PROMPT},
            {"role": "user", "content": prompt},
        ]).get("choice")
        return check.options[int(choice) - 1] if choice else None
    except (GroqError, ValueError, TypeError, IndexError, AttributeError):
        return None


def run_item(item, config, gold_rows):
    question = item["question"]
    check = check_ambiguity(question, config["clarify"]) if config["clarify"] else NOT_AMBIGUOUS
    chosen = simulated_user_choice(item, check) if check.is_ambiguous else None
    if chosen:
        question = apply_clarification(question, chosen)

    result = generate_sql(question, max_retries=config["retries"])
    correct, error = False, result.error
    if result.ok:
        try:
            _, pred_rows = run_query(result.sql)
            correct = results_match(gold_rows, pred_rows, ordered="order by" in item["gold_sql"].lower())
        except Exception as e:  # runtime errors like division by zero or the statement timeout
            error = str(e).strip()

    return {
        "question": item["question"],
        "ambiguous": "intent" in item,
        "asked": check.is_ambiguous,
        "detector": check.source,
        "chosen": chosen.label if chosen else None,
        "sql": result.sql,
        "failed_attempts": len(result.failed_attempts),
        "retry_errors": [a.error.splitlines()[0] for a in result.failed_attempts],
        "correct": correct,
        "error": error,
    }


# ---------- metrics ----------

def pct(part, whole):
    return round(100 * part / whole, 1) if whole else 0.0


def summarize(rows, clarifies):
    amb = [r for r in rows if r["ambiguous"]]
    unamb = [r for r in rows if not r["ambiguous"]]
    summary = {
        "execution_accuracy": pct(sum(r["correct"] for r in rows), len(rows)),
        "ambiguous_accuracy": pct(sum(r["correct"] for r in amb), len(amb)),
        "unambiguous_accuracy": pct(sum(r["correct"] for r in unamb), len(unamb)),
        # Self-correction: "accuracy without retries" counts the questions
        # that were right on the first try. With temperature 0 the first
        # attempt is nearly (not perfectly) the same with or without
        # retries, so this is a close estimate rather than a separate run.
        "first_try_failures": sum(r["failed_attempts"] > 0 for r in rows),
        "recovered_by_retry": sum(r["failed_attempts"] > 0 and not r["error"] for r in rows),
        "accuracy_without_retries": pct(sum(r["correct"] and r["failed_attempts"] == 0 for r in rows), len(rows)),
    }
    if clarifies:
        tp = sum(r["asked"] for r in amb)
        fp = sum(r["asked"] for r in unamb)
        precision, recall = (tp / (tp + fp) if tp + fp else 0.0), tp / len(amb) if amb else 0.0
        summary.update({
            "detection_precision": round(100 * precision, 1),
            "detection_recall": round(100 * recall, 1),
            "detection_f1": round(100 * 2 * precision * recall / (precision + recall), 1) if precision + recall else 0.0,
            "false_alarms": fp,
        })
    return summary


def print_report(summaries, total):
    names = list(summaries)
    rows = [
        ("Execution accuracy (all)", "execution_accuracy", "%"),
        ("  ambiguous questions", "ambiguous_accuracy", "%"),
        ("  unambiguous questions", "unambiguous_accuracy", "%"),
        ("Accuracy without retries", "accuracy_without_retries", "%"),
        ("First-try SQL failures", "first_try_failures", ""),
        ("  fixed by self-correction", "recovered_by_retry", ""),
        ("Detection precision", "detection_precision", "%"),
        ("Detection recall", "detection_recall", "%"),
        ("Detection F1", "detection_f1", "%"),
        ("False alarms (asked when clear)", "false_alarms", ""),
    ]
    print(f"\nResults on {total} questions\n")
    print(f"{'':34}" + "".join(f"{n:>10}" for n in names))
    for label, key, unit in rows:
        cells = [f"{summaries[n][key]}{unit}" if key in summaries[n] else "-" for n in names]
        print(f"{label:34}" + "".join(f"{c:>10}" for c in cells))


# ---------- entry points ----------

def check_benchmark():
    """Confirms every gold query runs and returns rows, and that the two
    readings of every ambiguous question really give different answers."""
    problems = 0
    for item in BENCHMARK:
        _, gold = run_query(item["gold_sql"])
        issue = None
        if not gold:
            issue = "gold query returns no rows"
        elif "other_sql" in item:
            _, other = run_query(item["other_sql"])
            if results_match(gold, other, ordered="order by" in item["gold_sql"].lower()):
                issue = "both readings return the same answer, so it isn't ambiguous on this data"
        if issue:
            problems += 1
            print(f"PROBLEM: {item['question']} -> {issue}")
    print(f"Checked {len(BENCHMARK)} items, {problems} problem(s).")


def warn_if_data_is_stale():
    _, rows = run_query("SELECT CURRENT_DATE - MAX(order_date) FROM orders")
    if rows[0][0] is not None and rows[0][0] > 7:
        print(f"Warning: the newest order is {rows[0][0]} days old. Questions about 'the last 30 days' "
              "assume fresh data, so re-run scripts.init_db and scripts.seed_data first.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", nargs="+", choices=CONFIGS, default=list(CONFIGS))
    parser.add_argument("--limit", type=int, help="only use the first N questions of each half (for a quick run)")
    parser.add_argument("--check", action="store_true", help="validate the benchmark instead of evaluating")
    args = parser.parse_args()

    if args.check:
        check_benchmark()
        return
    warn_if_data_is_stale()

    items = BENCHMARK
    if args.limit:
        unamb = [i for i in BENCHMARK if "intent" not in i][:args.limit]
        amb = [i for i in BENCHMARK if "intent" in i][:args.limit]
        items = unamb + amb
    gold = [run_query(item["gold_sql"])[1] for item in items]

    summaries, details = {}, {}
    for name in args.configs:
        config = CONFIGS[name]
        rows = []
        for n, (item, gold_rows) in enumerate(zip(items, gold), start=1):
            row = run_item(item, config, gold_rows)
            rows.append(row)
            mark = "ok " if row["correct"] else "XX "
            print(f"[{name} {n}/{len(items)}] {mark} asked={'y' if row['asked'] else 'n'} "
                  f"retries={row['failed_attempts']}  {item['question']}")
        summaries[name] = summarize(rows, clarifies=bool(config["clarify"]))
        details[name] = rows

    print_report(summaries, len(items))
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"summary": summaries, "details": details}, indent=2, default=str))
    print("\nFull per-question results saved to evaluation/results/latest.json")


if __name__ == "__main__":
    main()
