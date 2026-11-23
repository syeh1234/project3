"""Google Gemini multimodal classification with cached, structured results."""

import base64
import io
import json
import os
import re
import time
from pathlib import Path

import httpx
from PIL import Image

from taxonomy import (
    PAPER_FIGURE_CATEGORIES, VISUAL_TYPES, CHART_TYPES,
    EXPERIMENTAL_TECHNIQUES, VISUALIZATION_PURPOSES,
    PUBLICATION_TYPES, RESEARCH_FIELDS
)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

PAPER_SYSTEM_PROMPT = f"""
You characterize scientific papers for a searchable educational figure library.
Return only one valid JSON object with these keys:
publication_type: one of {PUBLICATION_TYPES}
research_fields: array using {RESEARCH_FIELDS}
subfields: array of specific scientific subfields, preferably concise canonical names
journal_subject_area: a concise area suggested by the journal name and paper context, or "unknown"
reasoning_evidence: brief evidence from title, abstract, or article metadata
Do not infer a journal's official scope from its name alone. Mark uncertain fields unknown.
"""

FIGURE_SYSTEM_PROMPT = f"""
You characterize scientific figures from chemistry, materials science, chemical
engineering, physics, biology, and related research papers.

Return ONLY a valid JSON object with these keys:
paper_figure_category: one of {PAPER_FIGURE_CATEGORIES}
visual_types: array using {VISUAL_TYPES}
chart_types: array using {CHART_TYPES}
experimental_techniques: array using {EXPERIMENTAL_TECHNIQUES}
technique_groups: array using spectroscopy, microscopy, electrochemistry,
chromatography, thermal_analysis, diffraction, mechanical_testing, synthesis,
computational_modeling, imaging, other, unknown
visualization_purposes: array using {VISUALIZATION_PURPOSES}
data_characteristics: qualitative | quantitative | mixed | unknown
variables: array of objects with name, axis (x, y, z, color, other), and unit
description: concise plain-language description of what the figure shows
style_tags: 2 to 6 short lowercase visual descriptors
panel_count: integer or null
panels: array of objects with panel_label, paper_figure_category, visual_type,
experimental_technique, visualization_purpose, description
confidence: number from 0 to 1
needs_review: boolean
evidence: brief explanation citing visible features, caption, or paper context

Rules:
- Use the image as the primary evidence for visual type and figure category.
- Use caption and article context to identify experimental technique.
- Do not infer a technique solely from the visual appearance of a graph.
- Distinguish a data chart from a method diagram, conceptual illustration,
  molecular structure, microscopy image, photograph, and table.
- Multi-panel figures may have multiple visual types and techniques.
- Use "unknown" or an empty array when evidence is insufficient; never guess.
- Do not decide which paper section the figure belongs to. That is extracted
  separately from the article XML.
- Keep descriptions factual; do not claim results that are not evident.
"""


def _image_base64(path: Path, max_side=1200):
    """Resize an image and return its JPEG data as base64."""
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=88)

    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _json_from_response(text):
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    return json.loads(text)


