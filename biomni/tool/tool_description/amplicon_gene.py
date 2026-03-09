# biomni/tool_desc/amplicon_gene.py

description = [
    {
        "name": "query_amplicon_genes",
        "description": (
            "Query and filter gene-level records from an amplicon gene list TSV file. "
            "This tool provides per-gene detail within amplicon features, including gene symbol, "
            "per-gene copy number, truncation status, oncogene status, and NCBI transcript ID. "
            "Each row represents one gene within one feature (e.g., ecDNA_1, BFB_2) of one amplicon. "
            "Use this tool to answer questions about which genes are amplified within specific features, "
            "co-amplification patterns within a feature, copy number of individual genes, oncogene content "
            "of amplicons, or NCBI ID-based gene lookups. "
            "Use tsv_path to specify any compatible amplicon gene list TSV file (e.g., CCLE_gene_list.tsv). "
            "You can apply multiple filters in a single query to narrow results "
            "(e.g., filter by gene, feature type, and minimum copy number simultaneously)."
        ),
        "required_parameters": [],
        "optional_parameters": [
            {
                "name": "sample_name",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": "Sample name(s) to filter (e.g., '5637_URINARY_TRACT'). Accepts a single value or a list of values for OR matching.",
            },
            {
                "name": "sample_name_match",
                "type": "string",
                "enum": ["exact", "startswith", "contains"],
                "description": "Match mode for sample_name: 'exact', 'startswith', or 'contains' (default). Case-insensitive.",
            },
            {
                "name": "amplicon_number",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": "Amplicon number(s) to filter (e.g., 'amplicon1'). Accepts a single value or a list of values for OR matching.",
            },
            {
                "name": "feature",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Feature name(s) to filter (e.g., 'ecDNA_1', 'BFB_2'). "
                    "Accepts a single value or a list of values for OR matching."
                ),
            },
            {
                "name": "feature_type",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "enum": ["ecDNA", "BFB", "Linear", "Complex-non-cyclic"],
                "description": (
                    "Filter by feature type prefix (e.g., 'ecDNA' matches ecDNA_1, ecDNA_2, etc.). "
                    "Accepts a single value or a list of values for OR matching."
                ),
            },
            {
                "name": "gene",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Gene symbol(s) to filter by (e.g., 'EGFR' or ['MYC', 'EGFR', 'ERBB2']). "
                    "Returns rows where the gene column matches one of the specified symbols (OR logic). "
                    "Case-insensitive exact match."
                ),
            },
            {
                "name": "ncbi_id",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "NCBI transcript/gene ID(s) to filter by (e.g., 'NM_001949' or ['NR_015410', 'NM_017774']). "
                    "Returns rows where the ncbi_id column matches one of the specified IDs (OR logic)."
                ),
            },
            {
                "name": "is_canonical_oncogene",
                "type": "boolean",
                "description": "If True, return only genes that are canonical oncogenes. If False, return only non-oncogenes. Omit to return all.",
            },
            {
                "name": "is_truncated",
                "type": "boolean",
                "description": (
                    "Filter by truncation status. The truncated column indicates which end(s) of the gene "
                    "have been lost: None (not truncated), '5p' (5-prime end lost), '3p' (3-prime end lost), "
                    "or '5p_3p' (both ends lost). "
                    "If True, return only genes with any truncation (5p, 3p, or 5p_3p). "
                    "If False, return only non-truncated genes (None). Omit to return all."
                ),
            },
            {
                "name": "truncated",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "enum": ["5p", "3p", "5p_3p"],
                "description": (
                    "Filter by specific truncation type(s). Accepts a single value or a list for OR matching. "
                    "Valid values: '5p' (5-prime end lost), '3p' (3-prime end lost), '5p_3p' (both ends lost). "
                    "Use this when you need a specific truncation side rather than just any/none. "
                    "Example: truncated='3p' returns only genes truncated at the 3-prime end."
                ),
            },
            {
                "name": "gene_cn_min",
                "type": "number",
                "description": "Minimum per-gene copy number threshold. Filters rows to genes with copy number >= this value.",
            },
            {
                "name": "gene_cn_max",
                "type": "number",
                "description": "Maximum per-gene copy number threshold. Filters rows to genes with copy number <= this value.",
            },
            {
                "name": "select",
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Columns to return. Defaults to all columns: sample_name, amplicon_number, feature, gene, "
                    "gene_cn, truncated, is_canonical_oncogene, ncbi_id. "
                    "Use exact column names from the TSV schema; unknown columns will raise an error."
                ),
            },
            {
                "name": "limit",
                "type": "integer",
                "description": "Maximum number of rows to return. If not specified, returns all matching rows.",
            },
            {
                "name": "offset",
                "type": "integer",
                "description": "Row offset for pagination (default 0).",
            },
            {
                "name": "tsv_path",
                "type": "string",
                "description": "Path to the amplicon gene list TSV file (e.g., CCLE_gene_list.tsv). If not specified, uses default config path.",
            },
        ],
        "returns": {
            "type": "object",
            "fields": [
                "summary",
                "row_count_total",
                "row_count_returned",
                "filters_applied",
                "rows",
                "schema",
            ],
        },
    }
]
