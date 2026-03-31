# Biomni Amplicon Agent — Demo Guide

## Prerequisites

- Conda installed
- `ANTHROPIC_API_KEY` set in your `.env` file
- The `amplicon` conda environment set up

---

## 1. Setup (first time only)

```bash
# Create and activate the environment
conda env create -f biomni_env/environment.yml
conda activate amplicon

# Install the package
pip install -e .

# Copy and fill in your API key
cp .env.example .env
# Edit .env and set: ANTHROPIC_API_KEY=your_key_here
```

---

## 2. Run the demo locally

```bash
conda activate amplicon
python launch_demo.py
```

This will print two URLs:
- **Local:** `http://localhost:7860` — accessible only on your machine
- **Public:** `https://xxxxxx.gradio.live` — shareable with anyone

The public link is active for **72 hours** and requires your machine to stay on.

---

## 3. Share with testers

Just copy the public URL printed in the terminal and send it to your testers. They can open it in any browser — no setup needed on their end.

Example questions to try:
- *Is YES1 amplified as ecDNA or BFB in CCLE? In which samples?*
- *What are the top 10 most amplified oncogenes as ecDNA in CCLE?*
- *Show the distribution of amplification classes across cancer types in CCLE.*
- *What are all the ecDNA-like cycles in sample AU565_BREAST?*
- *What are the genomic coordinates of MYC in hg38?*

---

## 4. Keep the demo running

The demo runs as long as the terminal is open. To keep it running after closing the terminal:

```bash
# Run in a persistent terminal session
nohup python launch_demo.py > demo.log 2>&1 &

# Check the public URL from the log
grep "gradio.live" demo.log

# Stop it later
pkill -f "launch_demo.py"
```

---

## 5. Permanent hosting (optional)

For a permanent public link without a 72-hour limit, deploy to **Hugging Face Spaces** (free):

### Step 1 — Create a Space
Go to https://huggingface.co/spaces and create a new Space with:
- **SDK:** Gradio
- **Visibility:** Public

### Step 2 — Add your API key as a secret
In the Space settings → Secrets, add:
```
ANTHROPIC_API_KEY = your_key_here
BIOMNI_PATH = ./biomni/data
```

### Step 3 — Push the code
```bash
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
git push hf amplicon_table:main
```

### Step 4 — Add an `app.py` entry point
Hugging Face Spaces expects a file named `app.py`. Rename or symlink `launch_demo.py`:
```bash
cp launch_demo.py app.py
# Then commit and push
git add app.py
git commit -m "Add app.py for HF Spaces"
git push hf amplicon_table:main
```

Your agent will be live at:
`https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Address already in use` | Run `pkill -f "launch_demo.py"` then relaunch |
| No public URL printed | Make sure `share=True` is set in `launch_demo.py` |
| API key error | Check your `.env` file has `ANTHROPIC_API_KEY` set |
| Import errors | Make sure you're in the `amplicon` conda environment |
| Link expired | Simply rerun `python launch_demo.py` to get a new link |
