# FigureLab

FigureLab is a Python prototype for collecting scientific figures from PubMed Central (PMC) and generating structured, AI-assisted descriptions and labels for a searchable figure library.

The initial focus is chemistry and materials science, with a taxonomy intended to expand to related fields.

## What it does

FigureLab has two main stages:

1. **Extract papers and figures from PMC.** Search PMC, retrieve available article packages, parse JATS XML, collect article and figure metadata, and download figure images when the article license permits.
2. **Characterize papers and figures.** Use the Google Gemini API to classify paper-level information and analyze figure images, captions, and article context. Results are saved as JSON Lines (JSONL).

This is a research prototype, not a production ingestion service.

## Repository layout

All Python modules are in the repository root (there is no `figurelab/` package directory):

```text
project3/
├── characterize_figures.py
├── classifier.py
├── config.py
├── jats.py
├── pipeline.py
├── pmc.py
├── pull_figures.py
├── taxonomy.py
├── utils.py
├── requirements.txt
├── README.md
├── THIRD_PARTY_NOTICES.md
└── data/                 # generated locally; not committed
    ├── articles/
    ├── figures/
    └── metadata/
```

## Requirements

- Python 3.10 or newer recommended
- A Google Gemini API key to run AI characterization
- Internet access for PMC retrieval and Gemini API requests

The extraction stage does not require a Gemini API key. Gemini API access, model availability, quotas, and pricing depend on your Google AI Studio project and the selected model. Check Google's current [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) before running larger jobs.

## Installation

Clone the repository and enter its directory:

```bash
git clone https://github.com/syeh1234/project3.git
cd project3
```

Create and activate a virtual environment (recommended):

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The dependencies are listed in `requirements.txt`. No separate package installation is needed for Gemini because the project calls the Gemini REST API using `httpx`.

## Configure Gemini

Only the characterization stage requires a Gemini API key. Create your own key in [Google AI Studio](https://aistudio.google.com/apikey). Do not share your key, paste it into source code, or commit it to Git.

Set the key in the terminal session where you will run FigureLab:

**macOS / Linux**
```bash
export GEMINI_API_KEY="your-google-api-key"
# Optional: override the default model
export FIGURELAB_VISION_MODEL="gemini-3.1-flash-lite"
```

**Windows PowerShell**
```powershell
$env:GEMINI_API_KEY = "your-google-api-key"
# Optional: override the default model
$env:FIGURELAB_VISION_MODEL = "gemini-3.1-flash-lite"
```

The default model is `gemini-3.1-flash-lite`; set `FIGURELAB_VISION_MODEL` to another model ID available to your API project if needed. API keys and model access are managed by Google, not by a ChatGPT subscription.

The environment variable is set only for the current terminal session. Set it again in a new terminal session.

## 1. Pull papers and figures from PMC

Run a small test first:

```bash
python pull_figures.py --max-articles 2
```

To use a custom PubMed query:

```bash
python pull_figures.py --query '"UV-vis spectroscopy" AND chemistry AND open_access[filter]' --max-articles 10
```

The extraction script creates the local data directories and writes:

- JATS XML article files: `data/articles/`
- Downloaded figure images: `data/figures/`
- Figure metadata: `data/metadata/figures.jsonl`
- Paper metadata: `data/metadata/papers.jsonl`

Figure metadata can be retained even when an image cannot be downloaded. The downloader only downloads images when PMC metadata indicates a Creative Commons license code; the precise license code is retained in the metadata. A Creative Commons label is not a substitute for checking the specific license terms before reuse or redistribution.

## 2. Characterize papers and figures

After extraction, make sure `GEMINI_API_KEY` is set, then run:

```bash
python characterize_figures.py --limit 10
```

The `--limit` option limits the number of **figure records**, not the number of papers. To process all available figure records:

```bash
python characterize_figures.py
```

To reclassify records that were already successfully classified:

```bash
python characterize_figures.py --force
```

The output is saved to:

```text
data/metadata/characterized_figures.jsonl
```

The pipeline makes a paper-level request for each relevant article and a figure-level request for each figure that has a local image. It supplies available image(s), caption, title, abstract, journal, article type, and XML-derived section placement to the model. Records without a local image cannot be visually classified and are recorded as errors for that run.

The paper-level characterization includes publication type, research fields, subfields, and an inferred journal subject area.

The figure-level characterization includes:

- Figure category
- Visual type(s) and chart type(s)
- Experimental technique(s) and technique groups
- Visualization purpose(s)
- Data characteristics and variables
- Panel count and panel descriptions
- Concise description, style tags, evidence, confidence, and review flag

## Configuration

By default, generated data is stored in the repository's `data/` directory. To store it elsewhere, set `FIGURELAB_DATA` before running either script.

**macOS / Linux**
```bash
export FIGURELAB_DATA="$HOME/figurelab-data"
```

**Windows PowerShell**
```powershell
$env:FIGURELAB_DATA = "$HOME\figurelab-data"
```

Other optional environment variables:

- `FIGURELAB_USER_AGENT`: user-agent string used for PMC requests.
- `FIGURELAB_REQUEST_DELAY`: delay between PMC article requests, in seconds.
- `FIGURELAB_VISION_MODEL`: Gemini model ID used for characterization.

## Inspecting the output

JSONL is a text format with one JSON object per line. You can open the files in a code editor, or pretty-print each record in the terminal:

```bash
python -c "import json; [print(json.dumps(json.loads(line), indent=2, ensure_ascii=False)) for line in open('data/metadata/characterized_figures.jsonl') if line.strip()]"
```

## Current design decisions and limitations

- Paper-level context is stored separately from figure-level characterization.
- Article section placement is extracted from JATS XML; it is not treated as the same thing as a figure's visual purpose.
- Multi-label values are allowed because a multi-panel figure can contain multiple visual types.
- Missing technique or axis information should not be guessed by the classifier.
- DOI, PMCID, source URL, and exact license code are retained with the source metadata.
- PMC article versions may be processed as separate records; deduplication may be needed for some use cases.
- Section references depend on figure cross-references in JATS XML. Figures without body references may have unknown section placement.
- The classifier sends up to three local image files for a figure. It describes panels but does not yet create separate database records for each panel.
- API requests are currently processed sequentially. Concurrency should be added only after considering provider quotas and costs.
- The controlled vocabulary and model-generated labels need validation against a manually reviewed sample before relying on them for large-scale search.

## Attribution and licensing

The [PaperFigureLib project](https://github.com/fengxijia/PaperFigureLib) was used as an architectural and workflow reference, particularly for figure categories, multimodal classification, cached labels, and staged verification.

See `THIRD_PARTY_NOTICES.md` for the applicable software license notice. The PaperFigureLib software license does not license the original paper images. FigureLab's PMC downloads retain their own article-level licensing information.
