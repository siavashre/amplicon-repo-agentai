import json
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_test_output(output: str) -> dict[int, str]:
    blocks: dict[int, str] = {}
    current_idx = None
    current_lines = []
    marker_re = re.compile(r"^=== QUESTION (\d+) ===$")

    for line in output.splitlines():
        marker = marker_re.match(line.strip())
        if marker:
            if current_idx is not None:
                blocks[current_idx] = "\n".join(current_lines).strip()
            current_idx = int(marker.group(1))
            current_lines = []
            continue
        if current_idx is not None:
            current_lines.append(line)

    if current_idx is not None:
        blocks[current_idx] = "\n".join(current_lines).strip()
    log(f"Parsed {len(blocks)} question blocks from test.py output.")
    return blocks


def extract_notebook_outputs(nb_path: Path) -> list[str]:
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    outputs: list[str] = []

    code_cells = [cell for cell in nb.get("cells", []) if cell.get("cell_type") == "code"]
    for idx, cell in enumerate(code_cells):
        # Skip setup cell (first code cell)
        if idx == 0:
            continue
        cell_outputs = []
        for out in cell.get("outputs", []) or []:
            output_type = out.get("output_type")
            if output_type == "stream" and out.get("name") == "stdout":
                text = out.get("text", [])
                if isinstance(text, list):
                    cell_outputs.append("".join(text))
                elif isinstance(text, str):
                    cell_outputs.append(text)
            # Some notebooks store stdout in a custom mime type
            if "text" in out and isinstance(out.get("text"), list):
                cell_outputs.append("".join(out.get("text")))
        outputs.append("\n".join(cell_outputs).strip())
    log(f"Extracted {len(outputs)} expected output blocks from notebook.")
    return outputs


def compare_outputs(expected: list[str], actual_by_q: dict[int, str]) -> list[dict[str, str | int | float]]:
    results = []
    total = min(len(expected), len(actual_by_q))

    log(f"Comparing {total} questions (min of expected={len(expected)} and actual={len(actual_by_q)}).")

    for i in range(1, total + 1):
        exp = expected[i - 1]
        act = actual_by_q.get(i, "")
        exp_norm = normalize_text(exp)
        act_norm = normalize_text(act)
        if not exp_norm:
            status = "no-expected"
            ratio = 0.0
        else:
            if exp_norm in act_norm:
                status = "pass"
                ratio = 1.0
            else:
                ratio = SequenceMatcher(None, exp_norm, act_norm).ratio()
                status = "fail"
        results.append(
            {
                "question": i,
                "status": status,
                "similarity": ratio,
                "expected": exp,
                "actual": act,
            }
        )
        log(f"Q{i}: {status} (similarity={ratio:.3f})")
    return results


def write_report(report_path: Path, results: list[dict[str, str | int | float]]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    no_expected = sum(1 for r in results if r["status"] == "no-expected")

    lines = []
    lines.append("# test.py vs Tests.ipynb report")
    lines.append("")
    lines.append(f"Total compared: {total}")
    lines.append(f"Pass: {passed}")
    lines.append(f"Fail: {failed}")
    lines.append(f"No expected output: {no_expected}")
    lines.append("")

    for r in results:
        q = r["question"]
        status = r["status"]
        similarity = r["similarity"]
        lines.append(f"## Question {q}")
        lines.append(f"Status: {status}")
        lines.append(f"Similarity: {similarity:.3f}")
        lines.append("")
        exp = str(r["expected"])[:2000]
        act = str(r["actual"])[:2000]
        lines.append("Expected (truncated):")
        lines.append("```")
        lines.append(exp)
        lines.append("```")
        lines.append("Actual (truncated):")
        lines.append("```")
        lines.append(act)
        lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    log(f"Report written: {report_path}")


def run_test_script(repo_root: Path) -> tuple[str, int]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    amplicon_dir = repo_root / "amplicon"
    cmd = [sys.executable, "test.py"]
    log(f"Running command: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=str(amplicon_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    output_lines = []
    if process.stdout is not None:
        for line in process.stdout:
            output_lines.append(line)
            stripped = line.strip()
            if stripped.startswith("=== QUESTION "):
                log(f"Running {stripped}")
            else:
                print(line, end="", flush=True)

    return_code = process.wait()
    output = "".join(output_lines)
    log(f"test.py exit code: {return_code}")
    return output, return_code


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    nb_path = repo_root / "Tests.ipynb"
    report_path = repo_root / "tests_report.md"
    output_path = repo_root / "test_run_output.txt"

    if not nb_path.exists():
        print(f"Notebook not found: {nb_path}")
        return 1

    log("Starting comparison workflow.")

    log("Step 1/5: Running test.py...")
    output, exit_code = run_test_script(repo_root)
    output_path.write_text(output, encoding="utf-8")
    log(f"Saved test.py output to {output_path}")

    log("Step 2/5: Parsing test.py output...")
    actual_by_q = parse_test_output(output)

    log("Step 3/5: Extracting notebook outputs...")
    expected_outputs = extract_notebook_outputs(nb_path)

    log("Step 4/5: Comparing outputs...")
    results = compare_outputs(expected_outputs, actual_by_q)

    log("Step 5/5: Writing report...")
    write_report(report_path, results)

    if exit_code != 0:
        log("test.py exited with a non-zero status. See test_run_output.txt for details.")
    log("Done.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
