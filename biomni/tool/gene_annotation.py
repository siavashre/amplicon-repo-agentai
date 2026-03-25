"""
Gene Annotation Tool for retrieving genomic coordinates from GENCODE GTF files.

Supports hg38 (GENCODE v47) and hg19 (GENCODE v19) reference genomes.
On first use, parses the GTF and caches a parquet file for fast subsequent lookups.

Files expected at:
    {genes_dir}/hg38.gtf.gz
    {genes_dir}/hg19.gtf.gz

Cached TSV files written to (built on first use):
    {genes_dir}/hg38_gene.tsv.gz
    {genes_dir}/hg38_transcript.tsv.gz
    {genes_dir}/hg19_gene.tsv.gz
    {genes_dir}/hg19_transcript.tsv.gz
"""

import gzip
import os
import re
from typing import Any

import pandas as pd

try:
    from biomni.config import default_config
except Exception:
    default_config = None

VALID_GENOMES = ["hg38", "hg19"]
VALID_TRANSCRIPT_MODES = ["primary", "all"]

ALL_GENE_COLUMNS = [
    "gene_name",
    "gene_id",
    "chrom",
    "start",
    "end",
    "strand",
    "gene_type",
    "reference_genome",
]

ALL_TRANSCRIPT_COLUMNS = [
    "gene_name",
    "gene_id",
    "transcript_id",
    "transcript_name",
    "transcript_type",
    "is_primary",
    "chrom",
    "start",
    "end",
    "strand",
    "reference_genome",
]


def _get_default_genes_dir() -> str:
    base = os.environ.get("BIOMNI_PATH") or os.environ.get("BIOMNI_DATA_PATH")
    if base is None and default_config is not None:
        base = getattr(default_config, "path", None)
    if base is None:
        base = "./data"
    return os.path.join(base, "biomni_data", "data_lake", "genes")


def _parse_attr(attr_str: str, key: str) -> str:
    """Extract a value from a GTF attributes string."""
    match = re.search(rf'{key} "([^"]+)"', attr_str)
    return match.group(1) if match else ""


