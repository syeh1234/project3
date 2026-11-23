"""Run paper-level and figure-level AI characterization.

Set OPENAI_API_KEY, then:
    python characterize_figures.py --limit 10
    python characterize_figures.py --force
"""

import argparse
from figurelab.config import FIGURES_JSONL, CHARACTERIZED_JSONL
from figurelab.pipeline import characterize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(FIGURES_JSONL))
    parser.add_argument("--output", default=str(CHARACTERIZED_JSONL))
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    characterize(
        input_path=args.input,
        output_path=args.output,
        model=args.model,
        limit=args.limit,
        force=args.force,
        jobs=args.jobs,
    )


if __name__ == "__main__":
    main()
