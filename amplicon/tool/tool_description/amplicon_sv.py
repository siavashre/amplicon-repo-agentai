# amplicon/tool_desc/amplicon_sv.py

description = [
    {
        "name": "query_amplicon_svs",
        "description": (
            "Query and filter structural variant (SV) records detected by AmpliconArchitect (AA) "
            "across amplicon samples. Each row represents one SV breakpoint pair within one amplicon "
            "of one sample, including breakpoint coordinates, SV type, read support, strand orientation, "
            "homology sequence, and which amplicon feature types the SV overlaps. "
            "Files are organized by dataset (e.g., CCLE, TCGA, PCAWG) and named "
            "{sample_name}_{amplicon_number}_SV_summary.tsv. When analyzing a dataset like CCLE, "
            "all TSV files within that dataset folder are loaded and queried together. "
            "Use this tool to answer questions about SV types, breakpoint locations, read support, "
            "foldback or interchromosomal events, co-occurrence of SVs with specific amplicon features "
            "(ecDNA, BFB, Linear, Complex-non-cyclic), or homology at breakpoints. "
            "You can apply multiple filters in a single query to narrow results. "
            "Note that SVs in amplicons with copy number near the focal amplification threshold (4.5) "
            "are less reliable — borderline amplicons may have noisier SV calls."
        ),
        "required_parameters": [],
        "optional_parameters": [
            {
                "name": "dataset",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Dataset folder name(s) to load (e.g., 'CCLE', 'TCGA', 'PCAWG'). "
                    "All TSV files within the specified folder(s) are loaded and queried together. "
                    "Accepts a single value or a list for OR matching. "
                    "If not specified, all available datasets are loaded."
                ),
            },
            {
                "name": "sample_name",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Sample name(s) to filter (e.g., 'AU565_BREAST'). "
                    "Parsed from the filename. Accepts a single value or a list for OR matching."
                ),
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
                "description": (
                    "Amplicon number(s) to filter (e.g., 'amplicon4'). "
                    "Parsed from the filename. Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "sv_type",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "enum": ["duplication-like", "deletion-like", "inversion", "foldback", "interchromosomal"],
                "description": (
                    "SV type(s) to filter. Accepts a single value or a list for OR matching. "
                    "Valid values: 'duplication-like', 'deletion-like', 'inversion', 'foldback', 'interchromosomal'. "
                    "'foldback' SVs are a key structural indicator of BFB (breakage-fusion-bridge) amplification."
                ),
            },
            {
                "name": "feature",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "enum": ["ecDNA", "BFB", "Linear", "Complex-non-cyclic", "unknown"],
                "description": (
                    "Filter SVs by the amplicon feature type(s) they overlap. The features column is "
                    "pipe-separated (e.g., 'ecDNA|unknown'). Returns rows where any of the specified "
                    "feature types appear in the features field. Accepts a single value or a list for OR matching. "
                    "Valid values: 'ecDNA', 'BFB', 'Linear', 'Complex-non-cyclic', 'unknown'."
                ),
            },
            {
                "name": "chrom",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Chromosome(s) to filter by (e.g., 'chr8', 'chrX'). "
                    "Returns rows where chrom1 or chrom2 matches one of the specified chromosomes. "
                    "Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "chrom1",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": "Filter specifically on chrom1 (first breakpoint chromosome). Accepts a single value or list.",
            },
            {
                "name": "chrom2",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": "Filter specifically on chrom2 (second breakpoint chromosome). Accepts a single value or list.",
            },
            {
                "name": "orientation",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "enum": ["++", "+-", "-+", "--"],
                "description": (
                    "Strand orientation of the two breakpoints. Accepts a single value or a list for OR matching. "
                    "Valid values: '++', '+-', '-+', '--'."
                ),
            },
            {
                "name": "pos1_range",
                "type": ["integer", "array"],
                "items": {"type": "integer"},
                "description": (
                    "Filter for the first breakpoint position. Accepts either an exact integer value "
                    "(e.g., 48905218) or a [min, max] range (e.g., [48000000, 49000000]). "
                    "Exact value returns rows where pos1 == value; range returns rows where pos1 falls "
                    "within [min, max] (inclusive)."
                ),
            },
            {
                "name": "pos2_range",
                "type": ["integer", "array"],
                "items": {"type": "integer"},
                "description": (
                    "Filter for the second breakpoint position. Accepts either an exact integer value "
                    "(e.g., 18695135) or a [min, max] range (e.g., [18000000, 19000000]). "
                    "Exact value returns rows where pos2 == value; range returns rows where pos2 falls "
                    "within [min, max] (inclusive)."
                ),
            },
            {
                "name": "genomic_region",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Genomic region(s) in chrN:start-end format (e.g., 'chr8:48000000-49000000'). "
                    "Returns SVs where either breakpoint (chrom1+pos1 or chrom2+pos2) falls within "
                    "any of the specified regions. Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "read_support_min",
                "type": "integer",
                "description": "Minimum number of reads supporting the SV (inclusive).",
            },
            {
                "name": "read_support_max",
                "type": "integer",
                "description": "Maximum number of reads supporting the SV (inclusive).",
            },
            {
                "name": "homology_length_min",
                "type": "number",
                "description": "Minimum homology length at the breakpoint (inclusive). Only SVs with a homology_length >= this value are returned.",
            },
            {
                "name": "select",
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Columns to return. Defaults to all columns: dataset, sample_name, amplicon_number, "
                    "chrom1, pos1, chrom2, pos2, sv_type, read_support, features, orientation, "
                    "pos1_flanking_coordinate, pos2_flanking_coordinate, homology_length, homology_sequence. "
                    "Use exact column names; unknown columns will raise an error."
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
                "name": "sv_dir",
                "type": "string",
                "description": (
                    "Path to the root SV directory containing dataset subfolders. "
                    "If not specified, uses the default config path."
                ),
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
                "datasets_loaded",
                "files_loaded",
            ],
        },
    }
]
