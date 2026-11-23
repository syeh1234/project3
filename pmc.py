"""PMC E-utilities and PMC AWS access."""

import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests

from .config import (
    EUTILS_URL, PMC_S3_BASE, USER_AGENT, REQUEST_DELAY, IMAGE_EXTENSIONS
)
from .utils import convert_s3_to_https, url_filename


class PMCClient:
    def __init__(self, timeout=60):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.timeout = timeout

    def get(self, url, params=None):
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response

    def search(self, query, max_articles=10):
        params = {
            "db": "pmc", "term": query, "retmax": max_articles,
            "retmode": "json"
        }
        result = self.get(EUTILS_URL, params=params).json()
        return result.get("esearchresult", {}).get("idlist", [])

    def article_versions(self, pmcid):
        prefix = f"PMC{pmcid}."
        response = self.get(
            PMC_S3_BASE + "/",
            params={"list-type": "2", "prefix": prefix, "delimiter": "/"}
        )
        root = ET.fromstring(response.content)
        versions = []
        for element in root.iter():
            if element.tag.split("}")[-1] != "Prefix":
                continue
            value = (element.text or "").strip().rstrip("/")
            if re.fullmatch(rf"PMC{re.escape(str(pmcid))}\.\d+", value):
                versions.append(value)
        return sorted(set(versions))

    def article_metadata(self, version):
        urls = [
            f"{PMC_S3_BASE}/{version}/{version}.json",
            f"{PMC_S3_BASE}/metadata/{version}.json",
        ]
        last_error = None
        for url in urls:
            try:
                return self.get(url).json()
            except requests.HTTPError as exc:
                last_error = exc
        raise last_error or RuntimeError(f"Could not retrieve metadata for {version}")

    def article_xml(self, metadata):
        xml_url = metadata.get("xml_url")
        if not xml_url:
            raise ValueError("PMC metadata does not contain xml_url")
        response = self.get(convert_s3_to_https(xml_url))
        return response.content

    def image_urls(self, metadata):
        output = []
        for raw_url in metadata.get("media_urls", []) or []:
            url = convert_s3_to_https(raw_url)
            suffix = Path(urlparse(url).path).suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                output.append(url)
        return output

    def download(self, url, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.stat().st_size > 0:
            return destination
        response = self.get(url)
        destination.write_bytes(response.content)
        return destination

    @staticmethod
    def pause():
        time.sleep(REQUEST_DELAY)


def match_images(figures, image_urls):
    """Match JATS graphic href basenames to the article's media URLs."""
    lookup = {url_filename(url): url for url in image_urls}
    by_stem = {Path(name).stem.lower(): (name, url) for name, url in lookup.items()}
    for figure in figures:
        matched = []
        for original in figure.get("image_filenames", []):
            name = Path(original).name
            if name in lookup:
                matched.append({"filename": name, "url": lookup[name]})
            elif Path(name).stem.lower() in by_stem:
                found_name, found_url = by_stem[Path(name).stem.lower()]
                matched.append({"filename": found_name, "url": found_url})
        figure["matched_images"] = matched
    return figures
