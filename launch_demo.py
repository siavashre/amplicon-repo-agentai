"""
Launch the Biomni amplicon agent as a public Gradio web demo.

All interactions are logged to: logs/demo_interactions.log
"""

import glob
import os
import re
import base64
import queue
import tempfile
import threading
import time
from datetime import datetime

import pandas as pd
import gradio as gr

os.environ.setdefault("BIOMNI_PATH", "biomni/data")

from biomni.agent import A1
from biomni.tool.support_tools import get_captured_plots, clear_captured_plots

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
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=LOG_DIR)
    tmp.write(raw)
    tmp.close()
    return tmp.name


def _cleanup_old_plots(max_age_seconds: int = 3600):
    """Delete plot temp files in LOG_DIR older than max_age_seconds."""
    now = time.time()
    for path in glob.glob(os.path.join(LOG_DIR, "tmp*.png")):
        try:
            if now - os.path.getmtime(path) > max_age_seconds:
                os.unlink(path)
        except OSError:
            pass


def _parse_markdown_table(text: str):
    """Extract all markdown tables from text, concatenate, and return a DataFrame, or None."""
    # Collect each contiguous table block
    blocks = []
    current = []
    for line in text.splitlines():
        if re.match(r"\s*\|.+\|", line):
            current.append(line.strip())
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)

    dfs = []
    for block in blocks:
        rows = [l for l in block if not re.match(r"^\|[-| :]+\|$", l)]
        if len(rows) < 1:
            continue
        headers = [c.strip() for c in rows[0].strip("|").split("|")]
        data = [[c.strip() for c in r.strip("|").split("|")] for r in rows[1:]]
        try:
            dfs.append(pd.DataFrame(data, columns=headers))
        except Exception:
            continue

    if not dfs:
        return None
    if len(dfs) == 1:
        return dfs[0]
    return pd.concat(dfs, ignore_index=True)


def _extract_answer(messages):
    full_text = "\n".join(messages) if isinstance(messages, list) else str(messages)
    solution_match = re.search(r"<solution>(.*?)</solution>", full_text, re.DOTALL)
    if solution_match:
        return solution_match.group(1).strip()
    for msg in reversed(messages):
        if "Ai Message" in msg:
            lines = msg.split("\n")
            answer = "\n".join(l for l in lines if "===" not in l).strip()
            if answer:
                return answer
    return str(messages[-1])


# ── Agent setup ───────────────────────────────────────────────────────────────
agent = A1(
    llm="gpt-5",
    expected_data_lake_files=[],
)


