"""
Judge agent answers against reference outputs using GPT-5-mini.

Reads:
  bench/{run_name}/manifest.json   — manifest from run_agent_on_questions.py
  bench/bench_reference.json       — reference output from build_reference.py

Produces:
  bench/{run_name}/results.json    — full results with correct/explanation per question

Usage:
    python judge_benchmark_answers.py --run-name baseline
    python judge_benchmark_answers.py --run-name smoke --reference bench/bench_reference.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Windows: reconfigure stdout/stderr to UTF-8 so agent emoji don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()


# ---------------------------------------------------------------------------
# Pydantic model for structured judge output
# ---------------------------------------------------------------------------

class JudgeResult(BaseModel):
    correct: bool
    explanation: str


# ---------------------------------------------------------------------------
# Session log extraction helpers
# ---------------------------------------------------------------------------

def extract_solution(session_dir) -> str | None:
    """Return the <solution>...</solution> text from the last turn output file."""
    output_files = sorted(Path(session_dir).glob("turn_*_output.txt"))
    if not output_files:
        return None
    content = output_files[-1].read_text(encoding="utf-8", errors="replace")
    match = re.search(r"<solution>(.*?)</solution>", content, re.DOTALL)
    return match.group(1).strip() if match else None


def extract_agent_tokens(session_dir) -> dict:
    """Sum token usage across all turns from the token headers in output files.

    Each turn file starts with:
        === TOKEN USAGE ===
        Prompt Tokens: 4629 (149 new)
        Cached Tokens: 4480
        Completion Tokens: 2438
        Total Tokens: 7067
        ==================
    """
    output_files = sorted(Path(session_dir).glob("turn_*_output.txt"))
    total_prompt = 0
    total_completion = 0
    turns = 0

    for f in output_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        prompt_match = re.search(r"Prompt Tokens:\s*(\d+)", content)
        completion_match = re.search(r"Completion Tokens:\s*(\d+)", content)
        if prompt_match and completion_match:
            total_prompt += int(prompt_match.group(1))
            total_completion += int(completion_match.group(1))
            turns += 1

    return {
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
        "turns": turns,
    }


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = (
    "You are an expert judge evaluating whether an AI agent correctly answered "
    "a bioinformatics question about ecDNA amplicons.\n\n"
    "You will receive three inputs:\n"
    "  1. QUESTION — the natural-language question that was asked.\n"
    "  2. REFERENCE ANSWER — the ground-truth answer.\n"
    "  3. AGENT ANSWER — the agent's final answer.\n\n"
    "Evaluation rules:\n"
    "- The agent's answer (sample names, gene names, classification, key findings) "
    "must match the reference answer. Minor formatting differences and rounding are fine.\n"
    "- Return correct=true only if the agent's core answer is substantively correct."
)


def judge_answer(
    question: str,
    reference_output: str,
    agent_solution: str,
    client: OpenAI,
) -> tuple[JudgeResult, dict]:
    """Returns (JudgeResult, judge_token_usage)."""
    user_msg = (
        f"QUESTION:\n{question}\n\n"
        f"REFERENCE ANSWER:\n{reference_output}\n\n"
        f"AGENT ANSWER:\n{agent_solution}"
    )
    completion = client.beta.chat.completions.parse(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format=JudgeResult,
    )
    usage = completion.usage
    judge_tokens = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    return completion.choices[0].message.parsed, judge_tokens


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Judge agent answers against reference outputs")
    parser.add_argument("--run-name", required=True,
                        help="Run name matching a bench_runs_{run_name}.json file")
    parser.add_argument("--reference", default="bench/bench_reference.json",
                        help="Path to bench_reference.json (built by build_reference.py)")
    args = parser.parse_args()

    # --- Load manifest ---
    manifest_path = Path(f"bench/{args.run_name}/manifest.json")
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found. Run run_agent_on_questions.py first.")
        sys.exit(1)

    with open(manifest_path, encoding="utf-8") as f:
        runs = json.load(f)
    print(f"Loaded {len(runs)} runs from {manifest_path}")

    # --- Load reference ---
    ref_path = Path(args.reference)
    if not ref_path.exists():
        print(f"ERROR: {ref_path} not found. Run build_reference.py first.")
        sys.exit(1)

    with open(ref_path, encoding="utf-8") as f:
        reference = {p["index"]: p for p in json.load(f)}
    print(f"Loaded {len(reference)} reference entries from {ref_path}")

    results_path = f"bench/{args.run_name}/results.json"
    openai_client = OpenAI()

    results = []
    n_correct = 0
    n_judged = 0
    total_agent_tokens = 0
    total_judge_tokens = 0

    for run in runs:
        idx = run["index"]
        question = run["question"]
        session_dir = run["session_dir"]
        ref = reference.get(idx, {})

        print(f"\n{'='*60}")
        print(f"[Q{idx}] {question}")

        # Agent failed to run
        if run["error"] or session_dir is None:
            print(f"  Skipping — agent error: {run['error']}")
            results.append({
                "index": idx,
                "question": question,
                "reference_output": ref.get("reference_output"),
                "agent_solution": None,
                "correct": None,
                "explanation": f"Agent error: {run['error']}",
                "agent_tokens": None,
                "judge_tokens": None,
                "session_dir": session_dir,
            })
            continue

        # Extract from session logs
        agent_solution = extract_solution(session_dir)
        agent_tokens = extract_agent_tokens(session_dir)
        total_agent_tokens += agent_tokens["total_tokens"]

        print(f"  Agent tokens: {agent_tokens['total_tokens']:,} "
              f"(prompt={agent_tokens['prompt_tokens']:,}, "
              f"completion={agent_tokens['completion_tokens']:,}, "
              f"turns={agent_tokens['turns']})")

        if agent_solution is None:
            print("  Warning: no <solution> tag found")

        # Judge
        judge_tokens = None
        if agent_solution is not None:
            try:
                judge, judge_tokens = judge_answer(
                    question,
                    ref.get("reference_output", ""),
                    agent_solution,
                    openai_client,
                )
                correct = judge.correct
                explanation = judge.explanation
                n_judged += 1
                if correct:
                    n_correct += 1
                total_judge_tokens += judge_tokens["total_tokens"]
                label = "CORRECT" if correct else "WRONG"
                print(f"  Judge: {label} (tokens={judge_tokens['total_tokens']}) -- {explanation}")
            except Exception as exc:
                correct = None
                explanation = f"Judge error: {exc}"
                print(f"  Judge error: {exc}")
        else:
            correct = None
            explanation = "No <solution> tag found"

        results.append({
            "index": idx,
            "question": question,
            "reference_output": ref.get("reference_output"),
            "agent_solution": agent_solution,
            "correct": correct,
            "explanation": explanation,
            "agent_tokens": agent_tokens,
            "judge_tokens": judge_tokens,
            "session_dir": session_dir,
        })

    # Save results
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Results saved to: {results_path}")
    print(f"Score: {n_correct}/{n_judged} judged correct  ({len(results)} total questions)")
    print(f"Total agent tokens:  {total_agent_tokens:,}")
    print(f"Total judge tokens:  {total_judge_tokens:,}")
    print(f"Total tokens (both): {total_agent_tokens + total_judge_tokens:,}")


if __name__ == "__main__":
    main()
