"""
Amplicon Cycle Query Tool for querying cycle/path structures predicted by AmpliconArchitect.

Each annotated cycle file covers one amplicon of one sample. The file has two sections:
  1. Segments: integer ID, chromosome, start, end
  2. Cycles: ID, copy count, length, is_cyclic, cycle_class, ordered segment list with strand

Files are organized as:
    {cycle_dir}/{dataset}/{sample_name}_{amplicon_number}_annotated_cycles

These annotated files are preferred over raw AA output — they filter low-complexity
overlaps, patch reference genome issues, and remove duplicate cycle entries.

Segment 0 is a reserved connection vertex indicating a linear path with open endpoints.
"""

import os
import re
from typing import Any

try:
    from amplicon.config import default_config
except Exception:
    default_config = None

# Regex to parse chrN:start-end genomic region strings
_REGION_PATTERN = re.compile(r"^(chr[0-9XYMa-z]+):(\d+)-(\d+)$", re.IGNORECASE)

# Regex to parse filename: {sample_name}_{amplicon_number}_annotated_cycles
_FILENAME_PATTERN = re.compile(r"^(.+)_(amplicon\d+)_annotated_cycl")

VALID_CYCLE_CLASSES = ["ecDNA-like", "Linear", "Rearranged", "Invalid"]

ALL_COLUMNS = [
    "dataset",
    "sample_name",
    "amplicon_number",
    "cycle_id",
    "copy_count",
    "length",
    "is_cyclic_path",
    "cycle_class",
    "num_segments",
    "chromosomes",
    "segments",
]


def _get_default_cycle_dir() -> str:
    base = os.environ.get("AMPLICON_PATH") or os.environ.get("AMPLICON_DATA_PATH")
    if base is None and default_config is not None:
        base = getattr(default_config, "path", None)
    if base is None:
        base = "./data"
    return os.path.join(base, "amplicon_data", "data_lake", "cycle_files")


def _parse_filename(filename: str) -> tuple[str, str] | None:
    """Parse sample_name and amplicon_number from a cycle filename."""
    match = _FILENAME_PATTERN.match(filename)
    if match:
        return match.group(1), match.group(2)
    return None


def _parse_cycle_file(filepath: str) -> list[dict[str, Any]]:
    """Parse an annotated cycle file into a list of cycle records.

    Each record contains all cycle fields plus a resolved 'segments' list
    where each entry has: id, strand, chrom, start, end.

    Returns an empty list if the file cannot be parsed.
    """
    segments: dict[int, dict[str, Any]] = {}  # seg_id -> {chrom, start, end}
    cycles: list[dict[str, Any]] = []

    try:
        with open(filepath) as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue

                # --- Segment line ---
                if line.startswith("Segment\t"):
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        seg_id = int(parts[1])
                        chrom = parts[2]
                        start = int(parts[3])
                        end = int(parts[4])
                        segments[seg_id] = {"chrom": chrom, "start": start, "end": end}
                    continue

                # --- Cycle line ---
                if line.startswith("Cycle="):
                    record = _parse_cycle_line(line, segments)
                    if record is not None:
                        cycles.append(record)
                    continue

    except Exception:
        return []

    return cycles


