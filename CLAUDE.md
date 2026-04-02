# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a fork of [Amplicon](https://github.com/snap-stanford/Amplicon), a general-purpose biomedical AI agent. This fork adds an **amplicon table tool** (`amplicon/tool/amplicon_table.py`) for querying cancer amplicon data (ecDNA, BFB, Linear, Complex-non-cyclic) from CSV datasets (CCLE, TCGA, PCAWG).

The active development branch is `amplicon_table`. The main test file is `amplicon/test.py`.

## Environment Setup

```bash
# Minimal environment (recommended for development)
conda env create -f amplicon_env/environment.yml
conda activate biomni_e1

# Install the package in editable mode
pip install -e .
```

Full E1 environment setup takes >10 hours (`amplicon_env/setup.sh`), requires Ubuntu 22.04 and 30GB disk. Use the minimal environment for development.

## Running the Agent

```bash
# Run the test script (requires API key + data)
python amplicon/test.py
```

```python
from amplicon.agent import A1

# Skip data lake download for fast testing
agent = A1(llm="claude-sonnet-4-20250514", expected_data_lake_files=[])
agent.go("Your question here")
```

## Linting

```bash
ruff check .
ruff format .
```

## Architecture

### Agent Layer (`amplicon/agent/`)
- **`A1`** (`a1.py`) — primary agent class (LangGraph-based ReAct loop). Supports planning, reflection, data lake access, tool retrieval, PDF export, Gradio UI. This is what users instantiate.
- **`react`** (`react.py`) — simpler legacy ReAct agent using LangGraph with multiprocessing-based tool timeouts.

### Tool Layer (`amplicon/tool/`)
Tools are Python functions organized by domain (genomics, genetics, cancer_biology, database, etc.). Each tool module has a matching description file in `amplicon/tool/tool_description/` (JSON schema format). Tools are loaded via `read_module2api()` from `amplicon/utils.py`.

**This fork's key addition:** `amplicon_table.py` — `query_amplicons()` function that filters a cancer amplicon CSV file. Corresponding description: `tool_description/amplicon_table.py`.

Amplicon data lives at:
- `amplicon/data/amplicon_data/data_lake/amplicon_data/CCLE.csv`
- `amplicon/data/amplicon_data/data_lake/amplicon_data/TCGA.csv`
- `amplicon/data/amplicon_data/data_lake/amplicon_data/PCAWG.csv`

### Configuration (`amplicon/config.py`)
`default_config` is a global config object. Agent parameters default to it if not specified. Modify it before creating agents for consistent behavior across database queries and agent reasoning.

### Data Lake / Library
- `amplicon/env_desc.py` — `data_lake_dict` and `library_content_dict` describe available datasets and software packages injected into the agent's system prompt.
- Data lake files (~11GB) download automatically to `./data/data_lake/` on first agent run. Pass `expected_data_lake_files=[]` to skip.

### Know-How Library (`amplicon/know_how/`)
Markdown files with domain protocols (e.g., sgRNA design, single-cell annotation). Retrieved automatically by `KnowHowLoader` when relevant to a query.

## Adding a New Tool

1. Implement function in `amplicon/tool/<domain>.py`
2. Create JSON schema description in `amplicon/tool/tool_description/<domain>.py` (see `amplicon_table.py` as example)
3. For new data in the data lake: add entry to `data_lake_dict` in `amplicon/env_desc.py`
4. For new software: add to `library_content_dict` in `amplicon/env_desc.py`

Auto-generate schema with:
```python
from amplicon.utils import function_to_api_schema
from amplicon.llm import get_llm
llm = get_llm('claude-sonnet-4-20250514')
desc = function_to_api_schema(function_code, llm)
```

## API Keys

Copy `.env.example` to `.env` and fill in keys. `ANTHROPIC_API_KEY` is required for Claude models. `LLM_SOURCE` must match your provider (e.g., `"Anthropic"`, `"OpenAI"`).