# ── Agent handler ─────────────────────────────────────────────────────────────
def respond(message, history, session_state):
    """Handle a user message. Generator — yields loading state then final answer."""
    history = history or []
    no_gallery = gr.update(visible=False, value=[])
    no_table = gr.update(visible=False, value=None)

    # ── Continuing a clarification ────────────────────────────────────────────
    if session_state is not None:
        response_q: queue.Queue = session_state["response_q"]
        question_q: queue.Queue = session_state["question_q"]
        result_container: dict = session_state["result"]

        # Show thinking indicator
        thinking = history + [{"role": "user", "content": message},
                               {"role": "assistant", "content": "⏳ Thinking..."}]
        yield "", thinking, no_gallery, no_table, session_state

        response_q.put(message)
        try:
            event = question_q.get(timeout=600)
        except queue.Empty:
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": "The agent timed out. Please start a new question."})
            yield "", history, no_gallery, no_table, None
            return

        if event["type"] == "help":
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": event["question"]})
            yield "", history, no_gallery, no_table, session_state
        else:
            answer = result_container.get("answer", "")
            plots = result_container.get("plots", [])
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": answer})
            gallery = gr.update(visible=True, value=[_save_plot(b) for b in plots]) if plots else no_gallery
            df = _parse_markdown_table(answer)
            table = gr.update(visible=True, value=df) if df is not None else no_table
            yield "", history, gallery, table, None
        return

    # ── Fresh query ───────────────────────────────────────────────────────────
    clear_captured_plots()
    _cleanup_old_plots()

    # Show thinking indicator immediately
    thinking = history + [{"role": "user", "content": message},
                           {"role": "assistant", "content": "⏳ Thinking..."}]
    yield "", thinking, no_gallery, no_table, session_state

    question_q: queue.Queue = queue.Queue()
    response_q: queue.Queue = queue.Queue()
    result_container: dict = {}

    HELP_TIMEOUT = 300  # seconds — abandon thread if user never responds
    AGENT_TIMEOUT = 600  # seconds — max time to wait for agent to finish/ask

    def user_input_fn(help_question: str) -> str:
        question_q.put({"type": "help", "question": help_question})
        try:
            return response_q.get(timeout=HELP_TIMEOUT) or ""
        except queue.Empty:
            raise RuntimeError("Session timed out waiting for user response.")

    def run_in_thread():
        try:
            result = agent.go(message, user_input_fn=user_input_fn)
            messages = result[0] if isinstance(result, tuple) else result
            tool_log = _extract_tool_log(messages)
            answer = _extract_answer(messages)
            _log_interaction(message, tool_log, answer)
            result_container["answer"] = answer
            result_container["plots"] = get_captured_plots()
            clear_captured_plots()
        except Exception as e:
            result_container["answer"] = f"Error: {str(e)}"
            result_container["plots"] = []
            _log_interaction(message, "(error)", result_container["answer"])
        question_q.put({"type": "done"})

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    try:
        event = question_q.get(timeout=AGENT_TIMEOUT)
    except queue.Empty:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "The agent timed out. Please try again with a more specific question."})
        yield "", history, no_gallery, no_table, None
        return

    if event["type"] == "help":
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": event["question"]})
        new_state = {"response_q": response_q, "question_q": question_q, "result": result_container}
        yield "", history, no_gallery, no_table, new_state
    else:
        answer = result_container.get("answer", "")
        plots = result_container.get("plots", [])
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": answer})
        gallery = gr.update(visible=True, value=[_save_plot(b) for b in plots]) if plots else no_gallery
        df = _parse_markdown_table(answer)
        table = gr.update(visible=True, value=df) if df is not None else no_table
        yield "", history, gallery, table, None


# ── Gradio UI ─────────────────────────────────────────────────────────────────
EXAMPLES = [
    "Is YES1 amplified as ecDNA or BFB in CCLE? In which samples?",
    "What are the top 10 most amplified oncogenes as ecDNA in CCLE?",
    "Show the distribution of amplification classes across cancer types in CCLE.",
    "What are all the ecDNA-like cycles in the CCLE dataset for sample AU565_BREAST?",
    "What are the genomic coordinates of MYC in hg38?",
]

CSS = "* { font-family: Arial, sans-serif !important; }"

with gr.Blocks(title="Biomni Amplicon Agent") as demo:
    gr.Markdown("# Biomni Amplicon Agent")
    gr.Markdown(
        "Ask questions about cancer amplicon data (ecDNA, BFB, Linear, Complex-non-cyclic) "
        "from CCLE, TCGA, and PCAWG datasets."
    )

    session_state = gr.State(value=None)

    chatbot = gr.Chatbot(height=550, show_label=False)
    data_table = gr.Dataframe(label="Results Table", visible=False, wrap=True)
    plot_gallery = gr.Gallery(label="Generated Plots", visible=False, columns=2, height=400)

    with gr.Row():
        msg_box = gr.Textbox(
            placeholder="Type your question here...",
            show_label=False,
            scale=9,
            autofocus=True,
        )
        send_btn = gr.Button("Send", variant="primary", scale=1)

    gr.Examples(examples=EXAMPLES, inputs=msg_box)

    outputs = [msg_box, chatbot, plot_gallery, data_table, session_state]
    send_btn.click(respond, [msg_box, chatbot, session_state], outputs)
    msg_box.submit(respond, [msg_box, chatbot, session_state], outputs)

print(f"\nLaunching Biomni Amplicon Agent demo...")
print(f"Interactions will be logged to: {DEMO_LOG}")
print("Share the public URL below with your testers.\n")

demo.launch(share=True, server_name="0.0.0.0", css=CSS)
