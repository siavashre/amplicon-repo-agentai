"""
Run the judge N times and display a comparison table of results.

Usage:
    python judge_multi_run.py --run-name baseline --runs 3
    python judge_multi_run.py --run-name baseline --runs 5 --reference bench_reference.json
    python judge_multi_run.py --run-name baseline --runs 3 --no-rerun   # load existing run files
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


EMOJI = {True: "CORRECT", False: "WRONG  ", None: "SKIP   "}


def run_judge(run_name: str, reference: str) -> list[dict]:
    """Run the judge once and return parsed results."""
    cmd = [sys.executable, "judge_benchmark_answers.py", "--run-name", run_name, "--reference", reference]
    subprocess.run(cmd, check=True)
    results_path = Path(f"bench_results_{run_name}.json")
    with open(results_path, encoding="utf-8") as f:
        return json.load(f)


def save_run_results(run_name: str, run_number: int):
    src = Path(f"bench_results_{run_name}.json")
    dst = Path(f"bench_results_{run_name}_run{run_number}.json")
    shutil.copy(src, dst)


def print_table(run_name: str, all_runs: list[list[dict]]):
    n_runs = len(all_runs)
    questions = all_runs[0]

    Q_WIDTH = 58
    COL_WIDTH = 9  # "CORRECT" / "WRONG  " / "SKIP   "
    col_sep = "  "

    run_headers = [f"Run {i+1}".center(COL_WIDTH) for i in range(n_runs)]
    header = f"{'#':<5}  {'Question':<{Q_WIDTH}}  {col_sep.join(run_headers)}"
    sep = "-" * len(header)

    print(f"\n{'='*len(header)}")
    print(f"Judge consistency report  |  run-name: {run_name}  |  {n_runs} runs")
    print(f"{'='*len(header)}")
    print(header)
    print(sep)

    flip_count = 0
    for q_entry in questions:
        idx = q_entry["index"]
        question = q_entry["question"]
        q_short = question if len(question) <= Q_WIDTH else question[:Q_WIDTH - 1] + "~"

        verdicts = []
        for run in all_runs:
            entry = next((e for e in run if e["index"] == idx), None)
            verdicts.append(entry["correct"] if entry else None)

        cells = [EMOJI[v].center(COL_WIDTH) for v in verdicts]
        print(f"Q{idx:<4}  {q_short:<{Q_WIDTH}}  {col_sep.join(cells)}")

        judged = [v for v in verdicts if v is not None]
        if judged and len(set(judged)) > 1:
            flip_count += 1
            print(f"{'':7}{'':>{Q_WIDTH}}  ^^^ VERDICT FLIPPED")

    print(sep)

    # Per-run score summary
    for i, run in enumerate(all_runs):
        n_correct = sum(1 for e in run if e["correct"] is True)
        n_judged  = sum(1 for e in run if e["correct"] is not None)
        n_skipped = sum(1 for e in run if e["correct"] is None)
        print(f"Run {i+1}:  {n_correct}/{n_judged} correct  ({n_skipped} skipped/errored)")

    print(sep)
    if flip_count == 0:
        print("No verdict flips detected across runs -- judge is fully consistent.")
    else:
        print(f"WARNING: {flip_count} question(s) flipped verdict across runs.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Run judge N times and compare results in a table")
    parser.add_argument("--run-name", required=True, help="Run name matching bench_runs_{name}.json")
    parser.add_argument("--runs", type=int, default=3, help="Number of judge runs (default: 3)")
    parser.add_argument("--reference", default="bench_reference.json", help="Path to bench_reference.json")
    parser.add_argument("--no-rerun", action="store_true",
                        help="Skip running the judge; load existing bench_results_{name}_runN.json files")
    args = parser.parse_args()

    all_runs = []

    if args.no_rerun:
        for i in range(1, args.runs + 1):
            path = Path(f"bench_results_{args.run_name}_run{i}.json")
            if not path.exists():
                print(f"ERROR: {path} not found. Run without --no-rerun first.")
                sys.exit(1)
            with open(path, encoding="utf-8") as f:
                all_runs.append(json.load(f))
            print(f"Loaded run {i} from {path}")
    else:
        for i in range(1, args.runs + 1):
            print(f"\n{'#'*60}")
            print(f"# JUDGE RUN {i} of {args.runs}")
            print(f"{'#'*60}\n")
            try:
                results = run_judge(args.run_name, args.reference)
            except subprocess.CalledProcessError as exc:
                print(f"\nERROR: Judge run {i} failed (exit code {exc.returncode}). Stopping early.")
                if all_runs:
                    print(f"Showing partial results from {len(all_runs)} completed run(s).")
                else:
                    sys.exit(1)
                break
            save_run_results(args.run_name, i)
            all_runs.append(results)
            print(f"\nRun {i} saved to bench_results_{args.run_name}_run{i}.json")

    print_table(args.run_name, all_runs)


if __name__ == "__main__":
    main()
