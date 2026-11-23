import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse, unquote


def local_name(tag: str) -> str:
    """Return an XML tag's local name, ignoring its namespace."""
    return tag.split("}")[-1] if "}" in tag else tag


def element_text(element) -> str:
    if element is None:
        return ""
    return " ".join(" ".join(element.itertext()).split())


def first_descendant(parent, name: str):
    if parent is None:
        return None
    for element in parent.iter():
        if local_name(element.tag) == name:
            return element
    return None


def safe_filename(value: str, max_length: int = 180) -> str:
    value = re.sub(r"[^\w.-]+", "_", str(value))
    return value[:max_length] or "unnamed"


def convert_s3_to_https(url: str) -> str:
    """Convert PMC's s3:// object URLs to public HTTPS URLs."""
    parsed = urlparse(url)
    if parsed.scheme == "s3":
        return (
            f"https://{parsed.netloc}.s3.amazonaws.com{parsed.path}"
            + (f"?{parsed.query}" if parsed.query else "")
        )
    return url


def url_filename(url: str) -> str:
    return unquote(Path(urlparse(url).path).name)


def atomic_write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}: {exc}"
                ) from exc
    return rows


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + chr(10))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
