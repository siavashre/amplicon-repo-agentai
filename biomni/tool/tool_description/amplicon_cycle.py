# biomni/tool/tool_description/amplicon_cycle.py

description = [
    {
        "name": "query_amplicon_cycles",
        "description": (
            "Query and filter cycle/path records from AmpliconArchitect (AA) annotated cycle files "
            "across amplicon samples. Each row represents one predicted cycle or linear path within one "
            "amplicon of one sample. Fields include cycle ID, copy count, path length (bp), whether the "
            "path is cyclic, cycle classification, and the ordered list of segments (with strand and "
            "genomic coordinates) composing the structure. "
            "Files are organized by dataset (e.g., CCLE, TCGA, PCAWG) and named "
            "{sample_name}_{amplicon_number}_annotated_cycles. These annotated files are preferred over "
            "raw AA output: they remove cycles overlapping low-complexity regions, patch reference genome "
            "issues, and deduplicate erroneously repeated entries. "
            "Each file is structured in two sections: first, a list of segments (each with an integer ID, "
            "chromosome, start, and end coordinate), followed by a list of cycles. Each cycle references "
            "its segments by ID and strand (e.g., '21+,34-'), and this tool resolves those IDs back to "
            "full genomic coordinates so each returned cycle row is self-contained. "
            "Segment 0 is a reserved connection vertex — a cycle containing segment 0 is a linear path "
            "whose endpoints connect to undetermined or out-of-amplicon positions. "
            "Use this tool to answer questions about amplicon structure, specifically the cycles and "
            "paths predicted by AA — such as which cycles are ecDNA-like, how many segments compose a "
            "cycle, what genomic regions a cycle spans, the copy count or length of specific cycles, "
            "whether a cycle is circular or linear, and how cycle classes are distributed across "
            "datasets, samples, or amplicons. "
            "You can apply multiple filters in a single query to narrow results."
        ),
        "required_parameters": [],
        "optional_parameters": [
            {
                "name": "dataset",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Dataset folder name(s) to load (e.g., 'CCLE', 'TCGA', 'PCAWG'). "
                    "All cycle files within the specified folder(s) are loaded and queried together. "
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
                "name": "cycle_id",
                "type": ["integer", "array"],
                "items": {"type": "integer"},
                "description": (
                    "Cycle ID(s) to filter (e.g., 1 or [1, 3]). IDs are unique within a single file "
                    "(sample + amplicon) but restart from 1 across different files. Should be combined "
                    "with sample_name and amplicon_number to target a specific cycle. "
                    "Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "cycle_class",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "enum": ["ecDNA-like", "Linear", "Rearranged", "Invalid"],
                "description": (
                    "Cycle classification(s) to filter. Accepts a single value or a list for OR matching. "
                    "Valid values: 'ecDNA-like' (circular amplicons), 'Linear' (linear paths), "
                    "'Rearranged' (rearranged linear paths), 'Invalid' (low-complexity or artefact cycles)."
                ),
            },
            {
                "name": "is_cyclic",
                "type": "boolean",
                "description": (
                    "Filter by whether the path is cyclic (True) or linear (False). "
                    "A cyclic path loops back to its first segment; a non-cyclic path contains segment 0 "
                    "(connection vertex), indicating open endpoints."
                ),
            },
            {
                "name": "copy_count_min",
                "type": "number",
                "description": "Minimum copy count of the cycle (inclusive).",
            },
            {
                "name": "copy_count_max",
                "type": "number",
                "description": "Maximum copy count of the cycle (inclusive).",
            },
            {
                "name": "length_min",
                "type": "integer",
                "description": "Minimum total path length in base pairs (inclusive).",
            },
            {
                "name": "length_max",
                "type": "integer",
                "description": "Maximum total path length in base pairs (inclusive).",
            },
            {
                "name": "num_segments_min",
                "type": "integer",
                "description": (
                    "Minimum number of segments in the cycle, excluding segment 0 connection vertices. "
                    "Useful for filtering out single-segment trivial cycles."
                ),
            },
            {
                "name": "num_segments_max",
                "type": "integer",
                "description": (
                    "Maximum number of segments in the cycle, excluding segment 0 connection vertices."
                ),
            },
            {
                "name": "chrom",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Chromosome(s) to filter by (e.g., 'chr8', 'chrX'). "
                    "Returns cycles where at least one segment in the cycle overlaps the specified "
                    "chromosome(s). Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "genomic_region",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Genomic region(s) in chrN:start-end format (e.g., 'chr8:127700000-128000000'). "
                    "Returns cycles where at least one segment overlaps any of the specified regions. "
                    "Overlap is defined as the segment interval [start, end] intersecting the query "
                    "region [start, end] (inclusive). "
                    "Accepts a single value or a list for OR matching."
                ),
            },
            {
                "name": "select",
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Columns to return. Defaults to all columns: dataset, sample_name, amplicon_number, "
                    "cycle_id, copy_count, length, is_cyclic_path, cycle_class, num_segments, "
                    "chromosomes, segments. "
                    "The 'segments' field is a list of objects each containing: "
                    "id (segment ID), strand ('+' or '-'), chrom, start, end. "
                    "The 'chromosomes' field is a sorted list of unique chromosomes spanned by the cycle. "
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
                "name": "cycle_dir",
                "type": "string",
                "description": (
                    "Path to the root cycle files directory containing dataset subfolders. "
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
