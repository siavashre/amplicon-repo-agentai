# biomni/tool/tool_description/amplicon_graph.py

description = [
    {
        "name": "query_amplicon_graphs",
        "description": (
            "Query and filter edges from AmpliconArchitect (AA) graph files across amplicon samples. "
            "Each graph file describes the amplicon structure as a set of edges in two sections: "
            "(1) Sequence edges — non-overlapping reference genome segments covering all amplicon "
            "intervals, each with predicted copy number, average coverage, size (bp), and number "
            "of mapped reads; "
            "(2) Breakpoint edges — connections between genomic positions, categorized as: "
            "'discordant' (non-consecutive positions joined in the amplicon, representing structural variants such as rearrangements and novel adjacencies), "
            "'concordant' (consecutive reference positions, confirming reference connectivity), or "
            "'source' (connection between a known genomic position and an unknown/out-of-amplicon "
            "position). Breakpoint edges include predicted copy number, number of supporting read pairs, "
            "and homology/insertion size and sequence at the breakpoint. "
            "Files are organized by dataset (e.g., CCLE) and named "
            "{sample_name}_{amplicon_number}_graph.txt, where sample_name and amplicon_number "
            "are parsed directly from the filename. "
            "Use this tool to answer questions about amplicon graph structure — such as which segments "
            "have high copy number, what discordant breakpoints are present, the coverage of specific "
            "genomic intervals, or the connectivity of amplicon segments. "
            "Use the 'query_type' parameter to retrieve sequence edges, breakpoint edges, or both. "
            "You can apply multiple filters in a single query to narrow results."
        ),
        "required_parameters": [],
        "optional_parameters": [
            {
                "name": "dataset",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Dataset folder name(s) to load (e.g., 'CCLE'). "
                    "All graph files within the specified folder(s) are loaded and queried together. "
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
                "description": (
                    "Match mode for sample_name: 'exact', 'startswith', or 'contains' (default). "
                    "Case-insensitive."
                ),
            },
            {
                "name": "amplicon_number",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Amplicon number(s) to filter (e.g., 'amplicon1'). "
                    "Parsed from the filename. Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "query_type",
                "type": "string",
                "enum": ["sequence", "breakpoint", "all"],
                "description": (
                    "Which edge type to return. 'sequence' returns only sequence edges (genomic segments). "
                    "'breakpoint' returns only breakpoint edges (discordant, concordant, source). "
                    "'all' (default) returns both types together, with an 'edge_category' column "
                    "indicating 'sequence' or 'breakpoint'."
                ),
            },
            {
                "name": "breakpoint_edge_type",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "enum": ["discordant", "concordant", "source"],
                "description": (
                    "Filter breakpoint edges by type. Only applies when query_type is 'breakpoint' or 'all'. "
                    "'discordant': non-consecutive positions joined in the amplicon, representing structural variants (SVs) such as rearrangements, fusions, or novel adjacencies. "
                    "'concordant': consecutive reference positions confirming reference connectivity. "
                    "'source': connection to an unknown or out-of-amplicon position. "
                    "Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "chrom",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Chromosome(s) to filter by (e.g., 'chr8', 'chrX'). "
                    "For sequence edges, returns edges where the segment lies on the chromosome. "
                    "For breakpoint edges, returns edges where either endpoint lies on the chromosome. "
                    "Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "genomic_region",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Genomic region(s) in chrN:start-end format (e.g., 'chr8:127700000-128000000'). "
                    "For sequence edges, returns edges where the segment overlaps the region. "
                    "For breakpoint edges, returns edges where either endpoint falls within the region. "
                    "Overlap is inclusive. Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "copy_count_min",
                "type": "number",
                "description": "Minimum predicted copy number of the edge (inclusive). Applies to both sequence and breakpoint edges.",
            },
            {
                "name": "copy_count_max",
                "type": "number",
                "description": "Maximum predicted copy number of the edge (inclusive). Applies to both sequence and breakpoint edges.",
            },
            {
                "name": "coverage_min",
                "type": "number",
                "description": "Minimum average read coverage of a sequence edge (inclusive). Only applies to sequence edges.",
            },
            {
                "name": "coverage_max",
                "type": "number",
                "description": "Maximum average read coverage of a sequence edge (inclusive). Only applies to sequence edges.",
            },
            {
                "name": "size_min",
                "type": "integer",
                "description": "Minimum size in base pairs of a sequence edge (inclusive). Only applies to sequence edges.",
            },
            {
                "name": "size_max",
                "type": "integer",
                "description": "Maximum size in base pairs of a sequence edge (inclusive). Only applies to sequence edges.",
            },
            {
                "name": "read_pairs_min",
                "type": "integer",
                "description": "Minimum number of supporting read pairs for a breakpoint edge (inclusive). Only applies to breakpoint edges.",
            },
            {
                "name": "read_pairs_max",
                "type": "integer",
                "description": "Maximum number of supporting read pairs for a breakpoint edge (inclusive). Only applies to breakpoint edges.",
            },
            {
                "name": "homology_size_min",
                "type": "number",
                "description": (
                    "Minimum homology size at a breakpoint edge (inclusive). Negative values indicate insertions. "
                    "Only applies to breakpoint edges. Rows with None homology size are excluded."
                ),
            },
            {
                "name": "select",
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Columns to return. For sequence edges the available columns are: "
                    "dataset, sample_name, amplicon_number, edge_category, chrom1, start1, chrom2, start2, "
                    "copy_count, avg_coverage, size, num_reads_mapped. "
                    "For breakpoint edges the available columns are: "
                    "dataset, sample_name, amplicon_number, edge_category, edge_type, "
                    "chrom1, pos1, strand1, chrom2, pos2, strand2, "
                    "copy_count, num_read_pairs, homology_size, homology_sequence. "
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
                "name": "graph_dir",
                "type": "string",
                "description": (
                    "Path to the root graph files directory containing dataset subfolders. "
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
