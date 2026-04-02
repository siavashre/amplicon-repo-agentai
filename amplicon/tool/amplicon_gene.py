"""
Amplicon Gene Query Tool for querying per-gene amplicon data.

This module provides a function to retrieve gene-level records from an amplicon
gene list TSV file, where each row represents one gene within one feature
(e.g., ecDNA_1, BFB_2) of one amplicon. Supports filtering by sample, amplicon,
feature, gene symbol, NCBI ID, copy number, oncogene status, and truncation status.
"""

import os
from typing import Any

import pandas as pd

try:
    from amplicon.config import default_config
except Exception:
    default_config = None


# All columns in the TSV schema
ALL_COLUMNS = [
    "sample_name",
    "amplicon_number",
    "feature",
    "gene",
    "gene_cn",
    "truncated",
    "is_canonical_oncogene",
    "ncbi_id",
]


def _get_default_tsv_path() -> str | None:
    """Resolve the default TSV path from config or environment."""
    base = os.environ.get("AMPLICON_PATH") or os.environ.get("AMPLICON_DATA_PATH")
    if base is None and default_config is not None:
        base = getattr(default_config, "path", None)
    if base is None:
        base = "./data"
    return os.path.join(base, "amplicon_data", "data_lake", "gene_list", "CCLE_gene_list.tsv")


