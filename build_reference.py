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
from io import StringIO
from pathlib import Path

import nbformat


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
    nb = nbformat.read(open(notebook_path, encoding="utf-8"), as_version=4)
    cells = nb.cells
    print(f"Loaded {len(cells)} cells from {notebook_path}")

    namespace: dict = {}

    # Cell 0: setup — run it to populate shared namespace (df, helpers, etc.)
    if cells[0].cell_type == "code":
        setup_src = _patch_data_paths(cells[0].source)
        print("Running setup cell...")
        exec(compile(setup_src, "<setup>", "exec"), namespace)  # noqa: S102
        print("  Setup OK")

    pairs = []
    i = 1
    while i < len(cells) - 1:
        if cells[i].cell_type == "markdown" and cells[i + 1].cell_type == "code":
            question = cells[i].source.strip()
            code = cells[i + 1].source.strip()
            idx = len(pairs)

            buf = StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    exec(compile(_patch_data_paths(code), f"<q{idx}>", "exec"), namespace)  # noqa: S102
                output = buf.getvalue().strip() or "(no stdout)"
            except Exception as exc:
                output = f"ERROR: {exc}"
                print(f"  [Q{idx}] ERROR: {exc}")

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
        len(pairs),  # if not found, all questions are CCLE-only
    )
    for p in pairs:
        if p["index"] < mix_start:
            p["question"] = "(Use CCLE dataset only.) " + p["question"]

    print(f"Tagged Q0-Q{mix_start - 1} as CCLE-only, Q{mix_start}+ as mixed datasets")

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