def _build_cache(gtf_path: str, genome: str, cache_path: str) -> pd.DataFrame:
    """Parse GTF file and build a gene+transcript annotation dataframe, saved as parquet."""
    gene_rows = []
    transcript_rows = []

    opener = gzip.open if gtf_path.endswith(".gz") else open

    with opener(gtf_path, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue

            chrom, _, feature, start, end, _, strand, _, attrs = parts

            if feature == "gene":
                gene_name = _parse_attr(attrs, "gene_name")
                gene_id = _parse_attr(attrs, "gene_id")
                gene_type = _parse_attr(attrs, "gene_type")
                if gene_name:
                    gene_rows.append({
                        "gene_name": gene_name,
                        "gene_id": gene_id,
                        "chrom": chrom,
                        "start": int(start),
                        "end": int(end),
                        "strand": strand,
                        "gene_type": gene_type,
                        "reference_genome": genome,
                    })

            elif feature == "transcript":
                gene_name = _parse_attr(attrs, "gene_name")
                gene_id = _parse_attr(attrs, "gene_id")
                transcript_id = _parse_attr(attrs, "transcript_id")
                transcript_name = _parse_attr(attrs, "transcript_name")
                transcript_type = _parse_attr(attrs, "transcript_type")
                tags = attrs  # check for MANE_Select or Ensembl_canonical tag
                is_primary = (
                    "MANE_Select" in tags
                    or "Ensembl_canonical" in tags
                    or "basic" in tags
                )
                if gene_name and transcript_id:
                    transcript_rows.append({
                        "gene_name": gene_name,
                        "gene_id": gene_id,
                        "transcript_id": transcript_id,
                        "transcript_name": transcript_name,
                        "transcript_type": transcript_type,
                        "is_primary": is_primary,
                        "chrom": chrom,
                        "start": int(start),
                        "end": int(end),
                        "strand": strand,
                        "reference_genome": genome,
                    })

    genes_df = pd.DataFrame(gene_rows)
    transcripts_df = pd.DataFrame(transcript_rows)

    # Save as TSV cache (no extra dependencies)
    genes_cache = cache_path.replace(".parquet", "_gene.tsv.gz")
    transcripts_cache = cache_path.replace(".parquet", "_transcript.tsv.gz")
    genes_df.to_csv(genes_cache, sep="\t", index=False)
    transcripts_df.to_csv(transcripts_cache, sep="\t", index=False)

    return genes_df, transcripts_df


def _load_annotation(genome: str, genes_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load gene/transcript annotations from parquet cache or parse GTF if not cached."""
    cache_base = os.path.join(genes_dir, f"{genome}.parquet")
    genes_cache = cache_base.replace(".parquet", "_gene.tsv.gz")
    transcripts_cache = cache_base.replace(".parquet", "_transcript.tsv.gz")

    if os.path.exists(genes_cache) and os.path.exists(transcripts_cache):
        return pd.read_csv(genes_cache, sep="\t"), pd.read_csv(transcripts_cache, sep="\t")

    gtf_path = os.path.join(genes_dir, f"{genome}.gtf.gz")
    if not os.path.exists(gtf_path):
        gtf_path_unzipped = os.path.join(genes_dir, f"{genome}.gtf")
        if not os.path.exists(gtf_path_unzipped):
            raise FileNotFoundError(
                f"GTF file not found for {genome}. Expected at '{gtf_path}' or '{gtf_path_unzipped}'."
            )
        gtf_path = gtf_path_unzipped

    return _build_cache(gtf_path, genome, cache_base)


def query_gene_coordinates(
    gene_name: str | list[str],
    reference_genome: str = "hg38",
    transcript_mode: str = "primary",
    gene_type: str | list[str] | None = None,
    select: list[str] | None = None,
    genes_dir: str | None = None,
) -> dict[str, Any]:
    """Retrieve genomic coordinates for one or more genes from GENCODE annotations.

    Looks up gene coordinates (and optionally transcript coordinates) by gene symbol
    in local GENCODE GTF files for hg38 or hg19. On first use, parses the GTF and
    caches a parquet file for fast subsequent lookups.

    Args:
        gene_name: Gene symbol(s) to query (e.g., 'MYC' or ['MYC', 'EGFR', 'KRAS']).
            Case-sensitive. Raises an error if a gene is not found.
        reference_genome: Reference genome version. Valid values: 'hg38' (default),
            'hg19'.
        transcript_mode: Which transcripts to return. 'primary' (default) returns only
            the canonical/MANE Select transcript per gene. 'all' returns all transcripts.
            Gene-level coordinates (spanning all transcripts) are always included.
        gene_type: Optional filter by gene biotype (e.g., 'protein_coding', 'lncRNA').
            Accepts a single value or list for OR matching.
        select: Columns to return in the transcript output. Defaults to all columns:
            gene_name, gene_id, transcript_id, transcript_name, transcript_type,
            is_primary, chrom, start, end, strand, reference_genome.
            For gene-level output the columns are: gene_name, gene_id, chrom, start,
            end, strand, gene_type, reference_genome. Use exact column names.
        genes_dir: Path to the directory containing GTF and parquet files. If not
            specified, uses the default config path.

    Returns:
        Dictionary containing:
            - summary: Brief description of results
            - genes: List of gene-level records (one per queried gene) with chrom,
              start, end, strand, gene_id, gene_type
            - transcripts: List of transcript records filtered by transcript_mode.
              Each record has full coordinates plus is_primary flag.
            - not_found: List of gene names that were not found in the annotation
            - reference_genome: Genome version used
            - transcript_mode: Transcript mode used

    Raises:
        FileNotFoundError: If the GTF or parquet file is not found.
        ValueError: If invalid parameter values are provided or any gene is not found.
    """
    # --- Validate ---
    if reference_genome not in VALID_GENOMES:
        raise ValueError(
            f"Invalid reference_genome '{reference_genome}'. Must be one of: {VALID_GENOMES}"
        )
    if transcript_mode not in VALID_TRANSCRIPT_MODES:
        raise ValueError(
            f"Invalid transcript_mode '{transcript_mode}'. Must be one of: {VALID_TRANSCRIPT_MODES}"
        )

    gene_list = [gene_name] if isinstance(gene_name, str) else list(gene_name)
    if not gene_list:
        raise ValueError("gene_name must not be empty.")

    # --- Resolve directory ---
    if genes_dir is None:
        genes_dir = _get_default_genes_dir()
    if not os.path.isdir(genes_dir):
        raise FileNotFoundError(f"Genes directory not found at '{genes_dir}'.")

    # --- Load annotation (from cache or GTF) ---
    genes_df, transcripts_df = _load_annotation(reference_genome, genes_dir)

    # --- Gene-level query ---
    gene_type_list = None
    if gene_type is not None:
        gene_type_list = [gene_type] if isinstance(gene_type, str) else gene_type

    gene_results = []
    not_found = []

    for gname in gene_list:
        matches = genes_df[genes_df["gene_name"] == gname]
        if gene_type_list is not None:
            matches = matches[matches["gene_type"].isin(gene_type_list)]
        if matches.empty:
            not_found.append(gname)
        else:
            gene_results.extend(matches.to_dict(orient="records"))

    if not_found:
        raise ValueError(
            f"Gene(s) not found in {reference_genome} annotation: {not_found}. "
            "Check spelling and case (gene names are case-sensitive)."
        )

    # --- Transcript-level query ---
    transcript_results = []
    for gname in gene_list:
        t_matches = transcripts_df[transcripts_df["gene_name"] == gname]
        if transcript_mode == "primary":
            primary = t_matches[t_matches["is_primary"]]
            # Fall back to first transcript if no primary found
            t_matches = primary if not primary.empty else t_matches.head(1)
        if gene_type_list is not None:
            t_matches = t_matches[t_matches["transcript_type"].isin(gene_type_list)]
        transcript_results.extend(t_matches.to_dict(orient="records"))

    # --- Column selection for transcripts ---
    if select is not None:
        valid_cols = ALL_TRANSCRIPT_COLUMNS
        invalid = [c for c in select if c not in valid_cols]
        if invalid:
            raise ValueError(
                f"Invalid columns requested: {invalid}. Available: {valid_cols}"
            )
        transcript_results = [{c: r[c] for c in select if c in r} for r in transcript_results]

    # --- Summary ---
    summary = (
        f"Found {len(gene_results)} gene record(s) and {len(transcript_results)} "
        f"transcript record(s) for {len(gene_list)} gene(s) in {reference_genome} "
        f"(transcript_mode='{transcript_mode}')."
    )

    return {
        "summary": summary,
        "genes": gene_results,
        "transcripts": transcript_results,
        "not_found": not_found,
        "reference_genome": reference_genome,
        "transcript_mode": transcript_mode,
    }
