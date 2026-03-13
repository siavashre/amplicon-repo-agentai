"""
Run the A1 agent on benchmark questions and save session logs.

Produces:
  bench/{run_name}/logs/session_*/   — per-question agent logs
  bench/{run_name}/manifest.json     — manifest mapping index -> session_dir

Run judge_benchmark_answers.py afterwards to score the results.

Usage:
    python run_agent_on_questions.py --run-name baseline
    python run_agent_on_questions.py --run-name smoke --questions 0 1 2
    python run_agent_on_questions.py --run-name ccle_only --questions-range 0 23
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows: reconfigure stdout/stderr to UTF-8 so agent emoji don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Run A1 agent on benchmark questions")
    parser.add_argument("--run-name", default=None,
                        help="Name for this run (default: auto timestamp)")
    parser.add_argument("--questions", nargs="+", type=int, default=None,
                        help="Explicit question indices, e.g. --questions 0 1 5")
    parser.add_argument("--questions-range", nargs=2, type=int, metavar=("START", "END"),
                        default=None,
                        help="Inclusive range, e.g. --questions-range 0 23")
    parser.add_argument("--reference", default="bench/bench_reference.json",
                        help="Path to bench_reference.json (built by build_reference.py)")
    args = parser.parse_args()

    if args.questions and args.questions_range:
        print("ERROR: use --questions or --questions-range, not both.")
        sys.exit(1)

    # --- Load reference ---
    ref_path = Path(args.reference)
    if not ref_path.exists():
        print(f"ERROR: {ref_path} not found. Run build_reference.py first.")
        sys.exit(1)

    with open(ref_path, encoding="utf-8") as f:
        pairs = json.load(f)
    print(f"Loaded {len(pairs)} reference entries from {ref_path}")

    # --- Subset ---
    if args.questions is not None:
        pairs = [p for p in pairs if p["index"] in args.questions]
        print(f"Running subset: questions {args.questions}")
    elif args.questions_range is not None:
        start, end = args.questions_range
        pairs = [p for p in pairs if start <= p["index"] <= end]
        print(f"Running subset: questions {start} to {end} (inclusive)")

    # --- Run identification ---
    run_name = args.run_name or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = f"bench/{run_name}/logs"
    manifest_path = f"bench/{run_name}/manifest.json"
    os.makedirs(run_dir, exist_ok=True)

    print(f"Run: {run_name}")
    print(f"Logs dir: {run_dir}")
    print(f"Manifest: {manifest_path}")

    # --- Resume: skip questions already completed successfully ---
    runs = []
    if Path(manifest_path).exists():
        with open(manifest_path, encoding="utf-8") as f:
            runs = json.load(f)
        completed = {r["index"] for r in runs if r["error"] is None}
        if completed:
            before = len(pairs)
            pairs = [p for p in pairs if p["index"] not in completed]
            print(f"Resuming: skipping {len(completed)} already-completed question(s), {len(pairs)}/{before} remaining")

    print(f"Questions to run: {len(pairs)}")

    # --- Agent imports (mutate default_config before any A1 construction) ---
    from biomni.config import default_config
    from biomni.agent.a1 import A1

    for pair in pairs:
        idx = pair["index"]
        question = pair["question"]

        print(f"\n{'='*60}")
        print(f"[Q{idx}] {question[:100]}")

        # Must mutate default_config BEFORE constructing A1 (a1.py:231 reads it at init)
        default_config.logs_dir = run_dir

        try:
            agent = A1(llm="gpt-5-mini", expected_data_lake_files=[])
            agent.go(question)
            session_dir = str(agent.token_logger.session_dir)
            error = None
            print(f"  Done -> {session_dir}")
        except Exception as exc:
            session_dir = None
            error = str(exc)
            print(f"  Agent error: {exc}")

        runs.append({
            "index": idx,
            "question": question,
            "session_dir": session_dir,
            "error": error,
        })

        # Save incrementally after each question so a crash doesn't lose prior work
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(runs, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Manifest saved to: {manifest_path}")
    print(f"Completed: {sum(1 for r in runs if r['error'] is None)}/{len(runs)} questions")


if __name__ == "__main__":
    main()
