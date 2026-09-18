"""Tests for Agent 1 (deterministic rule engine path, no LLM required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402

config.LLM_ENABLED = False  # force pure-rules path for all tests

from models.input_schema import Agent1Input, ExpectedImpact  # noqa: E402
from models.output_schema import RiskLevel  # noqa: E402
from services import classifier, risk_scorer  # noqa: E402
from services.output_generator import generate  # noqa: E402

SAMPLE_INPUT = PROJECT_ROOT / "data" / "Agent1_input.json"


def sample_event() -> Agent1Input:
    if SAMPLE_INPUT.exists():
        import json

        with open(SAMPLE_INPUT, "r", encoding="utf-8") as fh:
            return Agent1Input.model_validate(json.load(fh))
    return Agent1Input(
        event_id="EVT-2026-001",
        event_timestamp="2026-09-15T04:30:00Z",
        event_type="Typhoon",
        event_name="Typhoon Hai Phong",
        country="Vietnam",
        affected_regions=["Hai Phong", "Quang Ninh", "Da Nang"],
        severity="SEVERE",
        source="National Weather Authority",
        description="Typhoon warning issued across northern and central Vietnam. Ports may face closures and transportation interruptions for the next 5-7 days.",
        expected_impact=ExpectedImpact(
            port_disruption=True,
            road_disruption=True,
            power_outage_risk=True,
            manufacturing_disruption=True,
        ),
        affected_materials=["Cashew Nuts"],
    )


# --- Severity scoring ---

def test_severity_severe_natural_disaster():
    ev = sample_event()
    assert risk_scorer.score_severity(ev) == 95  # SEVERE=90 + natural disaster bonus 5


def test_severity_moderate():
    ev = sample_event()
    ev.event_type = "Port Strike"
    ev.severity = "MODERATE"
    assert risk_scorer.score_severity(ev) == 55


# --- Geographic scoring ---

def test_geographic_three_regions_production_country():
    ev = sample_event()
    assert risk_scorer.score_geographic(ev) == 75  # 55 + 20 (Vietnam)


def test_geographic_unknown_country_no_bonus():
    ev = sample_event()
    ev.country = "Fiji"
    assert risk_scorer.score_geographic(ev) == 55


# --- Logistics scoring ---

def test_logistics_all_impacts_cap():
    ev = sample_event()
    assert risk_scorer.score_logistics(ev) == 100  # 45+25+20+20 = 110 -> capped 100


def test_logistics_none():
    ev = sample_event()
    ev.expected_impact = ExpectedImpact(
        port_disruption=False,
        road_disruption=False,
        power_outage_risk=False,
        manufacturing_disruption=False,
    )
    assert risk_scorer.score_logistics(ev) == 0


# --- Commodity scoring ---

def test_commodity_cashew_in_production_country():
    ev = sample_event()
    assert risk_scorer.score_commodity(ev) == 80  # 70 + 10 (Vietnam)


def test_commodity_generic_material():
    ev = sample_event()
    ev.affected_materials = ["Steel"]
    ev.country = "Fiji"
    assert risk_scorer.score_commodity(ev) == 40


# --- Weighted formula ---

def test_weighted_risk_score_matches_expected_range():
    ev = sample_event()
    dims = risk_scorer.compute_dimensions(ev)
    score = risk_scorer.compute_risk_score(dims)
    # Expected: 95*.30 + 75*.25 + 100*.20 + 80*.15 + 30*.10 = 82.25 -> 82
    assert score == 82
    assert classifier.classify(score) is RiskLevel.HIGH


# --- Risk bands ---

def test_bands():
    assert classifier.classify(10) is RiskLevel.LOW
    assert classifier.classify(30) is RiskLevel.LOW
    assert classifier.classify(31) is RiskLevel.MEDIUM
    assert classifier.classify(60) is RiskLevel.MEDIUM
    assert classifier.classify(61) is RiskLevel.HIGH
    assert classifier.classify(100) is RiskLevel.HIGH


# --- End-to-end deterministic output ---

def test_generate_output_contract():
    ev = sample_event()
    result = generate(ev)

    assert result.risk_score == 82
    assert result.risk_level is RiskLevel.HIGH
    assert result.affected_country == "Vietnam"
    assert result.affected_material == "Cashew Nuts"
    assert result.activate_agent_2 is True
    assert result.agent_2_payload.risk_score == 82
    assert result.agent_2_payload.risk_level is RiskLevel.HIGH
    assert result.agent_2_payload.affected_country == "Vietnam"
    assert result.agent_2_payload.commodity == "Cashew Nuts"
    assert result.confidence_score == 0.92
    assert result.supply_disruption_probability == 78  # round(82*0.95)
    assert "NATURAL_DISASTER" in result.risk_categories
    assert "PROCUREMENT_RISK" in result.risk_categories
    assert "SUPPLY_DISRUPTION" in result.risk_categories
    assert result.estimated_disruption_days == 7  # parsed from "next 5-7 days"
    assert len(result.recommended_actions) >= 3
    assert result.assessment_metadata.agent_name == config.AGENT_NAME


def test_determinism():
    ev = sample_event()
    a = generate(ev).model_dump(mode="json")
    b = generate(ev).model_dump(mode="json")
    assert a == b


def test_low_risk_event():
    ev = sample_event()
    ev.severity = "MINOR"
    ev.event_type = "Localized Festival"
    ev.country = "Fiji"
    ev.affected_regions = ["Suva"]
    ev.expected_impact = ExpectedImpact(
        port_disruption=False,
        road_disruption=False,
        power_outage_risk=False,
        manufacturing_disruption=False,
    )
    ev.description = ""
    result = generate(ev)
    assert result.risk_level is RiskLevel.LOW
    assert result.risk_score <= 30
    assert result.activate_agent_2 is False


def test_medium_risk_event():
    ev = sample_event()
    ev.severity = "MODERATE"
    ev.event_type = "Port Congestion"
    ev.country = "Indonesia"
    ev.affected_regions = ["Jakarta"]
    ev.expected_impact = ExpectedImpact(
        port_disruption=True,
        road_disruption=False,
        power_outage_risk=False,
        manufacturing_disruption=False,
    )
    ev.description = "Port congestion may cause delays of up to 3 days."
    result = generate(ev)
    assert result.risk_level is RiskLevel.MEDIUM
    assert 31 <= result.risk_score <= 60
    assert result.activate_agent_2 is False
    assert result.estimated_disruption_days == 3


def test_output_complete_when_llm_offline():
    """With LLM disabled, output must still be schema-complete."""
    ev = sample_event()
    result = generate(ev)
    assert result.summary.strip()
    assert len(result.risk_reasoning) >= 1
    assert result.risk_reasoning[0].factor.strip()