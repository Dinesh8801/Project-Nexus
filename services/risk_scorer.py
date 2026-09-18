"""Pure-rule (deterministic) risk scoring engine.

Computes the 5 dimension scores from the input event and applies the
weighted Risk Score formula from Risk_Score_Formula.txt:

    Risk Score = Severity*0.30 + Geographic*0.25 + Logistics*0.20
                 + Commodity*0.15 + Inventory*0.10
"""

from __future__ import annotations

import re
from typing import List

import config
from models.input_schema import Agent1Input
from models.output_schema import DimensionScores


def _cap(value: int, upper: int = 100) -> int:
    return max(0, min(upper, value))


def is_natural_disaster(event_type: str) -> bool:
    et = (event_type or "").upper()
    return any(kw in et for kw in config.NATURAL_DISASTER_KEYWORDS)


def score_severity(event: Agent1Input) -> int:
    sev = (event.severity or "").upper()
    base = config.SEVERITY_SCORES.get(sev, config.SEVERITY_DEFAULT)
    if is_natural_disaster(event.event_type):
        base += config.NATURAL_DISASTER_BONUS
    return _cap(base)


def score_geographic(event: Agent1Input) -> int:
    n = len(event.affected_regions)
    base = config.GEO_REGION_SCORES.get(n, config.GEO_REGION_FLAT)
    if event.country.strip().upper() in config.MAJOR_CASHEW_COUNTRIES:
        base += config.PRODUCTION_COUNTRY_BONUS
    return _cap(base)


def score_logistics(event: Agent1Input) -> int:
    impact = event.expected_impact
    total = 0
    for flag, points in config.LOGISTICS_POINTS.items():
        if getattr(impact, flag, False):
            total += points
    return _cap(total)


def score_commodity(event: Agent1Input) -> int:
    materials = [m.strip().lower() for m in event.affected_materials]
    if not materials:
        return _cap(config.COMMODITY_GENERIC_BASE - 10)
    is_cashew = any("cashew" in m for m in materials)
    base = config.COMMODITY_STRATEGIC_BASE if is_cashew else config.COMMODITY_GENERIC_BASE
    if len(materials) >= 2:
        base += config.COMMODITY_MULTI_MATERIAL_BONUS
    if event.country.strip().upper() in config.MAJOR_CASHEW_COUNTRIES:
        base += config.COMMODITY_PRODUCTION_COUNTRY_BONUS
    return _cap(base)


def score_inventory(event: Agent1Input, override: int | None = None) -> int:
    if override is not None:
        return _cap(override)
    return _cap(config.INVENTORY_SCORE_BASE)


def compute_dimensions(event: Agent1Input, inventory_override: int | None = None) -> DimensionScores:
    return DimensionScores(
        severity=score_severity(event),
        geographic=score_geographic(event),
        logistics=score_logistics(event),
        commodity=score_commodity(event),
        inventory=score_inventory(event, inventory_override),
    )


def compute_risk_score(dimensions: DimensionScores) -> int:
    raw = (
        dimensions.severity * config.WEIGHT_SEVERITY
        + dimensions.geographic * config.WEIGHT_GEOGRAPHIC
        + dimensions.logistics * config.WEIGHT_LOGISTICS
        + dimensions.commodity * config.WEIGHT_COMMODITY
        + dimensions.inventory * config.WEIGHT_INVENTORY
    )
    return _cap(int(round(raw)))


def extract_disruption_days_from_description(event: Agent1Input) -> int:
    """Deterministic extraction of disruption duration from the description text.

    Supports patterns like '5-7 days', 'next 5 days', '3 days', 'for 2 weeks'.
    Returns 0 when no duration can be parsed.
    """
    text = (event.description or "")[:400]
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*(?:days|day)", text, re.IGNORECASE)
    if m:
        low, high = int(m.group(1)), int(m.group(2))
        return max(low, high)
    m = re.search(r"(?:next|up to|within|for)\s+(\d+)\s*(?:days|day)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(?:days|day)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(?:weeks|week)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 7
    return 0


def compute_confidence(event: Agent1Input) -> float:
    conf = config.CONFIDENCE_BASE
    if event.description.strip():
        conf += config.CONFIDENCE_DESCRIPTION_BONUS
    if event.source.strip():
        conf += config.CONFIDENCE_SOURCE_BONUS
    if event.affected_regions:
        conf += config.CONFIDENCE_REGIONS_BONUS
    return round(min(config.CONFIDENCE_CAP, conf), 2)


def compute_disruption_probability(risk_score: int) -> int:
    return min(config.DISRUPTION_PROBABILITY_CAP, round(risk_score * config.DISRUPTION_PROBABILITY_FACTOR))


def classify_risk(risk_score: int) -> str:
    if risk_score <= config.LOW_MAX:
        return "LOW"
    if risk_score <= config.MEDIUM_MAX:
        return "MEDIUM"
    return "HIGH"


def build_risk_categories(event: Agent1Input, risk_level: str) -> List[str]:
    categories: List[str] = []
    natural = is_natural_disaster(event.event_type)
    if natural:
        categories.append("NATURAL_DISASTER")
    impact = event.expected_impact
    logistic_flags = [getattr(impact, flag, False) for flag in config.LOGISTICS_POINTS]
    if not natural and any(logistic_flags):
        categories.append("LOGISTICS_DISRUPTION")
    if event.affected_materials:
        categories.append("PROCUREMENT_RISK")
        categories.append("SUPPLY_DISRUPTION")
    if not categories and any(logistic_flags):
        categories.append("LOGISTICS_DISRUPTION")
    if not categories:
        categories.append("SUPPLY_DISRUPTION")
    return categories


def default_summary(event: Agent1Input, risk_level: str) -> str:
    country = event.country or "the affected region"
    material = ", ".join(event.affected_materials) or "supply"
    evt = event.event_type or "event"
    return (
        f"A {risk_level} supply risk is assessed for '{material}' from {country} "
        f"following the reported {evt} event ({event.event_id})."
    )


def build_rule_reasoning(event: Agent1Input, dimensions: DimensionScores, risk_level: str) -> List[dict]:
    reasons: List[dict] = []
    sev_label = risk_level if dimensions.severity >= 61 else ("MEDIUM" if dimensions.severity >= 31 else "LOW")
    reasons.append({"factor": f"{event.event_type or 'Event'} severity", "impact": sev_label})
    geo_label = risk_level if dimensions.geographic >= 61 else ("MEDIUM" if dimensions.geographic >= 31 else "LOW")
    reasons.append({"factor": "Geographic impact concentration", "impact": geo_label})
    log_label = risk_level if dimensions.logistics >= 61 else ("MEDIUM" if dimensions.logistics >= 31 else "LOW")
    reasons.append({"factor": "Logistics disruption exposure", "impact": log_label})
    if event.affected_materials:
        reasons.append({"factor": "Supply concentration", "impact": risk_level})
    return reasons