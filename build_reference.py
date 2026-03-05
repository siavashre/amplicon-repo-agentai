"""
One-time script: parse Tests.ipynb, run every reference code cell, and save
(question, reference_code, reference_output) tuples to bench_reference.json.

Run once before benchmarking:
    python build_reference.py
    python build_reference.py --notebook Tests.ipynb --output bench_reference.json
"""

import argparse
import contextlib
import json
import re
import signal
from io import StringIO
from pathlib import Path

import nbformat

CELL_TIMEOUT = 120  # seconds; cells that exceed this are skipped


def _cell_timeout_handler(signum, frame):
    raise TimeoutError(f"Cell execution exceeded {CELL_TIMEOUT}s")


def _patch_data_paths(source: str) -> str:
    """Patch hardcoded data directory/file paths that don't exist on disk.

    Handles both:
      PATH = "biomni/data/.../CCLE.csv"   (single file)
      DATA_DIR = "biomni/data/.../data_lake/"  (directory prefix)
    """
    # Patch single-file PATH assignment
    m = re.search(r'\bPATH\s*=\s*["\']([^"\']+)["\']', source)
    if m:
        nb_path = m.group(1)
        if not Path(nb_path).exists():
            candidates = list(Path(".").rglob("CCLE.csv"))
            if candidates:
                real_path = str(candidates[0]).replace("\\", "/")
                source = source.replace(nb_path, real_path)
                print(f"  Patched PATH: {nb_path!r} -> {real_path!r}")

    # Patch DATA_DIR assignment by finding the real amplicon_data directory
    m = re.search(r'\bDATA_DIR\s*=\s*["\']([^"\']+)["\']', source)
    if m:
        nb_dir = m.group(1)
        if not Path(nb_dir).exists():
            candidates = list(Path(".").rglob("CCLE.csv"))
            if candidates:
                real_dir = str(candidates[0].parent).replace("\\", "/") + "/"
                source = source.replace(nb_dir, real_dir)
                print(f"  Patched DATA_DIR: {nb_dir!r} -> {real_dir!r}")

    return source


def build_reference(notebook_path: str, output_path: str) -> list[dict]:
    """Execute all notebook cells in a shared namespace; save outputs to JSON."""
    with open(notebook_path, encoding="utf-8") as fh:
        nb = nbformat.read(fh, as_version=4)
    cells = nb.cells
    print(f"Loaded {len(cells)} cells from {notebook_path}")

    namespace: dict = {}

    # Force non-interactive matplotlib backend before any cell runs so that
    # plt.show() / chart-drawing cells don't open GUI windows and block.
    exec("import matplotlib; matplotlib.use('Agg')", namespace)  # noqa: S102

    signal.signal(signal.SIGALRM, _cell_timeout_handler)

    # Cell 0: setup — run it to populate shared namespace (df, helpers, etc.)
    if cells[0].cell_type == "code":
        setup_src = _patch_data_paths(cells[0].source)
        print("Running setup cell...")
        signal.alarm(CELL_TIMEOUT)
        try:
            exec(compile(setup_src, "<setup>", "exec"), namespace)  # noqa: S102
        finally:
            signal.alarm(0)
        print("  Setup OK")

    pairs = []
    i = 1
    while i < len(cells) - 1:
        if cells[i].cell_type == "markdown" and cells[i + 1].cell_type == "code":
            question = cells[i].source.strip()
            code = cells[i + 1].source.strip()
            idx = len(pairs)

            buf = StringIO()
            exec_error = None
            try:
                signal.alarm(CELL_TIMEOUT)
                with contextlib.redirect_stdout(buf):
                    exec(compile(_patch_data_paths(code), f"<q{idx}>", "exec"), namespace)  # noqa: S102
                output = buf.getvalue().strip() or "(no stdout)"
            except TimeoutError as exc:
                exec_error = exc
                print(f"  [Q{idx}] SKIPPED (timeout): {exc}")
            except Exception as exc:
                exec_error = exc
                print(f"  [Q{idx}] SKIPPED (execution error): {exc}")
            finally:
                signal.alarm(0)

            if exec_error is not None:
                i += 2
                continue

            pairs.append({
                "index": idx,
                "question": question,
                "reference_code": code,
                "reference_output": output,
            })
            print(f"  [Q{idx}] {question[:70]} -> {len(output)} chars")
            i += 2
        else:
            i += 1

    # Tag CCLE-only questions: find where the mixed-datasets section begins
    # (detected by the first question containing "mix dataset") and prepend a
    # short instruction to every question before that boundary.
    mix_start = next(
        (p["index"] for p in pairs if "mix dataset" in p["question"].lower()),
        None,
    )
    if mix_start is None:
        print("WARNING: No 'mix dataset' question found; tagging all questions as CCLE-only.")
        mix_start = len(pairs)
    else:
        print(f"Tagged Q0-Q{mix_start - 1} as CCLE-only, Q{mix_start}+ as mixed datasets")

    for p in pairs:
        if p["index"] < mix_start:
            p["question"] = "(Use CCLE dataset only.) " + p["question"]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2)

    print(f"\nSaved {len(pairs)} entries to {output_path}")
    return pairs


def main():
    parser = argparse.ArgumentParser(description="Build bench_reference.json from Tests.ipynb")
    parser.add_argument("--notebook", default="Tests.ipynb")
    parser.add_argument("--output", default="bench_reference.json")
    args = parser.parse_args()
    build_reference(args.notebook, args.output)


if __name__ == "__main__":
    main()
