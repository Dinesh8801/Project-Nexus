"""Risk classification per the 30/60 split and action mapping."""

from __future__ import annotations

import config
from models.input_schema import Agent1Input
from models.output_schema import RiskLevel


def classify(risk_score: int) -> RiskLevel:
    if risk_score <= config.LOW_MAX:
        return RiskLevel.LOW
    if risk_score <= config.MEDIUM_MAX:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def recommended_actions(risk_level: RiskLevel) -> "list[str]":
    return list(config.ACTIONS[risk_level.value])


def business_impact(risk_level: RiskLevel) -> dict:
    if risk_level is RiskLevel.HIGH:
        return {
            "procurement_risk": "HIGH",
            "price_escalation_risk": "HIGH",
            "inventory_shortage_risk": "HIGH",
        }
    if risk_level is RiskLevel.MEDIUM:
        return {
            "procurement_risk": "MEDIUM",
            "price_escalation_risk": "MEDIUM",
            "inventory_shortage_risk": "LOW",
        }
    return {
        "procurement_risk": "LOW",
        "price_escalation_risk": "LOW",
        "inventory_shortage_risk": "LOW",
    }


def activate_agent_2(risk_level: RiskLevel) -> bool:
    return risk_level is RiskLevel.HIGH


def affected_material_label(event: Agent1Input) -> str:
    if event.affected_materials:
        return ", ".join(event.affected_materials)
    return "Unknown"