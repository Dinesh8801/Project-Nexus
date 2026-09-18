"""Assembles the final Agent1_output.json by merging the deterministic rule
engine output with optional LLM enrichment."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

import config
from models.input_schema import Agent1Input
from models.output_schema import (
    Agent1Output,
    Agent2Payload,
    AgentMetadata,
    BusinessImpact,
    DimensionScores,
    RiskFactor,
    RiskLevel,
)
from services import classifier, llm_service, risk_scorer


def build_assessment_id(event_id: str) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:4].upper()
    return f"RA-{date_part}-{event_id}"


def _sanitize_llm_enrichment(data: Optional[dict]) -> dict:
    """Return a safe, validated subset of the LLM response."""
    if not isinstance(data, dict):
        return {}
    safe: dict = {}
    summary = data.get("summary")
    if isinstance(summary, str) and summary.strip():
        safe["summary"] = summary.strip()

    reasoning = data.get("risk_reasoning")
    cleaned_reasoning: List[dict] = []
    if isinstance(reasoning, list):
        for item in reasoning:
            if isinstance(item, dict):
                factor = str(item.get("factor", "")).strip()
                impact = str(item.get("impact", "")).upper().strip()
                if factor and impact in {"LOW", "MEDIUM", "HIGH"}:
                    cleaned_reasoning.append({"factor": factor, "impact": impact})
    if cleaned_reasoning:
        safe["risk_reasoning"] = cleaned_reasoning[:5]

    days = data.get("estimated_disruption_days")
    if isinstance(days, str) and days.strip().isdigit():
        days = int(days.strip())
    if isinstance(days, (int, float)) and 0 <= days <= 365:
        safe["estimated_disruption_days"] = int(days)

    return safe


def generate(event: Agent1Input, inventory_override: Optional[int] = None) -> Agent1Output:
    # ---- Deterministic rule engine ----
    dimensions: DimensionScores = risk_scorer.compute_dimensions(event, inventory_override)
    risk_score: int = risk_scorer.compute_risk_score(dimensions)
    risk_level: RiskLevel = classifier.classify(risk_score)
    affected_material = classifier.affected_material_label(event)
    disruption_probability: int = risk_scorer.compute_disruption_probability(risk_score)
    confidence: float = risk_scorer.compute_confidence(event)
    risk_categories: List[str] = risk_scorer.build_risk_categories(event, risk_level.value)
    business = classifier.business_impact(risk_level)
    actions = classifier.recommended_actions(risk_level)
    rule_reasoning = risk_scorer.build_rule_reasoning(event, dimensions, risk_level.value)
    rule_days = risk_scorer.extract_disruption_days_from_description(event)

    # ---- Fallback fields (rule-derived) ----
    fallback_summary = risk_scorer.default_summary(event, risk_level.value)
    reasoning = rule_reasoning
    estimated_days = rule_days
    final_summary = fallback_summary

    # ---- Optional LLM enrichment (graceful degradation) ----
    llm_payload = llm_service.enrich(event.model_dump(mode="json"))

    if llm_payload:
        safe = _sanitize_llm_enrichment(llm_payload)
        if safe.get("summary"):
            final_summary = safe["summary"]
        if safe.get("risk_reasoning"):
            reasoning = safe["risk_reasoning"]
        if safe.get("estimated_disruption_days") is not None:
            estimated_days = safe["estimated_disruption_days"]

    output = Agent1Output(
        risk_assessment_id=build_assessment_id(event.event_id),
        event_id=event.event_id,
        affected_country=event.country,
        affected_material=affected_material,
        event_type=event.event_type,
        event_severity=event.severity,
        risk_level=risk_level,
        risk_score=risk_score,
        confidence_score=confidence,
        supply_disruption_probability=disruption_probability,
        estimated_disruption_days=estimated_days,
        risk_categories=risk_categories,
        summary=final_summary,
        business_impact=BusinessImpact(
            procurement_risk=RiskLevel(business["procurement_risk"]),
            price_escalation_risk=RiskLevel(business["price_escalation_risk"]),
            inventory_shortage_risk=RiskLevel(business["inventory_shortage_risk"]),
        ),
        risk_reasoning=[RiskFactor(factor=r["factor"], impact=RiskLevel(r["impact"])) for r in reasoning],
        recommended_actions=actions,
        agent_2_payload=Agent2Payload(
            commodity=affected_material,
            affected_country=event.country,
            risk_level=risk_level,
            risk_score=risk_score,
            estimated_disruption_days=estimated_days,
        ),
        activate_agent_2=classifier.activate_agent_2(risk_level),
        assessment_metadata=AgentMetadata(agent_name=config.AGENT_NAME, version=config.VERSION),
    )
    return output