def query_amplicon_genes(
    sample_name: str | list[str] | None = None,
    sample_name_match: str | None = None,
    amplicon_number: str | list[str] | None = None,
    feature: str | list[str] | None = None,
    feature_type: str | list[str] | None = None,
    gene: str | list[str] | None = None,
    ncbi_id: str | list[str] | None = None,
    is_canonical_oncogene: bool | None = None,
    is_truncated: bool | None = None,
    truncated: str | list[str] | None = None,
    gene_cn_min: float | None = None,
    gene_cn_max: float | None = None,
    select: list[str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    tsv_path: str | None = None,
) -> dict[str, Any]:
    """Query and filter gene-level records from an amplicon gene list TSV file.

    Each row represents one gene within one feature (e.g., ecDNA_1, BFB_2) of
    one amplicon. Use this tool to answer questions about which genes are amplified
    within specific features, co-amplification patterns, copy number of individual
    genes, oncogene content, or NCBI ID-based lookups.

    Args:
        sample_name: Sample name(s) to filter (e.g., '5637_URINARY_TRACT').
            Accepts a single value or list for OR matching.
        sample_name_match: Match mode for sample_name: 'exact', 'startswith',
            or 'contains' (default). Case-insensitive.
        amplicon_number: Amplicon number(s) to filter (e.g., 'amplicon1').
            Accepts a single value or list for OR matching.
        feature: Feature name(s) to filter (e.g., 'ecDNA_1', 'BFB_2').
            Accepts a single value or list for OR matching.
        feature_type: Filter by feature type prefix (e.g., 'ecDNA' matches
            ecDNA_1, ecDNA_2, etc.). Accepts a single value or list for OR matching.
            Valid values: 'ecDNA', 'BFB', 'Linear', 'Complex-non-cyclic'.
        gene: Gene symbol(s) to filter by (e.g., 'EGFR' or ['MYC', 'EGFR']).
            Case-insensitive exact match. OR logic across multiple values.
        ncbi_id: NCBI transcript/gene ID(s) to filter by. OR logic.
        is_canonical_oncogene: If True, return only canonical oncogenes.
            If False, return only non-oncogenes. Omit to return all.
        is_truncated: Filter by truncation status. The truncated column indicates
            which end(s) of the gene have been lost: None (not truncated),
            '5p' (5-prime end lost), '3p' (3-prime end lost), or '5p_3p' (both
            ends lost). If True, return only genes with any truncation (5p, 3p,
            or 5p_3p). If False, return only non-truncated genes (None).
            Omit to return all.
        truncated: Filter by specific truncation type(s). Accepts a single value
            or a list for OR matching. Valid values: '5p', '3p', '5p_3p'.
            Example: truncated='3p' returns only genes truncated at the 3-prime end.
        gene_cn_min: Minimum per-gene copy number (inclusive).
        gene_cn_max: Maximum per-gene copy number (inclusive).
        select: Columns to return. Defaults to all columns:
            sample_name, amplicon_number, feature, gene, gene_cn,
            truncated, is_canonical_oncogene, ncbi_id.
            Unknown columns will raise an error.
        limit: Maximum number of rows to return. Returns all if not specified.
        offset: Row offset for pagination (default 0).
        tsv_path: Path to the amplicon gene list TSV file. If not specified,
            uses the default config path.

    Returns:
        Dictionary containing:
            - summary: Brief description of the results
            - row_count_total: Total matching rows before pagination
            - row_count_returned: Rows returned after pagination
            - filters_applied: Filters that were applied
            - rows: List of matching gene-level records
            - schema: Column names in the returned data

    Raises:
        FileNotFoundError: If the TSV file is not found
        ValueError: If invalid parameter values are provided
    """
    # Set defaults
    if offset is None:
        offset = 0
    if sample_name_match is None:
        sample_name_match = "contains"

    # Validate parameters
    if limit is not None:
        limit = max(1, limit)
    offset = max(0, offset)

    valid_sample_name_match = ["exact", "startswith", "contains"]
    if sample_name_match not in valid_sample_name_match:
        raise ValueError(
            f"Invalid sample_name_match '{sample_name_match}'. Must be one of: {valid_sample_name_match}"
        )

    valid_feature_types = ["ecDNA", "BFB", "Linear", "Complex-non-cyclic"]
    if feature_type is not None:
        ft_list = [feature_type] if isinstance(feature_type, str) else feature_type
        invalid = [ft for ft in ft_list if ft not in valid_feature_types]
        if invalid:
            raise ValueError(f"Invalid feature_type value(s) {invalid}. Must be one of: {valid_feature_types}")

    valid_truncated_values = ["5p", "3p", "5p_3p"]
    if truncated is not None:
        trunc_list = [truncated] if isinstance(truncated, str) else truncated
        invalid = [t for t in trunc_list if t not in valid_truncated_values]
        if invalid:
            raise ValueError(f"Invalid truncated value(s) {invalid}. Must be one of: {valid_truncated_values}")

    # Resolve TSV path
    if tsv_path is None:
        tsv_path = _get_default_tsv_path()

    if not os.path.exists(tsv_path):
        raise FileNotFoundError(
            f"Amplicon gene list file not found at '{tsv_path}'. "
            "Please ensure the file is available or specify a path using the tsv_path parameter."
        )

    # Load the TSV file
    df = pd.read_csv(tsv_path, sep="\t")

    # Normalize column names to lower snake_case if needed
    df.columns = [col.strip() for col in df.columns]

    filters_applied: dict[str, Any] = {}
    mask = pd.Series([True] * len(df))

    # Sample name filter
    if sample_name is not None:
        col = "sample_name"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        name_list = [sample_name] if isinstance(sample_name, str) else sample_name
        name_mask = pd.Series([False] * len(df))
        col_lower = df[col].str.lower()
        if sample_name_match == "exact":
            for name in name_list:
                name_mask |= col_lower == name.lower()
        elif sample_name_match == "startswith":
            for name in name_list:
                name_mask |= col_lower.str.startswith(name.lower())
        else:  # contains
            for name in name_list:
                name_mask |= col_lower.str.contains(name.lower(), regex=False)
        mask &= name_mask
        filters_applied["sample_name"] = sample_name
        filters_applied["sample_name_match"] = sample_name_match

    # Amplicon number filter
    if amplicon_number is not None:
        col = "amplicon_number"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        amp_list = [amplicon_number] if isinstance(amplicon_number, str) else amplicon_number
        amp_list_lower = [a.lower() for a in amp_list]
        mask &= df[col].str.lower().isin(amp_list_lower)
        filters_applied["amplicon_number"] = amplicon_number

    # Feature filter (exact name match, e.g., 'ecDNA_1')
    if feature is not None:
        col = "feature"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        feat_list = [feature] if isinstance(feature, str) else feature
        feat_list_lower = [f.lower() for f in feat_list]
        mask &= df[col].str.lower().isin(feat_list_lower)
        filters_applied["feature"] = feature

    # Feature type filter (prefix match, e.g., 'ecDNA' matches 'ecDNA_1')
    if feature_type is not None:
        col = "feature"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        ft_list = [feature_type] if isinstance(feature_type, str) else feature_type
        ft_mask = pd.Series([False] * len(df))
        for ft in ft_list:
            # Match prefix: ecDNA_1, ecDNA_2, etc.
            ft_mask |= df[col].str.lower().str.startswith(ft.lower() + "_") | (
                df[col].str.lower() == ft.lower()
            )
        mask &= ft_mask
        filters_applied["feature_type"] = feature_type

    # Gene symbol filter (case-insensitive exact match)
    if gene is not None:
        col = "gene"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        gene_list = [gene] if isinstance(gene, str) else gene
        gene_list_upper = [g.upper() for g in gene_list]
        mask &= df[col].str.upper().isin(gene_list_upper)
        filters_applied["gene"] = gene

    # NCBI ID filter
    if ncbi_id is not None:
        col = "ncbi_id"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        ncbi_list = [ncbi_id] if isinstance(ncbi_id, str) else ncbi_id
        ncbi_list_lower = [n.lower() for n in ncbi_list]
        mask &= df[col].astype(str).str.lower().isin(ncbi_list_lower)
        filters_applied["ncbi_id"] = ncbi_id

    # Oncogene boolean filter
    if is_canonical_oncogene is not None:
        col = "is_canonical_oncogene"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        if is_canonical_oncogene:
            mask &= df[col].astype(bool)
        else:
            mask &= ~df[col].astype(bool)
        filters_applied["is_canonical_oncogene"] = is_canonical_oncogene

    # Truncated filter: column contains nan (not truncated) or a truncation type string
    # ('3p', '5p', '5p_3p', etc.). is_truncated=True means any non-null value.
    if is_truncated is not None:
        col = "truncated"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        has_truncation = df[col].notna() & (df[col].astype(str).str.lower() != "nan")
        if is_truncated:
            mask &= has_truncation
        else:
            mask &= ~has_truncation
        filters_applied["is_truncated"] = is_truncated

    # Specific truncation type filter (e.g., '3p', '5p', '5p_3p')
    if truncated is not None:
        col = "truncated"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        trunc_list = [truncated] if isinstance(truncated, str) else truncated
        mask &= df[col].isin(trunc_list)
        filters_applied["truncated"] = truncated

    # Gene copy number range filters
    if gene_cn_min is not None or gene_cn_max is not None:
        col = "gene_cn"
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in the data")
        numeric_cn = pd.to_numeric(df[col], errors="coerce")
        if gene_cn_min is not None:
            mask &= numeric_cn >= gene_cn_min
            filters_applied["gene_cn_min"] = gene_cn_min
        if gene_cn_max is not None:
            mask &= numeric_cn <= gene_cn_max
            filters_applied["gene_cn_max"] = gene_cn_max

    # Apply filter mask
    filtered_df = df[mask]
    row_count_total = len(filtered_df)

    # Pagination
    if limit is not None:
        filtered_df = filtered_df.iloc[offset : offset + limit]
    else:
        filtered_df = filtered_df.iloc[offset:]
    row_count_returned = len(filtered_df)

    # Column selection
    if select is not None:
        invalid_cols = [col for col in select if col not in df.columns]
        if invalid_cols:
            raise ValueError(f"Invalid columns requested: {invalid_cols}. Available columns: {list(df.columns)}")
        output_columns = select
    else:
        output_columns = [col for col in ALL_COLUMNS if col in df.columns]
        if not output_columns:
            output_columns = list(df.columns)

    rows = filtered_df[output_columns].to_dict(orient="records")

    # Build summary
    filter_parts = []
    if sample_name:
        filter_parts.append(f"sample_name={sample_name}")
    if amplicon_number:
        filter_parts.append(f"amplicon_number={amplicon_number}")
    if feature:
        filter_parts.append(f"feature={feature}")
    if feature_type:
        filter_parts.append(f"feature_type={feature_type}")
    if gene:
        gene_str = gene if isinstance(gene, str) else ",".join(gene)
        filter_parts.append(f"gene={gene_str}")
    if ncbi_id:
        filter_parts.append(f"ncbi_id={ncbi_id}")
    if is_canonical_oncogene is not None:
        filter_parts.append(f"is_canonical_oncogene={is_canonical_oncogene}")
    if is_truncated is not None:
        filter_parts.append(f"is_truncated={is_truncated}")
    if truncated is not None:
        filter_parts.append(f"truncated={truncated}")
    if gene_cn_min is not None:
        filter_parts.append(f"gene_cn_min={gene_cn_min}")
    if gene_cn_max is not None:
        filter_parts.append(f"gene_cn_max={gene_cn_max}")

    filter_str = ", ".join(filter_parts) if filter_parts else "no filters"
    summary = (
        f"Found {row_count_total} gene records ({filter_str}). "
        f"Returning rows {offset + 1}-{offset + row_count_returned}."
    )

    return {
        "summary": summary,
        "row_count_total": row_count_total,
        "row_count_returned": row_count_returned,
        "filters_applied": filters_applied,
        "rows": rows,
        "schema": output_columns,
    }
