"""LLM-based risk enrichment using FreeFlow (Groq primary, Gemini fallback).

Enrichment is OPTIONAL. The deterministic rule engine produces the risk score
independently; the LLM only adds qualitative fields (summary, risk_reasoning,
estimated_disruption_days). If the LLM is unavailable (no API keys, rate
limited, network down) this module degrades gracefully to None and the caller
falls back to rule-generated content.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "risk_analysis.txt"


def load_prompt(event_json: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{event_json}", event_json)


def _parse_json_response(content: str) -> Optional[dict]:
    if not content:
        return None
    text = content.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Attempt to extract the first {...} block
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    return data


def _try_freeflow(event_dict: dict) -> Optional[dict]:
    try:
        from freeflow_llm import FreeFlowClient  # type: ignore
    except Exception:
        return None
    if not (config.GROQ_API_KEY or config.GEMINI_API_KEY):
        return None
    try:
        with FreeFlowClient() as client:
            response = client.chat(
                model=config.LLM_PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": load_prompt(json.dumps(event_dict))},
                    {"role": "user", "content": "Enrich this event's risk assessment."},
                ],
                temperature=0.1,
                max_tokens=800,
            )
        return _parse_json_response(response.content)
    except Exception as exc:  # pragma: no cover - rate limit / provider failure
        logger.warning("FreeFlow enrichment failed: %s", exc)
        return None


def _try_groq_direct(event_dict: dict) -> Optional[dict]:
    if not config.GROQ_API_KEY:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    try:
        client = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
        completion = client.chat.completions.create(
            model=config.LLM_PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": load_prompt(json.dumps(event_dict))},
                {"role": "user", "content": "Enrich this event's risk assessment."},
            ],
            temperature=0.1,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        return _parse_json_response(completion.choices[0].message.content)
    except Exception as exc:  # pragma: no cover
        logger.warning("Groq direct enrichment failed: %s", exc)
        return None


def _try_gemini_direct(event_dict: dict) -> Optional[dict]:
    if not config.GEMINI_API_KEY:
        return None
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=config.LLM_FALLBACK_MODEL,
            contents=[
                ("You are a supply chain risk analyst. Return strictly valid JSON only.\n"),
                load_prompt(json.dumps(event_dict)),
            ],
            config={"temperature": 0.1},
        )
        return _parse_json_response(response.text)
    except Exception as exc:  # pragma: no cover
        logger.warning("Gemini enrichment failed: %s", exc)
        return None


def enrich(event_dict: dict) -> Optional[dict]:
    """Attempt LLM enrichment. Returns a dict or None on total failure."""
    if not config.LLM_ENABLED:
        return None

    result = _try_freeflow(event_dict)
    if result is not None:
        logger.info("LLM enrichment used FreeFlow provider")
        return result

    result = _try_groq_direct(event_dict)
    if result is not None:
        logger.info("LLM enrichment used Groq provider")
        return result

    result = _try_gemini_direct(event_dict)
    if result is not None:
        logger.info("LLM enrichment used Gemini provider")
        return result

    logger.info("LLM enrichment unavailable; using rule-based content")
    return None