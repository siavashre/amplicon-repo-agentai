"""
Launch the Biomni amplicon agent as a public Gradio web demo.

Usage:
    python launch_demo.py

The script will print a public shareable URL (e.g. https://xxxxx.gradio.live)
that anyone can open in their browser. The link stays active as long as this
script is running (up to 72 hours).

All interactions are logged to: logs/demo_interactions.log
Full per-turn tool logs are saved to: logs/session_*/
"""

import os
import re
import json
from datetime import datetime

import gradio as gr

os.environ.setdefault("BIOMNI_PATH", "biomni/data")

from biomni.agent import A1

# ── Logging setup ────────────────────────────────────────────────────────────
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
DEMO_LOG = os.path.join(LOG_DIR, "demo_interactions.log")

def _log_interaction(question: str, tool_log: str, answer: str):
    """Append one interaction to the demo log file."""
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
    """Extract tool calls and observations from the message list."""
    tool_lines = []
    for msg in messages:
        if "Ai Message" not in msg and "Human Message" not in msg:
            continue
        # Collect <execute> blocks and <observation> blocks
        for block in re.findall(r"<execute>(.*?)</execute>", msg, re.DOTALL):
            tool_lines.append(f"[TOOL CALL]\n{block.strip()}")
        for obs in re.findall(r"<observation>(.*?)</observation>", msg, re.DOTALL):
            tool_lines.append(f"[OBSERVATION]\n{obs.strip()}")
    return "\n\n".join(tool_lines) if tool_lines else "(no tool calls recorded)"


# ── Agent setup ───────────────────────────────────────────────────────────────
agent = A1(
    # llm="claude-sonnet-4-20250514",
    llm="gpt-5",
    expected_data_lake_files=[],
)


# ── Gradio handler ────────────────────────────────────────────────────────────
def run_agent(message, history):
    """Run the agent and return the final answer, logging everything."""
    try:
        result = agent.go(message)
        messages = result[0] if isinstance(result, tuple) else result
        full_text = "\n".join(messages) if isinstance(messages, list) else str(messages)

        # Extract final answer from <solution> tag
        solution_match = re.search(r"<solution>(.*?)</solution>", full_text, re.DOTALL)
        if solution_match:
            answer = solution_match.group(1).strip()
        else:
            # Fallback: last AI message content
            answer = ""
            for msg in reversed(messages):
                if "Ai Message" in msg:
                    lines = msg.split("\n")
                    answer = "\n".join(l for l in lines if "===" not in l).strip()
                    if answer:
                        break
            if not answer:
                answer = str(messages[-1])

        # Extract tool log
        tool_log = _extract_tool_log(messages)

        # Save to log file
        _log_interaction(message, tool_log, answer)

        return answer

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        _log_interaction(message, "(error — no tool log)", error_msg)
        return error_msg


# ── Gradio UI ─────────────────────────────────────────────────────────────────
demo = gr.ChatInterface(
    fn=run_agent,
    title="Biomni Amplicon Agent",
    description=(
        "Ask questions about cancer amplicon data"
        "from CCLE, TCGA, and PCAWG datasets. "
        "Example: *Which oncogenes are most frequently amplified as BFB? (top 25)*"
    ),
    examples=[
        "Is YES1 amplified as ecDNA or BFB in CCLE? In which samples?",
        "What are the top 10 most amplified oncogenes as ecDNA in CCLE?",
        "Show the distribution of amplification classes across cancer types in CCLE.",
        "What are all the ecDNA-like cycles in the CCLE dataset for sample AU565_BREAST?",
        "What are the genomic coordinates of MYC in hg38?",
    ],
)

print(f"\nLaunching Biomni Amplicon Agent demo...")
print(f"Interactions will be logged to: {DEMO_LOG}")
print(f"Full tool logs saved to:        logs/session_*/")
print("Share the public URL below with your testers.\n")

demo.launch(share=True, server_name="0.0.0.0")
