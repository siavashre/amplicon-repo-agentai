"""
Amplicon SV Query Tool for querying structural variants detected by AmpliconArchitect.

Each TSV file covers one amplicon of one sample and contains SV breakpoint pairs with
type, read support, orientation, homology, and which amplicon feature types the SV
overlaps. Files are organized as:
    {sv_dir}/{dataset}/{sample_name}_{amplicon_number}_SV_summary.tsv

When querying a dataset (e.g., CCLE), all TSV files in that folder are loaded and
merged into a single table with added sample_name, amplicon_number, and dataset columns.
"""

import os
import re
from typing import Any

# Regex for chrN:start-end genomic region format
_REGION_PATTERN = re.compile(r"^(chr[0-9XYMa-z]+):(\d+)-(\d+)$", re.IGNORECASE)

import pandas as pd

try:
    from biomni.config import default_config
except Exception:
    default_config = None


ALL_COLUMNS = [
    "dataset",
    "sample_name",
    "amplicon_number",
    "chrom1",
    "pos1",
    "chrom2",
    "pos2",
    "sv_type",
    "read_support",
    "features",
    "orientation",
    "pos1_flanking_coordinate",
    "pos2_flanking_coordinate",
    "homology_length",
    "homology_sequence",
]

VALID_SV_TYPES = ["duplication-like", "deletion-like", "inversion", "foldback", "interchromosomal"]
VALID_FEATURES = ["ecDNA", "BFB", "Linear", "Complex-non-cyclic", "unknown"]
VALID_ORIENTATIONS = ["++", "+-", "-+", "--"]

# Parses {sample_name}_{amplicon_number}_SV_summary.tsv
_FILENAME_PATTERN = re.compile(r"^(.+)_(amplicon\d+)_SV_summary\.tsv$")


def _get_default_sv_dir() -> str:
    base = os.environ.get("BIOMNI_PATH") or os.environ.get("BIOMNI_DATA_PATH")
    if base is None and default_config is not None:
        base = getattr(default_config, "path", None)
    if base is None:
        base = "./data"
    return os.path.join(base, "biomni_data", "data_lake", "SV")


def _parse_filename(filename: str) -> tuple[str, str] | None:
    """Parse sample_name and amplicon_number from a SV summary filename."""
    match = _FILENAME_PATTERN.match(filename)
    if match:
        return match.group(1), match.group(2)
    return None


def _feature_matches(features_val: Any, target_features: list[str]) -> bool:
    """Check if any target feature appears in a pipe-separated features field."""
    if pd.isna(features_val) or not features_val:
        return False
    parts = {p.strip() for p in str(features_val).split("|")}
    return bool(parts & set(target_features))


