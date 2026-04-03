"""
Launch the Biomni amplicon agent as a public Gradio web demo.

All interactions are logged to: logs/demo_interactions.log
"""

import os
import re
import base64
import tempfile
from datetime import datetime

import gradio as gr
from openai import OpenAI

os.environ.setdefault("BIOMNI_PATH", "amplicon/data")

from amplicon.agent import A1
from amplicon.tool.support_tools import get_captured_plots, clear_captured_plots

# ── Topic filter ──────────────────────────────────────────────────────────────
_openai_client = OpenAI()

_FILTER_PROMPT = """You are a strict topic classifier for a cancer genomics assistant.
The assistant ONLY answers questions about:
- Cancer amplicons (ecDNA, BFB, Linear, Complex-non-cyclic)
- Oncogenes and their amplification
- Cancer datasets: CCLE, TCGA, PCAWG
- Genomic coordinates of genes
- Cancer biology related to amplification

Reply with exactly one word: RELEVANT or IRRELEVANT."""


def _is_cancer_question(question: str) -> bool:
    """Return True if the question is relevant to cancer amplicon biology."""
    try:
        resp = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _FILTER_PROMPT},
                {"role": "user", "content": question},
            ],
            max_tokens=5,
            temperature=0,
        )
        verdict = resp.choices[0].message.content.strip().upper()
        return verdict == "RELEVANT"
    except Exception:
        return True  # fail open — let agent handle it

# ── Logging setup ────────────────────────────────────────────────────────────
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
DEMO_LOG = os.path.join(LOG_DIR, "demo_interactions.log")


def _log_interaction(question: str, tool_log: str, answer: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 80
    entry = (
        f"\n{separator}\n"
        f"TIMESTAMP : {timestamp}\n"
        f"{separator}\n"
        f"QUESTION\n{'-' * 40}\n{question}\n\n"
        f"TOOL LOG\n{'-' * 40}\n{tool_log}\n\n"
        f"ANSWER\n{'-' * 40}\n{answer}\n"
    )
    with open(DEMO_LOG, "a") as f:
        f.write(entry)


def _extract_tool_log(messages: list) -> str:
    tool_lines = []
    for msg in messages:
        if "Ai Message" not in msg and "Human Message" not in msg:
            continue
        for block in re.findall(r"<execute>(.*?)</execute>", msg, re.DOTALL):
            tool_lines.append(f"[TOOL CALL]\n{block.strip()}")
        for obs in re.findall(r"<observation>(.*?)</observation>", msg, re.DOTALL):
            tool_lines.append(f"[OBSERVATION]\n{obs.strip()}")
    return "\n\n".join(tool_lines) if tool_lines else "(no tool calls recorded)"


def _save_plot(b64_data: str) -> str:
    """Save a base64-encoded PNG to a temp file and return the path."""
    raw = base64.b64decode(b64_data.split(",")[1] if "," in b64_data else b64_data)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(raw)
    tmp.close()
    return tmp.name


# ── Agent setup ───────────────────────────────────────────────────────────────
agent = A1(
    llm="gpt-5",
    expected_data_lake_files=[],
)


# ── Agent handler ─────────────────────────────────────────────────────────────
def run_agent(message, history):
    """Run the agent and return (answer, gallery_update)."""
    if not _is_cancer_question(message):
        return (
            "I can only answer questions about cancer amplicon data (ecDNA, BFB, Linear, "
            "Complex-non-cyclic) and related cancer genomics topics. Please ask something "
            "related to cancer amplification, oncogenes, or the CCLE/TCGA/PCAWG datasets.",
            gr.update(visible=False, value=[]),
        )

    clear_captured_plots()
    try:
        result = agent.go(message)
        messages = result[0] if isinstance(result, tuple) else result
        full_text = "\n".join(messages) if isinstance(messages, list) else str(messages)

        solution_match = re.search(r"<solution>(.*?)</solution>", full_text, re.DOTALL)
        if solution_match:
            answer = solution_match.group(1).strip()
        else:
            answer = ""
            for msg in reversed(messages):
                if "Ai Message" in msg:
                    lines = msg.split("\n")
                    answer = "\n".join(l for l in lines if "===" not in l).strip()
                    if answer:
                        break
            if not answer:
                answer = str(messages[-1])

        tool_log = _extract_tool_log(messages)
        _log_interaction(message, tool_log, answer)

        # Collect plots
        plots = get_captured_plots()
        clear_captured_plots()
        if plots:
            paths = [_save_plot(b) for b in plots]
            gallery_update = gr.update(visible=True, value=paths)
        else:
            gallery_update = gr.update(visible=False, value=[])

        return answer, gallery_update

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        _log_interaction(message, "(error — no tool log)", error_msg)
        return error_msg, gr.update(visible=False, value=[])


# ── Gradio UI ─────────────────────────────────────────────────────────────────
EXAMPLES = [
    "Is YES1 amplified as ecDNA or BFB in CCLE? In which samples?",
    "What are the top 10 most amplified oncogenes as ecDNA in CCLE?",
    "Show the distribution of amplification classes across cancer types in CCLE.",
    "What are all the ecDNA-like cycles in the CCLE dataset for sample AU565_BREAST?",
    "What are the genomic coordinates of MYC in hg38?",
]

CSS = "* { font-family: Arial, sans-serif !important; }"

plot_gallery = gr.Gallery(label="Generated Plots", visible=False, columns=2, height=400)

with gr.Blocks(title="Biomni Amplicon Agent") as demo:
    gr.ChatInterface(
        fn=run_agent,
        title="Biomni Amplicon Agent",
        description=(
            "Ask questions about cancer amplicon data (ecDNA, BFB, Linear, Complex-non-cyclic) "
            "from CCLE, TCGA, and PCAWG datasets."
        ),
        examples=EXAMPLES,
        additional_outputs=[plot_gallery],
    )
    plot_gallery.render()

print(f"\nLaunching Biomni Amplicon Agent demo...")
print(f"Interactions will be logged to: {DEMO_LOG}")

demo.launch(share=False, server_name="0.0.0.0", css=CSS)
