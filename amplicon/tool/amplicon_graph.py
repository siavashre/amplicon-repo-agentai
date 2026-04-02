"""
Amplicon Graph Query Tool for querying sequence and breakpoint edges from
AmpliconArchitect (AA) graph files.

Each graph file covers one amplicon of one sample and has two sections:
  1. Sequence edges: non-overlapping reference genome segments with copy number,
     coverage, size, and read counts.
  2. Breakpoint edges: connections between genomic positions, typed as discordant
     (structural variants), concordant (reference-consecutive), or source
     (connection to unknown/out-of-amplicon position).

Files are organized as:
    {graph_dir}/{dataset}/{sample_name}_{amplicon_number}_graph.txt
"""

import os
import re
from typing import Any

try:
    from amplicon.config import default_config
except Exception:
    default_config = None

_REGION_PATTERN = re.compile(r"^(chr[0-9XYMa-z]+):(\d+)-(\d+)$", re.IGNORECASE)
_FILENAME_PATTERN = re.compile(r"^(.+)_(amplicon\d+)_graph\.txt$")

# e.g. chr8:127700000+ or chr8:-1-
_VERTEX_PATTERN = re.compile(r"^(chr[0-9XYMa-z]+):(-?\d+)([+\-])$", re.IGNORECASE)

VALID_QUERY_TYPES = ["sequence", "breakpoint", "all"]
VALID_BREAKPOINT_EDGE_TYPES = ["discordant", "concordant", "source"]

SEQ_COLUMNS = [
    "dataset", "sample_name", "amplicon_number", "edge_category",
    "chrom1", "start1", "chrom2", "start2",
    "copy_count", "avg_coverage", "size", "num_reads_mapped",
]

BP_COLUMNS = [
    "dataset", "sample_name", "amplicon_number", "edge_category", "edge_type",
    "chrom1", "pos1", "strand1", "chrom2", "pos2", "strand2",
    "copy_count", "num_read_pairs", "homology_size", "homology_sequence",
]

ALL_COLUMNS = list(dict.fromkeys(SEQ_COLUMNS + BP_COLUMNS))  # union, preserving order


def _get_default_graph_dir() -> str:
    base = os.environ.get("AMPLICON_PATH") or os.environ.get("AMPLICON_DATA_PATH")
    if base is None and default_config is not None:
        base = getattr(default_config, "path", None)
    if base is None:
        base = "./data"
    return os.path.join(base, "amplicon_data", "data_lake", "graph_files")


def _parse_filename(filename: str) -> tuple[str, str] | None:
    match = _FILENAME_PATTERN.match(filename)
    if match:
        return match.group(1), match.group(2)
    return None


def _parse_vertex(vertex: str) -> tuple[str, int, str] | None:
    """Parse a breakpoint vertex string like chr8:127700000+ into (chrom, pos, strand)."""
    m = _VERTEX_PATTERN.match(vertex.strip())
    if m:
        return m.group(1), int(m.group(2)), m.group(3)
    return None


