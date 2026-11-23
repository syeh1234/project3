# FigureLab — Python baseline

A first-pass scientific-figure ingestion and characterization pipeline.

This repository combines:
- Your PMC workflow: search PMC, retrieve the PMC AWS article package, parse JATS XML, download eligible figure images, and save metadata.
- A PaperFigureLib-inspired classification workflow: controlled figure categories, vision-model labels, cached results, and a separate paper/figure characterization layer.

The initial target is chemistry and materials science, but the taxonomy is designed to expand.

## Repository layout

```text
figurelab-baseline/
├── figurelab/
│   ├── __init__.py
│   ├── config.py
│   ├── utils.py
│   ├── taxonomy.py
│   ├── pmc.py
│   ├── jats.py
│   ├── classifier.py
│   └── pipeline.py
├── pull_figures.py
├── characterize_figures.py
├── requirements.txt
├── .env.example
└── data/                    # generated locally; excluded from Git
    ├── articles/
    ├── figures/
    └── metadata/
```

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\\Scripts\\activate       # Windows

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add an API key for classification. The scripts read environment variables directly; if you use a `.env` file, export its values in your shell or install/use `python-dotenv`.

```bash
export GEMINI_API_KEY="your-google-api-key"
export FIGURELAB_VISION_MODEL="gemini-3.1-flash-lite"
```

## 2. Pull papers and figures from PMC

```bash
python pull_figures.py --max-articles 10
```

Or supply a PubMed Central query:

```bash
python pull_figures.py \\
  --query '"UV-vis spectroscopy" AND chemistry AND open_access[filter]' \\
  --max-articles 25
```

The script saves:
- JATS XML: `data/articles/`
- Figure images: `data/figures/`
- One JSONL record per figure: `data/metadata/figures.jsonl`
- One JSONL record per paper: `data/metadata/papers.jsonl`

Each figure record includes paper metadata, caption, image paths, license code, and the section(s) in which the figure is referenced.

### Section characterization

The parser maps figure IDs to `<xref ref-type="fig" rid="...">` references in the article body. It records all referenced sections and uses the first body reference as the initial primary section.

This is a heuristic, not a guarantee of the figure's conceptual role. A figure may be cited in several sections, or not cited in the body at all. Such cases remain visible in the metadata.

### Licensing

The downloader only downloads images when the PMC metadata has a Creative Commons license code. It preserves the exact license code in each record. A Creative Commons label is not a substitute for checking the specific license terms before public redistribution, especially for noncommercial or no-derivatives variants.

## 3. Characterize papers and figures with a vision model

```bash
python characterize_figures.py --limit 10
```

Run the full collection:

```bash
python characterize_figures.py
```

Reclassify existing records:

```bash
python characterize_figures.py --force
```

Output: `data/metadata/characterized_figures.jsonl`

The pipeline makes one paper-level request per article and one figure-level request per figure. It supplies the image, caption, title, abstract, journal, article type, and XML-derived section placement to the model.

The paper-level characterization includes:
- publication type
- research field(s)
- subfield(s)
- inferred journal subject area

The figure-level characterization includes:
- PaperFigureLib-style category: background, method, data, example, prompt, table, other
- visual type(s) and chart subtype(s)
- experimental technique(s)
- visualization purpose(s)
- data characteristics and variables
- panel count and panel descriptions
- concise description, evidence, confidence, and review flag

The section is extracted from JATS XML rather than guessed by the vision model.

## 4. Current design decisions

- **Separate paper context from figure characterization.** Journal and article-level metadata should not be repeated as if they were properties of each image.
- **Separate paper section from figure purpose.** A figure can appear in Results but serve as a mechanism diagram, or appear in Introduction as a motivation graphic.
- **Allow multi-label values.** A multi-panel figure may contain a schematic and multiple charts.
- **Do not guess.** Missing technique or axis information should be marked unknown.
- **Keep source metadata.** DOI, PMCID, source URL, and exact license code travel with the figure record.
- **Keep downloaded data out of Git.** Commit source code and configuration, not article images or API keys.

## 5. Known limitations / next steps

This is a baseline, not a production ingestion system.

1. PMC article versions are processed as separate source versions. You may want a deduplication policy after testing.
2. Section references depend on JATS figure cross-references. Figures without body references remain `unknown`.
3. The current classifier sends up to three image files for a figure. It describes panels but does not yet crop each panel into a separate database record.
4. The baseline processes API requests sequentially. Add concurrency only after confirming provider rate limits and cost.
5. Journal subject area is an AI suggestion, not an authoritative journal taxonomy. Consider mapping journal ISSNs to an external subject taxonomy later.
6. The classifier is designed for scientific papers, but its controlled vocabulary needs to be tested and refined against a manually reviewed sample.
7. The existing CSV format from the earlier prototype is not the new canonical format. The new scripts write JSONL so nested fields (sections, panels, variables, licenses) are retained.

## 6. Attribution and licensing

The PaperFigureLib project was used as an architectural and workflow reference, particularly its figure-category taxonomy, multimodal classification approach, cached labels, and staged verification concept.

Repository: https://github.com/fengxijia/PaperFigureLib

See `THIRD_PARTY_NOTICES.md` for its MIT license notice. The original PaperFigureLib figure collection is not covered by that software license. FigureLab's PMC downloads retain their own article-level licensing information.
