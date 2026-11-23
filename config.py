from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("FIGURELAB_DATA", PROJECT_ROOT / "data")).expanduser()

FIGURE_DIR = DATA_DIR / "figures"
ARTICLE_DIR = DATA_DIR / "articles"
METADATA_DIR = DATA_DIR / "metadata"

FIGURES_JSONL = METADATA_DIR / "figures.jsonl"
PAPERS_JSONL = METADATA_DIR / "papers.jsonl"
CHARACTERIZED_JSONL = METADATA_DIR / "characterized_figures.jsonl"

EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PMC_S3_BASE = "https://pmc-oa-opendata.s3.amazonaws.com"
USER_AGENT = os.getenv(
    "FIGURELAB_USER_AGENT",
    "FigureLabPrototype/0.1 (educational research project)"
)
REQUEST_DELAY = float(os.getenv("FIGURELAB_REQUEST_DELAY", "0.4"))

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".webp", ".svg"
}

DEFAULT_PMC_QUERY = (
    '("chemistry"[Title/Abstract] OR "chemical"[Title/Abstract] '
    'OR "materials science"[Title/Abstract] OR "spectroscopy"[Title/Abstract]) '
    'AND open_access[filter]'
)