def _parse_graph_file(
    filepath: str,
    dataset: str,
    sample_name: str,
    amplicon_number: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a graph file into (sequence_edge_rows, breakpoint_edge_rows)."""
    seq_rows: list[dict[str, Any]] = []
    bp_rows: list[dict[str, Any]] = []

    section = None  # "sequence" or "breakpoint"

    try:
        with open(filepath) as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue

                # Detect section headers
                if line.startswith("SequenceEdge:"):
                    section = "sequence"
                    continue
                if line.startswith("BreakpointEdge:"):
                    section = "breakpoint"
                    continue

                parts = line.split("\t")

                if section == "sequence" and parts[0] == "sequence":
                    if len(parts) < 7:
                        continue
                    v1 = _parse_vertex(parts[1])
                    v2 = _parse_vertex(parts[2])
                    try:
                        copy_count = float(parts[3])
                        avg_coverage = float(parts[4])
                        size = int(parts[5])
                        num_reads_mapped = int(parts[6])
                    except (ValueError, IndexError):
                        continue
                    seq_rows.append({
                        "dataset": dataset,
                        "sample_name": sample_name,
                        "amplicon_number": amplicon_number,
                        "edge_category": "sequence",
                        "chrom1": v1[0] if v1 else None,
                        "start1": v1[1] if v1 else None,
                        "chrom2": v2[0] if v2 else None,
                        "start2": v2[1] if v2 else None,
                        "copy_count": copy_count,
                        "avg_coverage": avg_coverage,
                        "size": size,
                        "num_reads_mapped": num_reads_mapped,
                    })

                elif section == "breakpoint" and parts[0] in VALID_BREAKPOINT_EDGE_TYPES:
                    if len(parts) < 6:
                        continue
                    edge_type = parts[0]
                    endpoints = parts[1]  # e.g. "chr3:9521655-->chr3:9519220+"
                    # Split on "->" (handle "-->" as well)
                    ep_parts = re.split(r"->", endpoints, maxsplit=1)
                    if len(ep_parts) != 2:
                        continue
                    v1 = _parse_vertex(ep_parts[0])
                    v2 = _parse_vertex(ep_parts[1])
                    try:
                        copy_count = float(parts[2])
                        num_read_pairs = int(parts[3])
                        homology_size_raw = parts[4].strip()
                        homology_size = None if homology_size_raw == "None" else float(homology_size_raw)
                        homology_sequence_raw = parts[5].strip() if len(parts) > 5 else "None"
                        homology_sequence = None if homology_sequence_raw == "None" else homology_sequence_raw
                    except (ValueError, IndexError):
                        continue
                    bp_rows.append({
                        "dataset": dataset,
                        "sample_name": sample_name,
                        "amplicon_number": amplicon_number,
                        "edge_category": "breakpoint",
                        "edge_type": edge_type,
                        "chrom1": v1[0] if v1 else None,
                        "pos1": v1[1] if v1 else None,
                        "strand1": v1[2] if v1 else None,
                        "chrom2": v2[0] if v2 else None,
                        "pos2": v2[1] if v2 else None,
                        "strand2": v2[2] if v2 else None,
                        "copy_count": copy_count,
                        "num_read_pairs": num_read_pairs,
                        "homology_size": homology_size,
                        "homology_sequence": homology_sequence,
                    })

    except Exception:
        return [], []

    return seq_rows, bp_rows


def _seq_overlaps_region(row: dict, chrom_r: str, start_r: int, end_r: int) -> bool:
    """Return True if a sequence edge overlaps the given genomic region."""
    if row["chrom1"] is None or row["chrom1"].lower() != chrom_r:
        return False
    seg_start = min(row["start1"], row["start2"]) if row["start2"] is not None else row["start1"]
    seg_end = max(row["start1"], row["start2"]) if row["start2"] is not None else row["start1"]
    return seg_start <= end_r and seg_end >= start_r


def _bp_overlaps_region(row: dict, chrom_r: str, start_r: int, end_r: int) -> bool:
    """Return True if either breakpoint endpoint falls within the region."""
    ep1 = (
        row["chrom1"] is not None
        and row["chrom1"].lower() == chrom_r
        and row["pos1"] is not None
        and start_r <= row["pos1"] <= end_r
    )
    ep2 = (
        row["chrom2"] is not None
        and row["chrom2"].lower() == chrom_r
        and row["pos2"] is not None
        and start_r <= row["pos2"] <= end_r
    )
    return ep1 or ep2


def query_amplicon_graphs(
    dataset: str | list[str] | None = None,
    sample_name: str | list[str] | None = None,
    sample_name_match: str | None = None,
    amplicon_number: str | list[str] | None = None,
    query_type: str = "all",
    breakpoint_edge_type: str | list[str] | None = None,
    chrom: str | list[str] | None = None,
    genomic_region: str | list[str] | None = None,
    copy_count_min: float | None = None,
    copy_count_max: float | None = None,
    coverage_min: float | None = None,
    coverage_max: float | None = None,
    size_min: int | None = None,
    size_max: int | None = None,
    read_pairs_min: int | None = None,
    read_pairs_max: int | None = None,
    homology_size_min: float | None = None,
    select: list[str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    graph_dir: str | None = None,
) -> dict[str, Any]:
    """Query and filter edges from AmpliconArchitect (AA) graph files.

    Loads all graph files from the specified dataset folder(s) and returns rows
    representing sequence edges (genomic segments) and/or breakpoint edges
    (discordant structural variants, concordant reference connections, or source
    connections to unknown positions).

    Args:
        dataset: Dataset folder name(s) to load (e.g., 'CCLE'). All graph files
            in the folder are loaded together. Accepts a single value or list.
            If not specified, all available datasets are loaded.
        sample_name: Sample name(s) parsed from the filename (e.g., 'AU565_BREAST').
            Accepts a single value or list for OR matching.
        sample_name_match: Match mode for sample_name: 'exact', 'startswith', or
            'contains' (default). Case-insensitive.
        amplicon_number: Amplicon number(s) (e.g., 'amplicon1'). Parsed from the
            filename. Accepts a single value or list for OR matching.
        query_type: Which edge type to return. 'sequence' returns only sequence edges.
            'breakpoint' returns only breakpoint edges. 'all' (default) returns both,
            with an 'edge_category' column indicating 'sequence' or 'breakpoint'.
        breakpoint_edge_type: Filter breakpoint edges by type. Valid values:
            'discordant' (structural variants), 'concordant' (reference connections),
            'source' (connection to unknown/out-of-amplicon position). Accepts a single
            value or list for OR matching. Only applies to breakpoint edges.
        chrom: Chromosome(s) to filter by (e.g., 'chr8'). For sequence edges, returns
            edges on the chromosome. For breakpoint edges, returns edges where either
            endpoint is on the chromosome. Accepts a single value or list.
        genomic_region: Genomic region(s) in chrN:start-end format. For sequence edges,
            returns edges overlapping the region. For breakpoint edges, returns edges
            where either endpoint falls within the region. Accepts a single value or list.
        copy_count_min: Minimum predicted copy number (inclusive). Applies to both
            sequence and breakpoint edges.
        copy_count_max: Maximum predicted copy number (inclusive). Applies to both
            sequence and breakpoint edges.
        coverage_min: Minimum average read coverage (inclusive). Only applies to
            sequence edges.
        coverage_max: Maximum average read coverage (inclusive). Only applies to
            sequence edges.
        size_min: Minimum segment size in base pairs (inclusive). Only applies to
            sequence edges.
        size_max: Maximum segment size in base pairs (inclusive). Only applies to
            sequence edges.
        read_pairs_min: Minimum number of supporting read pairs (inclusive). Only
            applies to breakpoint edges.
        read_pairs_max: Maximum number of supporting read pairs (inclusive). Only
            applies to breakpoint edges.
        homology_size_min: Minimum homology size at breakpoint (inclusive). Negative
            values indicate insertions. Only applies to breakpoint edges. Rows with
            None homology size are excluded.
        select: Columns to return. For sequence edges: dataset, sample_name,
            amplicon_number, edge_category, chrom1, start1, chrom2, start2,
            copy_count, avg_coverage, size, num_reads_mapped. For breakpoint edges:
            dataset, sample_name, amplicon_number, edge_category, edge_type,
            chrom1, pos1, strand1, chrom2, pos2, strand2, copy_count, num_read_pairs,
            homology_size, homology_sequence. Use exact column names.
        limit: Maximum number of rows to return. Returns all if not specified.
        offset: Row offset for pagination (default 0).
        graph_dir: Path to the root graph files directory. If not specified, uses
            the default config path.

    Returns:
        Dictionary containing:
            - summary: Brief description of the results
            - row_count_total: Total matching rows before pagination
            - row_count_returned: Rows returned after pagination
            - filters_applied: Filters that were applied
            - rows: List of matching edge records
            - schema: Column names in the returned data
            - datasets_loaded: List of dataset folders loaded
            - files_loaded: Number of graph files loaded

    Raises:
        FileNotFoundError: If the graph directory or dataset folder is not found.
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
        raise ValueError(f"Invalid sample_name_match '{sample_name_match}'. Must be one of: {valid_match_modes}")

    if query_type not in VALID_QUERY_TYPES:
        raise ValueError(f"Invalid query_type '{query_type}'. Must be one of: {VALID_QUERY_TYPES}")

    if breakpoint_edge_type is not None:
        bp_type_list = [breakpoint_edge_type] if isinstance(breakpoint_edge_type, str) else breakpoint_edge_type
        invalid = [v for v in bp_type_list if v not in VALID_BREAKPOINT_EDGE_TYPES]
        if invalid:
            raise ValueError(f"Invalid breakpoint_edge_type value(s) {invalid}. Must be one of: {VALID_BREAKPOINT_EDGE_TYPES}")

    # Parse genomic regions early to catch format errors
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

    # --- Resolve graph root directory ---
    if graph_dir is None:
        graph_dir = _get_default_graph_dir()

    if not os.path.isdir(graph_dir):
        raise FileNotFoundError(f"Graph files directory not found at '{graph_dir}'.")

    # --- Resolve dataset folders ---
    available_datasets = sorted(
        d for d in os.listdir(graph_dir) if os.path.isdir(os.path.join(graph_dir, d))
    )
    if not available_datasets:
        raise FileNotFoundError(f"No dataset subfolders found in '{graph_dir}'.")

    if dataset is not None:
        dataset_list = [dataset] if isinstance(dataset, str) else dataset
        missing = [d for d in dataset_list if d not in available_datasets]
        if missing:
            raise FileNotFoundError(
                f"Dataset folder(s) {missing} not found in '{graph_dir}'. "
                f"Available: {available_datasets}"
            )
        folders_to_load = dataset_list
    else:
        folders_to_load = available_datasets

    # --- Load and parse all graph files ---
    all_seq: list[dict[str, Any]] = []
    all_bp: list[dict[str, Any]] = []
    files_loaded = 0

    for ds in folders_to_load:
        folder = os.path.join(graph_dir, ds)
        for fname in sorted(os.listdir(folder)):
            parsed = _parse_filename(fname)
            if parsed is None:
                continue
            sname, ampnum = parsed
            fpath = os.path.join(folder, fname)
            seq_rows, bp_rows = _parse_graph_file(fpath, ds, sname, ampnum)
            if seq_rows or bp_rows:
                all_seq.extend(seq_rows)
                all_bp.extend(bp_rows)
                files_loaded += 1

    # Select rows based on query_type
    if query_type == "sequence":
        rows = all_seq
    elif query_type == "breakpoint":
        rows = all_bp
    else:
        rows = all_seq + all_bp

    if not rows:
        return {
            "summary": "No graph records found for the specified dataset(s).",
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

    # Sample name filter
    if sample_name is not None:
        name_list_lower = [
            (sample_name if isinstance(sample_name, str) else sample_name)
        ]
        name_list_lower = [n.lower() for n in ([sample_name] if isinstance(sample_name, str) else sample_name)]
        if sample_name_match == "exact":
            rows = [r for r in rows if r["sample_name"].lower() in name_list_lower]
        elif sample_name_match == "startswith":
            rows = [r for r in rows if any(r["sample_name"].lower().startswith(n) for n in name_list_lower)]
        else:
            rows = [r for r in rows if any(n in r["sample_name"].lower() for n in name_list_lower)]
        filters_applied["sample_name"] = sample_name
        filters_applied["sample_name_match"] = sample_name_match

    # Amplicon number filter
    if amplicon_number is not None:
        amp_list = [amplicon_number] if isinstance(amplicon_number, str) else amplicon_number
        amp_list_lower = [a.lower() for a in amp_list]
        rows = [r for r in rows if r["amplicon_number"].lower() in amp_list_lower]
        filters_applied["amplicon_number"] = amplicon_number

    # Breakpoint edge type filter
    if breakpoint_edge_type is not None:
        bp_type_list = [breakpoint_edge_type] if isinstance(breakpoint_edge_type, str) else breakpoint_edge_type
        rows = [r for r in rows if r.get("edge_type") in bp_type_list or r["edge_category"] == "sequence"]
        # If query_type is breakpoint, sequence rows won't be present anyway
        if query_type == "breakpoint":
            rows = [r for r in rows if r.get("edge_type") in bp_type_list]
        filters_applied["breakpoint_edge_type"] = breakpoint_edge_type

    # Chromosome filter
    if chrom is not None:
        chrom_list = {c.lower() for c in ([chrom] if isinstance(chrom, str) else chrom)}
        def _chrom_match(r):
            if r["edge_category"] == "sequence":
                return r["chrom1"] is not None and r["chrom1"].lower() in chrom_list
            else:
                c1 = r["chrom1"] is not None and r["chrom1"].lower() in chrom_list
                c2 = r["chrom2"] is not None and r["chrom2"].lower() in chrom_list
                return c1 or c2
        rows = [r for r in rows if _chrom_match(r)]
        filters_applied["chrom"] = chrom

    # Genomic region filter
    if parsed_regions:
        def _region_match(r):
            for chrom_r, start_r, end_r in parsed_regions:
                if r["edge_category"] == "sequence":
                    if _seq_overlaps_region(r, chrom_r, start_r, end_r):
                        return True
                else:
                    if _bp_overlaps_region(r, chrom_r, start_r, end_r):
                        return True
            return False
        rows = [r for r in rows if _region_match(r)]
        filters_applied["genomic_region"] = genomic_region

    # Copy count filters (both edge types)
    if copy_count_min is not None:
        rows = [r for r in rows if r["copy_count"] >= copy_count_min]
        filters_applied["copy_count_min"] = copy_count_min
    if copy_count_max is not None:
        rows = [r for r in rows if r["copy_count"] <= copy_count_max]
        filters_applied["copy_count_max"] = copy_count_max

    # Sequence-edge-only filters
    if coverage_min is not None:
        rows = [r for r in rows if r["edge_category"] != "sequence" or r["avg_coverage"] >= coverage_min]
        filters_applied["coverage_min"] = coverage_min
    if coverage_max is not None:
        rows = [r for r in rows if r["edge_category"] != "sequence" or r["avg_coverage"] <= coverage_max]
        filters_applied["coverage_max"] = coverage_max
    if size_min is not None:
        rows = [r for r in rows if r["edge_category"] != "sequence" or r["size"] >= size_min]
        filters_applied["size_min"] = size_min
    if size_max is not None:
        rows = [r for r in rows if r["edge_category"] != "sequence" or r["size"] <= size_max]
        filters_applied["size_max"] = size_max

    # Breakpoint-edge-only filters
    if read_pairs_min is not None:
        rows = [r for r in rows if r["edge_category"] != "breakpoint" or (r["num_read_pairs"] is not None and r["num_read_pairs"] >= read_pairs_min)]
        filters_applied["read_pairs_min"] = read_pairs_min
    if read_pairs_max is not None:
        rows = [r for r in rows if r["edge_category"] != "breakpoint" or (r["num_read_pairs"] is not None and r["num_read_pairs"] <= read_pairs_max)]
        filters_applied["read_pairs_max"] = read_pairs_max
    if homology_size_min is not None:
        rows = [r for r in rows if r["edge_category"] != "breakpoint" or (r["homology_size"] is not None and r["homology_size"] >= homology_size_min)]
        filters_applied["homology_size_min"] = homology_size_min

    row_count_total = len(rows)

    # --- Pagination ---
    rows = rows[offset: offset + limit] if limit is not None else rows[offset:]
    row_count_returned = len(rows)

    # --- Column selection ---
    if select is not None:
        invalid_cols = [c for c in select if c not in ALL_COLUMNS]
        if invalid_cols:
            raise ValueError(f"Invalid columns requested: {invalid_cols}. Available: {ALL_COLUMNS}")
        rows = [{col: r.get(col) for col in select} for r in rows]
        output_columns = select
    else:
        output_columns = ALL_COLUMNS

    # --- Summary ---
    filter_parts = []
    if dataset:
        filter_parts.append(f"dataset={dataset}")
    if sample_name:
        filter_parts.append(f"sample_name={sample_name}")
    if amplicon_number:
        filter_parts.append(f"amplicon_number={amplicon_number}")
    if query_type != "all":
        filter_parts.append(f"query_type={query_type}")
    if breakpoint_edge_type:
        filter_parts.append(f"breakpoint_edge_type={breakpoint_edge_type}")
    if chrom:
        filter_parts.append(f"chrom={chrom}")
    if genomic_region:
        filter_parts.append(f"genomic_region={genomic_region}")
    if copy_count_min is not None:
        filter_parts.append(f"copy_count_min={copy_count_min}")
    if copy_count_max is not None:
        filter_parts.append(f"copy_count_max={copy_count_max}")
    if coverage_min is not None:
        filter_parts.append(f"coverage_min={coverage_min}")
    if coverage_max is not None:
        filter_parts.append(f"coverage_max={coverage_max}")
    if size_min is not None:
        filter_parts.append(f"size_min={size_min}")
    if size_max is not None:
        filter_parts.append(f"size_max={size_max}")
    if read_pairs_min is not None:
        filter_parts.append(f"read_pairs_min={read_pairs_min}")
    if read_pairs_max is not None:
        filter_parts.append(f"read_pairs_max={read_pairs_max}")
    if homology_size_min is not None:
        filter_parts.append(f"homology_size_min={homology_size_min}")

    filter_str = ", ".join(filter_parts) if filter_parts else "no filters"
    summary = (
        f"Found {row_count_total} edge records ({filter_str}) across {files_loaded} files "
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