class VisionClassifier:
    def __init__(self, model=None, api_key=None, timeout=120):
        self.model = (
            model
            or os.getenv("FIGURELAB_VISION_MODEL", "gemini-3.1-flash-lite")
        )

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise RuntimeError(
                "Set GEMINI_API_KEY before running classification."
            )

        self.url = f"{GEMINI_API_URL}/{self.model}:generateContent"

        self.client = httpx.Client(timeout=timeout, trust_env=False)

        self.usage = {
            "calls": 0,
            "errors": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

    def _chat_json(self, system_prompt, user_parts, max_tokens=1200):
        body = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": user_parts,
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }

        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        last_error = None

        for attempt in range(3):
            try:
                response = self.client.post(
                    self.url,
                    json=body,
                    headers=headers,
                )

                if response.status_code == 429 or response.status_code >= 500:
                    last_error = (
                        f"HTTP {response.status_code}: "
                        f"{response.text[:400]}"
                    )

                    if attempt < 2:
                        time.sleep(2 + attempt * 3)
                        continue

                    break

                if not response.is_success:
                    raise RuntimeError(
                        f"Gemini API returned {response.status_code}: "
                        f"{response.text[:600]}"
                    )

                data = response.json()

                candidates = data.get("candidates", [])

                if not candidates:
                    raise RuntimeError(
                        "Gemini returned no candidates: "
                        + json.dumps(data)[:600]
                    )

                parts = candidates[0].get("content", {}).get("parts", [])
                response_text = "".join(
                    part.get("text", "")
                    for part in parts
                    if "text" in part
                )

                if not response_text:
                    raise RuntimeError(
                        "Gemini returned an empty text response."
                    )

                usage = data.get("usageMetadata", {})

                self.usage["calls"] += 1
                self.usage["prompt_tokens"] += usage.get(
                    "promptTokenCount", 0
                )
                self.usage["completion_tokens"] += usage.get(
                    "candidatesTokenCount", 0
                )

                return _json_from_response(response_text)

            except RuntimeError:
                self.usage["errors"] += 1
                raise

            except Exception as exc:
                last_error = repr(exc)

                if attempt < 2:
                    time.sleep(2 + attempt * 3)

        self.usage["errors"] += 1
        raise RuntimeError(last_error or "Unknown Gemini API error")

    def classify_paper(self, paper):
        context = {
            "title": paper.get("paper_title", ""),
            "abstract": (paper.get("abstract", "") or "")[:5000],
            "journal": paper.get("journal", ""),
            "article_type_raw": paper.get("article_type_raw", ""),
            "publication_year": paper.get("publication_year", ""),
            "article_subjects": paper.get("article_subjects", []),
        }

        return self._chat_json(
            PAPER_SYSTEM_PROMPT,
            [{
                "text": json.dumps(context, ensure_ascii=False)
            }],
            max_tokens=500,
        )

    def classify_figure(self, figure, paper, image_paths):
        paths = [
            Path(p)
            for p in image_paths
            if p and Path(p).exists()
        ]

        if not paths:
            raise FileNotFoundError(
                f"No local image found for {figure.get('figure_uid')}"
            )

        text = (
            "Paper context:\n"
            + json.dumps({
                "title": paper.get("paper_title", ""),
                "journal": paper.get("journal", ""),
                "publication_type": paper.get("publication_type", ""),
                "abstract": (paper.get("abstract", "") or "")[:2500],
                "paper_characterization": paper.get(
                    "paper_characterization", {}
                ),
            }, ensure_ascii=False)
            + "\nFigure caption:\n"
            + (figure.get("caption", "") or "")[:2500]
            + "\nSection placement extracted from JATS XML:\n"
            + json.dumps(figure.get("section", {}), ensure_ascii=False)
        )

        parts = [{"text": text}]

        for path in paths[:3]:
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": _image_base64(path),
                }
            })

        return self._chat_json(
            FIGURE_SYSTEM_PROMPT,
            parts,
            max_tokens=1600,
        )

    def close(self):
        self.client.close()


def normalize_figure_result(result):
    """Normalize the model response into stable fields without inventing labels."""

    allowed = {
        "paper_figure_category": set(PAPER_FIGURE_CATEGORIES),
        "visual_types": set(VISUAL_TYPES),
        "chart_types": set(CHART_TYPES),
        "experimental_techniques": set(EXPERIMENTAL_TECHNIQUES),
        "visualization_purposes": set(VISUALIZATION_PURPOSES),
    }

    category = str(
        result.get("paper_figure_category", "other")
    ).lower().strip()

    if category not in allowed["paper_figure_category"]:
        category = "other"

    def clean_list(key):
        value = result.get(key) or []

        if isinstance(value, str):
            value = [value]

        values = []

        for item in value:
            item = str(item).strip()

            if item in allowed[key] and item not in values:
                values.append(item)

        return values

    confidence = result.get("confidence", 0)

    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0

    panels = result.get("panels") or []

    if not isinstance(panels, list):
        panels = []

    variables = result.get("variables") or []

    if not isinstance(variables, list):
        variables = []

    return {
        "paper_figure_category": category,
        "visual_types": clean_list("visual_types"),
        "chart_types": clean_list("chart_types"),
        "experimental_techniques": clean_list(
            "experimental_techniques"
        ),
        "technique_groups": result.get("technique_groups") or [],
        "visualization_purposes": clean_list(
            "visualization_purposes"
        ),
        "data_characteristics": result.get(
            "data_characteristics", "unknown"
        ),
        "variables": variables,
        "description": str(
            result.get("description", "")
        ).strip(),
        "style_tags": [
            str(x).strip().lower()
            for x in (result.get("style_tags") or [])
            if str(x).strip()
        ][:8],
        "panel_count": result.get("panel_count"),
        "panels": panels,
        "confidence": confidence,
        "needs_review": bool(
            result.get("needs_review", confidence < 0.75)
        ),
        "evidence": str(
            result.get("evidence", "")
        ).strip(),
        "model": None,
    }
