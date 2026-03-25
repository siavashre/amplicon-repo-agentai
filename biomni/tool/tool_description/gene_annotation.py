# biomni/tool/tool_description/gene_annotation.py

description = [
    {
        "name": "query_gene_coordinates",
        "description": (
            "Retrieve genomic coordinates for one or more genes from local GENCODE "
            "annotations for hg38 (v47) or hg19 (v19). Given a gene symbol, returns "
            "the gene's chromosomal location (chrom, start, end, strand), Ensembl gene ID, "
            "gene biotype, and transcript coordinates. Use this tool whenever an analysis "
            "requires knowing the genomic position of a gene — for example, to define a "
            "region of interest for amplicon overlap queries, to check which chromosome a "
            "gene is on, or to retrieve coordinates before calling other tools. "
            "On first use per genome, the GTF file is parsed and cached for fast subsequent "
            "lookups. Accepts one or multiple gene symbols in a single call."
        ),
        "required_parameters": [
            {
                "name": "gene_name",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Gene symbol(s) to query (e.g., 'MYC' or ['MYC', 'EGFR', 'KRAS']). "
                    "Case-sensitive. Raises an error if any gene is not found."
                ),
            },
        ],
        "optional_parameters": [
            {
                "name": "reference_genome",
                "type": "string",
                "enum": ["hg38", "hg19"],
                "description": (
                    "Reference genome version to query. Valid values: 'hg38' (default, GENCODE v47), "
                    "'hg19' (GENCODE v19)."
                ),
            },
            {
                "name": "transcript_mode",
                "type": "string",
                "enum": ["primary", "all"],
                "description": (
                    "Which transcripts to return alongside gene-level coordinates. "
                    "'primary' (default) returns only the canonical/MANE Select transcript per gene. "
                    "'all' returns every annotated transcript. Gene-level coordinates (spanning the "
                    "full gene locus) are always included regardless of this setting."
                ),
            },
            {
                "name": "gene_type",
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": (
                    "Optional filter by gene biotype (e.g., 'protein_coding', 'lncRNA', 'pseudogene'). "
                    "Accepts a single value or a list for OR matching. If not specified, all gene types "
                    "are returned."
                ),
            },
            {
                "name": "select",
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Columns to return in the transcript output. Defaults to all columns: "
                    "gene_name, gene_id, transcript_id, transcript_name, transcript_type, "
                    "is_primary, chrom, start, end, strand, reference_genome. "
                    "Gene-level output always contains: gene_name, gene_id, chrom, start, end, "
                    "strand, gene_type, reference_genome. Use exact column names."
                ),
            },
            {
                "name": "genes_dir",
                "type": "string",
                "description": (
                    "Path to the directory containing GTF and cache files. "
                    "If not specified, uses the default config path."
                ),
            },
        ],
        "returns": {
            "type": "object",
            "fields": [
                "summary",
                "genes",
                "transcripts",
                "not_found",
                "reference_genome",
                "transcript_mode",
            ],
        },
    }
]