def _parse_cycle_line(line: str, segments: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    """Parse a single Cycle= line into a cycle record dict."""
    # Fields are semicolon-separated: Cycle=1;Copy_count=...;Length=...;IsCyclicPath=...;CycleClass=...;Segments=...
    fields: dict[str, str] = {}
    for part in line.split(";"):
        if "=" in part:
            key, _, val = part.partition("=")
            fields[key.strip()] = val.strip()

    try:
        cycle_id = int(fields["Cycle"])
        copy_count = float(fields["Copy_count"])
        length = int(fields["Length"])
        is_cyclic_path = fields.get("IsCyclicPath", "False").lower() == "true"
        cycle_class = fields.get("CycleClass", "")
        segments_str = fields.get("Segments", "")
    except (KeyError, ValueError):
        return None

    # Parse segment list: e.g., "21+,34-,37+" or "0+,34-,0+"
    resolved_segments = []
    raw_seg_tokens = [s.strip() for s in segments_str.split(",") if s.strip()]
    for token in raw_seg_tokens:
        if not token:
            continue
        strand = token[-1] if token[-1] in ("+", "-") else "+"
        try:
            seg_id = int(token[:-1])
        except ValueError:
            continue
        if seg_id == 0:
            # Connection vertex — include as marker with no coordinates
            resolved_segments.append({"id": 0, "strand": strand, "chrom": None, "start": None, "end": None})
        elif seg_id in segments:
            seg_info = segments[seg_id]
            resolved_segments.append({
                "id": seg_id,
                "strand": strand,
                "chrom": seg_info["chrom"],
                "start": seg_info["start"],
                "end": seg_info["end"],
            })
        else:
            # Unknown segment ID — include as-is without coordinates
            resolved_segments.append({"id": seg_id, "strand": strand, "chrom": None, "start": None, "end": None})

    # Derive chromosomes (exclude segment 0 / connection vertices)
    chromosomes = sorted({
        s["chrom"] for s in resolved_segments if s["id"] != 0 and s["chrom"] is not None
    })

    # num_segments excludes connection vertex (segment 0)
    num_segments = sum(1 for s in resolved_segments if s["id"] != 0)

    return {
        "cycle_id": cycle_id,
        "copy_count": copy_count,
        "length": length,
        "is_cyclic_path": is_cyclic_path,
        "cycle_class": cycle_class,
        "num_segments": num_segments,
        "chromosomes": chromosomes,
        "segments": resolved_segments,
    }


def _segment_overlaps_region(seg: dict[str, Any], chrom_r: str, start_r: int, end_r: int) -> bool:
    """Return True if a segment overlaps the given genomic region."""
    if seg["id"] == 0 or seg["chrom"] is None:
        return False
    return (
        seg["chrom"].lower() == chrom_r
        and seg["start"] <= end_r
        and seg["end"] >= start_r
    )


def query_amplicon_cycles(
    dataset: str | list[str] | None = None,
    sample_name: str | list[str] | None = None,
    sample_name_match: str | None = None,
    amplicon_number: str | list[str] | None = None,
    cycle_id: int | list[int] | None = None,
    cycle_class: str | list[str] | None = None,
    is_cyclic: bool | None = None,
    copy_count_min: float | None = None,
    copy_count_max: float | None = None,
    length_min: int | None = None,
    length_max: int | None = None,
    num_segments_min: int | None = None,
    num_segments_max: int | None = None,
    chrom: str | list[str] | None = None,
    genomic_region: str | list[str] | None = None,
    select: list[str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    cycle_dir: str | None = None,
) -> dict[str, Any]:
    """Query and filter cycle/path records from AmpliconArchitect annotated cycle files.

    Loads all annotated cycle files from the specified dataset folder(s), parses both
    the segment coordinate table and the cycle list, and returns one row per cycle with
    fully resolved segment coordinates embedded in each row.

    Each file has two sections:
      1. Segments — integer ID, chromosome, start, end.
      2. Cycles — ID, copy count, length (bp), cyclic flag, class, and an ordered
         segment list (segment ID + strand). This tool resolves segment IDs to full
         genomic coordinates so each returned row is self-contained.

    Segment 0 is a reserved connection vertex indicating a linear path whose endpoints
    connect to undetermined or out-of-amplicon positions.

    Args:
        dataset: Dataset folder name(s) to load (e.g., 'CCLE', 'TCGA', 'PCAWG').
            All cycle files in the folder are loaded together. Accepts a single value
            or list. If not specified, all available datasets are loaded.
        sample_name: Sample name(s) parsed from the filename (e.g., 'AU565_BREAST').
            Accepts a single value or list for OR matching.
        sample_name_match: Match mode for sample_name: 'exact', 'startswith', or
            'contains' (default). Case-insensitive.
        amplicon_number: Amplicon number(s) (e.g., 'amplicon1'). Parsed from the
            filename. Accepts a single value or list for OR matching.
        cycle_id: Cycle ID(s) to filter (e.g., 1 or [1, 3]). IDs are unique within a
            single file but restart from 1 across different files. Should be combined
            with sample_name and amplicon_number to target a specific cycle. Accepts a
            single value or list for OR matching.
        cycle_class: Cycle classification(s) to filter. Valid values: 'ecDNA-like',
            'Linear', 'Rearranged', 'Invalid'. Accepts a single value or list for OR
            matching.
        is_cyclic: Filter by whether the path is cyclic (True) or linear (False).
            Cyclic paths loop back to their first segment; non-cyclic paths contain
            segment 0 (connection vertex) indicating open endpoints.
        copy_count_min: Minimum copy count of the cycle (inclusive).
        copy_count_max: Maximum copy count of the cycle (inclusive).
        length_min: Minimum total path length in base pairs (inclusive).
        length_max: Maximum total path length in base pairs (inclusive).
        num_segments_min: Minimum number of segments, excluding segment 0 connection
            vertices. Useful for filtering out single-segment trivial cycles.
        num_segments_max: Maximum number of segments, excluding segment 0 connection
            vertices.
        chrom: Chromosome(s) to filter by (e.g., 'chr8'). Returns cycles where at
            least one non-zero segment lies on the specified chromosome(s). Accepts a
            single value or list for OR matching.
        genomic_region: Genomic region(s) in chrN:start-end format
            (e.g., 'chr8:127700000-128000000'). Returns cycles where at least one
            segment overlaps any of the specified regions. Overlap is defined as the
            segment interval intersecting the query region (inclusive). Accepts a single
            value or list for OR matching.
        select: Columns to return. Defaults to all columns: dataset, sample_name,
            amplicon_number, cycle_id, copy_count, length, is_cyclic_path, cycle_class,
            num_segments, chromosomes, segments. The 'segments' field is a list of
            objects each with: id, strand, chrom, start, end. The 'chromosomes' field
            is a sorted list of unique chromosomes spanned by the cycle. Use exact
            column names; unknown columns will raise an error.
        limit: Maximum number of rows to return. Returns all if not specified.
        offset: Row offset for pagination (default 0).
        cycle_dir: Path to the root cycle files directory containing dataset subfolders.
            If not specified, uses the default config path.

    Returns:
        Dictionary containing:
            - summary: Brief description of the results
            - row_count_total: Total matching rows before pagination
            - row_count_returned: Rows returned after pagination
            - filters_applied: Filters that were applied
            - rows: List of matching cycle records
            - schema: Column names in the returned data
            - datasets_loaded: List of dataset folders loaded
            - files_loaded: Number of cycle files loaded

    Raises:
        FileNotFoundError: If the cycle directory or dataset folder is not found.
        ValueError: If invalid parameter values are provided.
    """
    # --- Defaults ---
    if offset is None:
        offset = 0
    if sample_name_match is None:
        sample_name_match = "contains"
    if limit is not None:
        limit = max(1, limit)
    offset = max(0, offset)

    # --- Validate ---
    valid_match_modes = ["exact", "startswith", "contains"]
    if sample_name_match not in valid_match_modes:
        raise ValueError(
            f"Invalid sample_name_match '{sample_name_match}'. Must be one of: {valid_match_modes}"
        )

    if cycle_class is not None:
        cc_list = [cycle_class] if isinstance(cycle_class, str) else cycle_class
        invalid = [v for v in cc_list if v not in VALID_CYCLE_CLASSES]
        if invalid:
            raise ValueError(
                f"Invalid cycle_class value(s) {invalid}. Must be one of: {VALID_CYCLE_CLASSES}"
            )

    if select is not None:
        invalid_cols = [c for c in select if c not in ALL_COLUMNS]
        if invalid_cols:
            raise ValueError(
                f"Invalid columns requested: {invalid_cols}. Available: {ALL_COLUMNS}"
            )

    # Parse genomic regions early to catch format errors before loading files
    parsed_regions: list[tuple[str, int, int]] = []
    if genomic_region is not None:
        region_list = [genomic_region] if isinstance(genomic_region, str) else genomic_region
        for region in region_list:
            m = _REGION_PATTERN.match(region)
            if m is None:
                raise ValueError(
                    f"Invalid genomic_region format '{region}'. "
                    "Expected format: chrN:start-end (e.g., chr8:127700000-128000000)."
                )
            parsed_regions.append((m.group(1).lower(), int(m.group(2)), int(m.group(3))))

    # --- Resolve cycle root directory ---
    if cycle_dir is None:
        cycle_dir = _get_default_cycle_dir()

    if not os.path.isdir(cycle_dir):
        raise FileNotFoundError(f"Cycle files directory not found at '{cycle_dir}'.")

    # --- Resolve dataset folders ---
    available_datasets = sorted(
        d for d in os.listdir(cycle_dir) if os.path.isdir(os.path.join(cycle_dir, d))
    )
    if not available_datasets:
        raise FileNotFoundError(f"No dataset subfolders found in '{cycle_dir}'.")

    if dataset is not None:
        dataset_list = [dataset] if isinstance(dataset, str) else dataset
        missing = [d for d in dataset_list if d not in available_datasets]
        if missing:
            raise FileNotFoundError(
                f"Dataset folder(s) {missing} not found in '{cycle_dir}'. "
                f"Available: {available_datasets}"
            )
        folders_to_load = dataset_list
    else:
        folders_to_load = available_datasets

    # --- Load and parse all cycle files ---
    all_rows: list[dict[str, Any]] = []
    files_loaded = 0

    for ds in folders_to_load:
        folder = os.path.join(cycle_dir, ds)
        for fname in sorted(os.listdir(folder)):
            parsed = _parse_filename(fname)
            if parsed is None:
                continue
            sname, ampnum = parsed
            fpath = os.path.join(folder, fname)
            cycles = _parse_cycle_file(fpath)
            if not cycles:
                continue
            for cycle in cycles:
                row = {
                    "dataset": ds,
                    "sample_name": sname,
                    "amplicon_number": ampnum,
                    **cycle,
                }
                all_rows.append(row)
            files_loaded += 1

    if not all_rows:
        return {
            "summary": "No cycle records found for the specified dataset(s).",
            "row_count_total": 0,
            "row_count_returned": 0,
            "filters_applied": {},
            "rows": [],
            "schema": select if select is not None else ALL_COLUMNS,
            "datasets_loaded": folders_to_load,
            "files_loaded": 0,
        }

    # --- Apply filters ---
    filters_applied: dict[str, Any] = {}
    rows = all_rows

    # Sample name filter
    if sample_name is not None:
        name_list = [sample_name] if isinstance(sample_name, str) else sample_name
        name_list_lower = [n.lower() for n in name_list]
        if sample_name_match == "exact":
            rows = [r for r in rows if r["sample_name"].lower() in name_list_lower]
        elif sample_name_match == "startswith":
            rows = [r for r in rows if any(r["sample_name"].lower().startswith(n) for n in name_list_lower)]
        else:  # contains
            rows = [r for r in rows if any(n in r["sample_name"].lower() for n in name_list_lower)]
        filters_applied["sample_name"] = sample_name
        filters_applied["sample_name_match"] = sample_name_match

    # Amplicon number filter
    if amplicon_number is not None:
        amp_list = [amplicon_number] if isinstance(amplicon_number, str) else amplicon_number
        amp_list_lower = [a.lower() for a in amp_list]
        rows = [r for r in rows if r["amplicon_number"].lower() in amp_list_lower]
        filters_applied["amplicon_number"] = amplicon_number

    # Cycle ID filter
    if cycle_id is not None:
        cid_list = [cycle_id] if isinstance(cycle_id, int) else cycle_id
        rows = [r for r in rows if r["cycle_id"] in cid_list]
        filters_applied["cycle_id"] = cycle_id

    # Cycle class filter
    if cycle_class is not None:
        cc_list = [cycle_class] if isinstance(cycle_class, str) else cycle_class
        rows = [r for r in rows if r["cycle_class"] in cc_list]
        filters_applied["cycle_class"] = cycle_class

    # Is cyclic filter
    if is_cyclic is not None:
        rows = [r for r in rows if r["is_cyclic_path"] == is_cyclic]
        filters_applied["is_cyclic"] = is_cyclic

    # Copy count filters
    if copy_count_min is not None:
        rows = [r for r in rows if r["copy_count"] >= copy_count_min]
        filters_applied["copy_count_min"] = copy_count_min
    if copy_count_max is not None:
        rows = [r for r in rows if r["copy_count"] <= copy_count_max]
        filters_applied["copy_count_max"] = copy_count_max

    # Length filters
    if length_min is not None:
        rows = [r for r in rows if r["length"] >= length_min]
        filters_applied["length_min"] = length_min
    if length_max is not None:
        rows = [r for r in rows if r["length"] <= length_max]
        filters_applied["length_max"] = length_max

    # Num segments filters
    if num_segments_min is not None:
        rows = [r for r in rows if r["num_segments"] >= num_segments_min]
        filters_applied["num_segments_min"] = num_segments_min
    if num_segments_max is not None:
        rows = [r for r in rows if r["num_segments"] <= num_segments_max]
        filters_applied["num_segments_max"] = num_segments_max

    # Chromosome filter — at least one non-zero segment on the chromosome
    if chrom is not None:
        chrom_list = [chrom] if isinstance(chrom, str) else chrom
        chrom_set = {c.lower() for c in chrom_list}
        rows = [
            r for r in rows
            if any(
                s["chrom"] is not None and s["chrom"].lower() in chrom_set
                for s in r["segments"] if s["id"] != 0
            )
        ]
        filters_applied["chrom"] = chrom

    # Genomic region filter — at least one segment overlaps any specified region
    if parsed_regions:
        rows = [
            r for r in rows
            if any(
                _segment_overlaps_region(s, chrom_r, start_r, end_r)
                for s in r["segments"]
                for chrom_r, start_r, end_r in parsed_regions
            )
        ]
        filters_applied["genomic_region"] = genomic_region

    row_count_total = len(rows)

    # --- Pagination ---
    rows = rows[offset: offset + limit] if limit is not None else rows[offset:]
    row_count_returned = len(rows)

    # --- Column selection ---
    output_columns = select if select is not None else ALL_COLUMNS
    if select is not None:
        rows = [{col: r[col] for col in select if col in r} for r in rows]

    # --- Summary ---
    filter_parts = []
    if dataset:
        filter_parts.append(f"dataset={dataset}")
    if sample_name:
        filter_parts.append(f"sample_name={sample_name}")
    if amplicon_number:
        filter_parts.append(f"amplicon_number={amplicon_number}")
    if cycle_id is not None:
        filter_parts.append(f"cycle_id={cycle_id}")
    if cycle_class:
        filter_parts.append(f"cycle_class={cycle_class}")
    if is_cyclic is not None:
        filter_parts.append(f"is_cyclic={is_cyclic}")
    if copy_count_min is not None:
        filter_parts.append(f"copy_count_min={copy_count_min}")
    if copy_count_max is not None:
        filter_parts.append(f"copy_count_max={copy_count_max}")
    if length_min is not None:
        filter_parts.append(f"length_min={length_min}")
    if length_max is not None:
        filter_parts.append(f"length_max={length_max}")
    if num_segments_min is not None:
        filter_parts.append(f"num_segments_min={num_segments_min}")
    if num_segments_max is not None:
        filter_parts.append(f"num_segments_max={num_segments_max}")
    if chrom:
        filter_parts.append(f"chrom={chrom}")
    if genomic_region is not None:
        filter_parts.append(f"genomic_region={genomic_region}")

    filter_str = ", ".join(filter_parts) if filter_parts else "no filters"
    summary = (
        f"Found {row_count_total} cycle records ({filter_str}) across {files_loaded} files "
        f"from dataset(s): {folders_to_load}. "
        f"Returning rows {offset + 1}-{offset + row_count_returned}."
    )

    return {
        "summary": summary,
        "row_count_total": row_count_total,
        "row_count_returned": row_count_returned,
        "filters_applied": filters_applied,
        "rows": rows,
        "schema": output_columns,
        "datasets_loaded": folders_to_load,
        "files_loaded": files_loaded,
    }
