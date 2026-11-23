"""Batch characterization of extracted PMC figures."""

from collections import OrderedDict
from pathlib import Path
import json

from .classifier import VisionClassifier, normalize_figure_result
from .config import FIGURES_JSONL, CHARACTERIZED_JSONL, PROJECT_ROOT
from .utils import read_jsonl, write_jsonl


def _resolve_images(record):
    values = record.get("image_paths") or []
    if not values and record.get("image_path"):
        values = [record["image_path"]]
    paths = []
    for value in values:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        paths.append(path)
    return paths


def characterize(input_path=FIGURES_JSONL, output_path=CHARACTERIZED_JSONL,
                 model=None, limit=None, force=False, jobs=1):
    """Classify paper metadata once per paper and each figure once.

    `jobs` is accepted for CLI compatibility; the baseline runs sequentially
    to keep API usage predictable. Parallelism can be added after validating
    the prompt and per-provider rate limits.
    """
    records = read_jsonl(Path(input_path))
    if limit:
        records = records[:limit]
    if not records:
        raise SystemExit(f"No figure records found in {input_path}. Run pull_figures.py first.")

    papers = OrderedDict()
    for record in records:
        papers.setdefault(record.get("pmcid") or record.get("paper_title"), record)

    classifier = VisionClassifier(model=model)
    paper_cache = {}
    previous = {}
    out_path = Path(output_path)
    if out_path.exists() and not force:
        previous = {r.get("figure_uid"): r for r in read_jsonl(out_path)}

    output = []
    try:
        for i, record in enumerate(records, 1):
            uid = record.get("figure_uid")
            if (uid in previous and previous[uid].get("figure_characterization", {}).get("status") == "classified"):
                output.append(previous[uid])
                print(f"[{i}/{len(records)}] cached {uid}")
                continue

            paper_key = record.get("pmcid") or record.get("paper_title")
            paper = papers[paper_key]
            if paper_key not in paper_cache:
                print(f"Characterizing paper: {paper.get('paper_title', paper_key)}")
                try:
                    paper_cache[paper_key] = classifier.classify_paper(paper)
                except Exception as exc:
                    print(f"  Paper classification warning: {exc}")
                    paper_cache[paper_key] = {
                        "publication_type": paper.get("publication_type", "unknown"),
                        "research_fields": [],
                        "subfields": [],
                        "journal_subject_area": "unknown",
                        "reasoning_evidence": "",
                    }

            enriched_paper = {**paper, "paper_characterization": paper_cache[paper_key]}
            try:
                result = classifier.classify_figure(
                    record, enriched_paper, _resolve_images(record)
                )
                characterization = normalize_figure_result(result)
                characterization["model"] = classifier.model
                characterization["status"] = "classified"
            except Exception as exc:
                characterization = {
                    "status": "error",
                    "error": str(exc),
                    "needs_review": True,
                    "confidence": 0.0,
                }

            enriched = {
                **record,
                "paper_characterization": paper_cache[paper_key],
                "figure_characterization": characterization,
            }
            output.append(enriched)
            print(
                f"[{i}/{len(records)}] {uid}: "
                f"{characterization.get('paper_figure_category', characterization['status'])}"
            )
            write_jsonl(out_path, output + records[i:]) if False else None
            # Persist completed work after each figure so interrupted jobs can resume.
            write_jsonl(out_path, output)

    finally:
        classifier.close()

    print("Classification usage:", json.dumps(classifier.usage))
    print(f"Saved {len(output)} records to {out_path}")
    return output
