"""Search PMC, download CC-licensed figure images, and save JATS metadata.

Example:
    python pull_figures.py --max-articles 10
    python pull_figures.py --query '"UV-vis spectroscopy" AND chemistry' --max-articles 20
"""

import argparse
import json
import time
from pathlib import Path

from config import (
    DEFAULT_PMC_QUERY, FIGURE_DIR, ARTICLE_DIR, METADATA_DIR,
    FIGURES_JSONL, PAPERS_JSONL, PROJECT_ROOT
)
from pmc import PMCClient, match_images
from jats import (
    extract_article_metadata, extract_section_references, extract_figures
)
from utils import safe_filename, write_jsonl, read_jsonl


def _is_cc_license(code):
    # TDM is not a figure-reuse license. Preserve the exact license code in metadata.
    return bool(code) and code.lower().startswith("cc")


def _upsert(existing, new_records, key):
    by_key = {row.get(key): row for row in existing}
    for row in new_records:
        by_key[row.get(key)] = row
    return list(by_key.values())


def process_article(client, pmcid, download_images=True):
    print(f"\nProcessing PMC{pmcid}")
    versions = client.article_versions(pmcid)
    if not versions:
        print("  No article version found in the PMC AWS dataset.")
        return [], []

    figure_records, paper_records = [], []
    for version in versions:
        print("  Version:", version)
        metadata = client.article_metadata(version)
        license_code = metadata.get("license_code", "")
        pmc_id = metadata.get("pmcid") or f"PMC{pmcid}"

        xml_bytes = client.article_xml(metadata)
        ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
        xml_path = ARTICLE_DIR / f"{version}.xml"
        xml_path.write_bytes(xml_bytes)

        # Parse from saved XML so section characterization can be rerun later
        # without making another network request.
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_bytes)

        pmc_context = {
            "pmcid": pmc_id,
            "pmid": metadata.get("pmid", ""),
            "doi": metadata.get("doi", ""),
            "title": metadata.get("title", ""),
            "citation": metadata.get("citation", ""),
            "license_code": license_code,
            "year": metadata.get("year", ""),
        }
        paper = extract_article_metadata(root, pmc_context)
        paper.update({
            "article_version": version,
            "article_xml_path": str(xml_path.relative_to(PROJECT_ROOT)),
            "metadata_source": "PMC AWS + JATS XML",
        })
        paper_records.append(paper)

        section_refs = extract_section_references(root)
        figures = extract_figures(root, paper, section_refs)

        # Metadata can be retained even when image redistribution is not allowed.
        image_urls = client.image_urls(metadata) if _is_cc_license(license_code) else []
        if not _is_cc_license(license_code):
            print(f"  Not downloading images: license code is {license_code or 'unspecified'}.")

        figures = match_images(figures, image_urls)
        version_figure_dir = FIGURE_DIR / version

        for index, figure in enumerate(figures, 1):
            fig_id = figure.get("figure_id") or f"figure_{index}"
            uid = f"{pmc_id}_{version}_{fig_id}"
            local_paths = []
            if download_images and _is_cc_license(license_code):
                for image in figure.get("matched_images", []):
                    filename = safe_filename(image["filename"])
                    destination = version_figure_dir / filename
                    try:
                        client.download(image["url"], destination)
                        local_paths.append(str(destination.relative_to(PROJECT_ROOT)))
                    except Exception as exc:
                        print(f"    Image download failed ({filename}): {exc}")

            record = {
                **paper,
                "figure_uid": uid,
                "figure_id": fig_id,
                "figure_label": figure.get("figure_label", ""),
                "caption": figure.get("caption", ""),
                "image_filenames": figure.get("image_filenames", []),
                "image_paths": local_paths,
                "image_urls": [x["url"] for x in figure.get("matched_images", [])],
                "primary_image_path": local_paths[0] if local_paths else "",
                "section": figure.get("section", {}),
                "extraction_source": "PMC JATS XML",
            }
            figure_records.append(record)

        print(f"  Figures found: {len(figures)}; local images: {sum(bool(x['image_paths']) for x in figure_records)}")
        client.pause()

    return figure_records, paper_records


def main():
    parser = argparse.ArgumentParser(description="Pull scientific figures from PMC.")
    parser.add_argument("--query", default=DEFAULT_PMC_QUERY)
    parser.add_argument("--max-articles", type=int, default=10)
    parser.add_argument("--no-download-images", action="store_true")
    args = parser.parse_args()

    for directory in (FIGURE_DIR, ARTICLE_DIR, METADATA_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    client = PMCClient()
    pmcids = client.search(args.query, args.max_articles)
    print(f"Found {len(pmcids)} PMC articles.")

    new_figures, new_papers = [], []
    for i, pmcid in enumerate(pmcids, 1):
        print(f"Article {i}/{len(pmcids)}")
        try:
            figures, papers = process_article(
                client, pmcid, download_images=not args.no_download_images
            )
            new_figures.extend(figures)
            new_papers.extend(papers)
        except Exception as exc:
            print(f"  Article failed: {exc}")
        time.sleep(0.4)

    existing_figures = read_jsonl(FIGURES_JSONL)
    existing_papers = read_jsonl(PAPERS_JSONL)
    write_jsonl(FIGURES_JSONL, _upsert(existing_figures, new_figures, "figure_uid"))
    write_jsonl(PAPERS_JSONL, _upsert(existing_papers, new_papers, "pmcid"))

    print("\nFinished.")
    print("New/updated figure records:", len(new_figures))
    print("Metadata file:", FIGURES_JSONL)
    print("Figure directory:", FIGURE_DIR)


if __name__ == "__main__":
    main()
