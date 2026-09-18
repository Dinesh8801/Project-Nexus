"""Agent 1 - Predictive Event Ingestion (Risk Detection Agent).

CLI entry point.

Usage:
    python main.py --input Agent1_input.json --output Agent1_output.json
    python main.py --input data/sample_input.json --skip-llm
    python main.py --input data/sample_input.json --inventory-score 50
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from models.input_schema import Agent1Input
from services.output_generator import generate

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("agent1")

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
logger = logging.getLogger("agent1")


def load_input(path: Path) -> Agent1Input:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return Agent1Input.model_validate(raw)


def run(input_path: Path, output_path: Path, inventory_override: int | None, skip_llm: bool) -> dict:
    event = load_input(input_path)
    if skip_llm:
        import config

        config.LLM_ENABLED = False
    result = generate(event, inventory_override=inventory_override)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    logger.info("Risk assessment complete: level=%s score=%s activate_agent_2=%s",
                result.risk_level.value, result.risk_score, result.activate_agent_2)
    logger.info("Output written to: %s", output_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 1 - Predictive Event Ingestion / Risk Detection")
    parser.add_argument("--input", required=True, help="Path to Agent1_input.json")
    parser.add_argument("--output", default=None, help="Path for Agent1_output.json (default: stdout file alongside input)")
    parser.add_argument("--inventory-score", type=int, default=None, help="Override inventory dimension score (0-100)")
    parser.add_argument("--skip-llm", action="store_true", help="Disable LLM enrichment (pure rules only)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.parent / "Agent1_output.json"

    try:
        payload = run(input_path, output_path, args.inventory_score, args.skip_llm)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        logger.error("Analysis failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()