def query_amplicon_svs(
    dataset: str | list[str] | None = None,
    sample_name: str | list[str] | None = None,
    sample_name_match: str | None = None,
    amplicon_number: str | list[str] | None = None,
    sv_type: str | list[str] | None = None,
    feature: str | list[str] | None = None,
    chrom: str | list[str] | None = None,
    chrom1: str | list[str] | None = None,
    chrom2: str | list[str] | None = None,
    orientation: str | list[str] | None = None,
    pos1_range: int | list[int] | None = None,
    pos2_range: int | list[int] | None = None,
    genomic_region: str | list[str] | None = None,
    read_support_min: int | None = None,
    read_support_max: int | None = None,
    homology_length_min: float | None = None,
    select: list[str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    sv_dir: str | None = None,
) -> dict[str, Any]:
    """Query and filter structural variant records from amplicon SV summary TSV files.

    Loads all TSV files from the specified dataset folder(s) and merges them into a
    single table for querying. Each row is one SV breakpoint pair within one amplicon.

    Args:
        dataset: Dataset folder name(s) to load (e.g., 'CCLE', 'TCGA', 'PCAWG').
            All TSVs in the folder are loaded together. Accepts a single value or list.
            If not specified, all available datasets are loaded.
        sample_name: Sample name(s) parsed from the filename. Accepts a single value
            or list for OR matching.
        sample_name_match: Match mode for sample_name: 'exact', 'startswith', or
            'contains' (default). Case-insensitive.
        amplicon_number: Amplicon number(s) (e.g., 'amplicon4'). Accepts a single
            value or list for OR matching.
        sv_type: SV type(s) to filter. Valid values: 'duplication-like',
            'deletion-like', 'inversion', 'foldback', 'interchromosomal'.
            Accepts a single value or list for OR matching.
        feature: Amplicon feature type(s) the SV overlaps (pipe-separated in source).
            Valid values: 'ecDNA', 'BFB', 'Linear', 'Complex-non-cyclic', 'unknown'.
            Returns rows where any of the specified features appear. Accepts a single
            value or list for OR matching.
        chrom: Chromosome(s) to filter — matches either chrom1 or chrom2.
            Accepts a single value or list for OR matching.
        chrom1: Filter specifically on chrom1. Accepts a single value or list.
        chrom2: Filter specifically on chrom2. Accepts a single value or list.
        orientation: Strand orientation of breakpoints. Valid values: '++', '+-',
            '-+', '--'. Accepts a single value or list for OR matching.
        pos1_range: Filter for pos1. Accepts an exact integer (e.g., 48905218) or a
            [min, max] range (e.g., [48000000, 49000000]). Exact value matches pos1 == value;
            range matches pos1 within [min, max] (inclusive).
        pos2_range: Filter for pos2. Accepts an exact integer (e.g., 18695135) or a
            [min, max] range (e.g., [18000000, 19000000]). Exact value matches pos2 == value;
            range matches pos2 within [min, max] (inclusive).
        genomic_region: Genomic region(s) in chrN:start-end format
            (e.g., 'chr8:48000000-49000000'). Returns SVs where either breakpoint
            (chrom1+pos1 or chrom2+pos2) falls within any of the specified regions.
            Accepts a single value or list for OR matching.
        read_support_min: Minimum read support (inclusive).
        read_support_max: Maximum read support (inclusive).
        homology_length_min: Minimum homology length at the breakpoint (inclusive).
        select: Columns to return. Defaults to all columns.
            Unknown columns will raise an error.
        limit: Maximum number of rows to return. Returns all if not specified.
        offset: Row offset for pagination (default 0).
        sv_dir: Path to the root SV directory. If not specified, uses default config path.

    Returns:
        Dictionary containing:
            - summary: Brief description of the results
            - row_count_total: Total matching rows before pagination
            - row_count_returned: Rows returned after pagination
            - filters_applied: Filters that were applied
            - rows: List of matching SV records
            - schema: Column names in the returned data
            - datasets_loaded: List of dataset folders loaded
            - files_loaded: Number of TSV files loaded

    Raises:
        FileNotFoundError: If the SV directory or dataset folder is not found
        ValueError: If invalid parameter values are provided
    """
    # Defaults
    if offset is None:
        offset = 0
    if sample_name_match is None:
        sample_name_match = "contains"
    if limit is not None:
        limit = max(1, limit)
    offset = max(0, offset)

    # Validate
    valid_match_modes = ["exact", "startswith", "contains"]
    if sample_name_match not in valid_match_modes:
        raise ValueError(f"Invalid sample_name_match '{sample_name_match}'. Must be one of: {valid_match_modes}")

    if sv_type is not None:
        svt_list = [sv_type] if isinstance(sv_type, str) else sv_type
        invalid = [v for v in svt_list if v not in VALID_SV_TYPES]
        if invalid:
            raise ValueError(f"Invalid sv_type value(s) {invalid}. Must be one of: {VALID_SV_TYPES}")

    if feature is not None:
        feat_list = [feature] if isinstance(feature, str) else feature
        invalid = [v for v in feat_list if v not in VALID_FEATURES]
        if invalid:
            raise ValueError(f"Invalid feature value(s) {invalid}. Must be one of: {VALID_FEATURES}")

    if orientation is not None:
        ori_list = [orientation] if isinstance(orientation, str) else orientation
        invalid = [v for v in ori_list if v not in VALID_ORIENTATIONS]
        if invalid:
            raise ValueError(f"Invalid orientation value(s) {invalid}. Must be one of: {VALID_ORIENTATIONS}")

    # Resolve SV root directory
    if sv_dir is None:
        sv_dir = _get_default_sv_dir()

    if not os.path.isdir(sv_dir):
        raise FileNotFoundError(f"SV directory not found at '{sv_dir}'.")

    # Resolve dataset folders to load
    available_datasets = sorted(
        d for d in os.listdir(sv_dir) if os.path.isdir(os.path.join(sv_dir, d))
    )
    if not available_datasets:
        raise FileNotFoundError(f"No dataset subfolders found in '{sv_dir}'.")

    if dataset is not None:
        dataset_list = [dataset] if isinstance(dataset, str) else dataset
        missing = [d for d in dataset_list if d not in available_datasets]
        if missing:
            raise FileNotFoundError(
                f"Dataset folder(s) {missing} not found in '{sv_dir}'. "
                f"Available: {available_datasets}"
            )
        folders_to_load = dataset_list
    else:
        folders_to_load = available_datasets

    # Load all TSV files from the selected folders
    frames = []
    files_loaded = 0
    for ds in folders_to_load:
        folder = os.path.join(sv_dir, ds)
        for fname in os.listdir(folder):
            if not fname.endswith(".tsv"):
                continue
            parsed = _parse_filename(fname)
            if parsed is None:
                continue
            sname, ampnum = parsed
            fpath = os.path.join(folder, fname)
            try:
                df_file = pd.read_csv(fpath, sep="\t")
            except Exception:
                continue
            if df_file.empty:
                continue
            df_file.insert(0, "dataset", ds)
            df_file.insert(1, "sample_name", sname)
            df_file.insert(2, "amplicon_number", ampnum)
            frames.append(df_file)
            files_loaded += 1

    if not frames:
        return {
            "summary": "No SV records found for the specified dataset(s).",
            "row_count_total": 0,
            "row_count_returned": 0,
            "filters_applied": {},
            "rows": [],
            "schema": ALL_COLUMNS,
            "datasets_loaded": folders_to_load,
            "files_loaded": 0,
        }

    df = pd.concat(frames, ignore_index=True)

    filters_applied: dict[str, Any] = {}
    mask = pd.Series([True] * len(df))

    # Sample name filter
    if sample_name is not None:
        name_list = [sample_name] if isinstance(sample_name, str) else sample_name
        name_mask = pd.Series([False] * len(df))
        col_lower = df["sample_name"].str.lower()
        if sample_name_match == "exact":
            for name in name_list:
                name_mask |= col_lower == name.lower()
        elif sample_name_match == "startswith":
            for name in name_list:
                name_mask |= col_lower.str.startswith(name.lower())
        else:
            for name in name_list:
                name_mask |= col_lower.str.contains(name.lower(), regex=False)
        mask &= name_mask
        filters_applied["sample_name"] = sample_name
        filters_applied["sample_name_match"] = sample_name_match

    # Amplicon number filter
    if amplicon_number is not None:
        amp_list = [amplicon_number] if isinstance(amplicon_number, str) else amplicon_number
        mask &= df["amplicon_number"].str.lower().isin([a.lower() for a in amp_list])
        filters_applied["amplicon_number"] = amplicon_number

    # SV type filter
    if sv_type is not None:
        svt_list = [sv_type] if isinstance(sv_type, str) else sv_type
        mask &= df["sv_type"].isin(svt_list)
        filters_applied["sv_type"] = sv_type

    # Feature overlap filter (pipe-separated values)
    if feature is not None:
        feat_list = [feature] if isinstance(feature, str) else feature
        mask &= df["features"].apply(lambda x: _feature_matches(x, feat_list))
        filters_applied["feature"] = feature

    # chrom filter (either chrom1 or chrom2)
    if chrom is not None:
        chrom_list = [chrom] if isinstance(chrom, str) else chrom
        mask &= df["chrom1"].isin(chrom_list) | df["chrom2"].isin(chrom_list)
        filters_applied["chrom"] = chrom

    # chrom1-specific filter
    if chrom1 is not None:
        c1_list = [chrom1] if isinstance(chrom1, str) else chrom1
        mask &= df["chrom1"].isin(c1_list)
        filters_applied["chrom1"] = chrom1

    # chrom2-specific filter
    if chrom2 is not None:
        c2_list = [chrom2] if isinstance(chrom2, str) else chrom2
        mask &= df["chrom2"].isin(c2_list)
        filters_applied["chrom2"] = chrom2

    # Orientation filter
    if orientation is not None:
        ori_list = [orientation] if isinstance(orientation, str) else orientation
        mask &= df["orientation"].isin(ori_list)
        filters_applied["orientation"] = orientation

    # pos1 filter (exact value or [min, max] range)
    if pos1_range is not None:
        pos1_num = pd.to_numeric(df["pos1"], errors="coerce")
        if isinstance(pos1_range, int):
            mask &= pos1_num == pos1_range
        elif len(pos1_range) == 2:
            mask &= (pos1_num >= pos1_range[0]) & (pos1_num <= pos1_range[1])
        else:
            raise ValueError("pos1_range must be an integer or a list of exactly 2 integers: [min, max].")
        filters_applied["pos1_range"] = pos1_range

    # pos2 filter (exact value or [min, max] range)
    if pos2_range is not None:
        pos2_num = pd.to_numeric(df["pos2"], errors="coerce")
        if isinstance(pos2_range, int):
            mask &= pos2_num == pos2_range
        elif len(pos2_range) == 2:
            mask &= (pos2_num >= pos2_range[0]) & (pos2_num <= pos2_range[1])
        else:
            raise ValueError("pos2_range must be an integer or a list of exactly 2 integers: [min, max].")
        filters_applied["pos2_range"] = pos2_range

    # Genomic region filter — either breakpoint falls within any specified region
    if genomic_region is not None:
        region_list = [genomic_region] if isinstance(genomic_region, str) else genomic_region
        parsed_regions = []
        for region in region_list:
            m = _REGION_PATTERN.match(region)
            if m is None:
                raise ValueError(
                    f"Invalid genomic_region format '{region}'. "
                    "Expected format: chrN:start-end (e.g., chr8:48000000-49000000)."
                )
            parsed_regions.append((m.group(1).lower(), int(m.group(2)), int(m.group(3))))

        pos1_num = pd.to_numeric(df["pos1"], errors="coerce")
        pos2_num = pd.to_numeric(df["pos2"], errors="coerce")
        region_mask = pd.Series([False] * len(df))
        for chrom_r, start_r, end_r in parsed_regions:
            bp1_match = (df["chrom1"].str.lower() == chrom_r) & (pos1_num >= start_r) & (pos1_num <= end_r)
            bp2_match = (df["chrom2"].str.lower() == chrom_r) & (pos2_num >= start_r) & (pos2_num <= end_r)
            region_mask |= bp1_match | bp2_match
        mask &= region_mask
        filters_applied["genomic_region"] = genomic_region

    # Read support filters
    if read_support_min is not None:
        mask &= pd.to_numeric(df["read_support"], errors="coerce") >= read_support_min
        filters_applied["read_support_min"] = read_support_min
    if read_support_max is not None:
        mask &= pd.to_numeric(df["read_support"], errors="coerce") <= read_support_max
        filters_applied["read_support_max"] = read_support_max

    # Homology length filter
    if homology_length_min is not None:
        mask &= pd.to_numeric(df["homology_length"], errors="coerce") >= homology_length_min
        filters_applied["homology_length_min"] = homology_length_min

    filtered_df = df[mask]
    row_count_total = len(filtered_df)

    # Pagination
    if limit is not None:
        filtered_df = filtered_df.iloc[offset : offset + limit]
    else:
        filtered_df = filtered_df.iloc[offset:]
    row_count_returned = len(filtered_df)

    # Column selection
    available_cols = list(df.columns)
    if select is not None:
        invalid_cols = [c for c in select if c not in available_cols]
        if invalid_cols:
            raise ValueError(f"Invalid columns requested: {invalid_cols}. Available: {available_cols}")
        output_columns = select
    else:
        output_columns = [c for c in ALL_COLUMNS if c in available_cols]

    rows = filtered_df[output_columns].to_dict(orient="records")

    # Summary
    filter_parts = []
    if dataset:
        filter_parts.append(f"dataset={dataset}")
    if sample_name:
        filter_parts.append(f"sample_name={sample_name}")
    if amplicon_number:
        filter_parts.append(f"amplicon_number={amplicon_number}")
    if sv_type:
        filter_parts.append(f"sv_type={sv_type}")
    if feature:
        filter_parts.append(f"feature={feature}")
    if chrom:
        filter_parts.append(f"chrom={chrom}")
    if chrom1:
        filter_parts.append(f"chrom1={chrom1}")
    if chrom2:
        filter_parts.append(f"chrom2={chrom2}")
    if orientation:
        filter_parts.append(f"orientation={orientation}")
    if pos1_range is not None:
        filter_parts.append(f"pos1_range={pos1_range}")
    if pos2_range is not None:
        filter_parts.append(f"pos2_range={pos2_range}")
    if genomic_region is not None:
        filter_parts.append(f"genomic_region={genomic_region}")
    if read_support_min is not None:
        filter_parts.append(f"read_support_min={read_support_min}")
    if read_support_max is not None:
        filter_parts.append(f"read_support_max={read_support_max}")
    if homology_length_min is not None:
        filter_parts.append(f"homology_length_min={homology_length_min}")

    filter_str = ", ".join(filter_parts) if filter_parts else "no filters"
    summary = (
        f"Found {row_count_total} SV records ({filter_str}) across {files_loaded} files "
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
