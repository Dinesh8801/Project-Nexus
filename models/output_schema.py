from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class BusinessImpact(BaseModel):
    procurement_risk: RiskLevel
    price_escalation_risk: RiskLevel
    inventory_shortage_risk: RiskLevel


class RiskFactor(BaseModel):
    factor: str
    impact: RiskLevel


class Agent2Payload(BaseModel):
    commodity: str
    affected_country: str
    risk_level: RiskLevel
    risk_score: int
    estimated_disruption_days: int


class AgentMetadata(BaseModel):
    agent_name: str = "Predictive Event Ingestion Agent"
    version: str = "1.0"


class DimensionScores(BaseModel):
    severity: int
    geographic: int
    logistics: int
    commodity: int
    inventory: int


class Agent1Output(BaseModel):
    risk_assessment_id: str
    event_id: str
    affected_country: str
    affected_material: str
    event_type: str
    event_severity: str
    risk_level: RiskLevel
    risk_score: int
    confidence_score: float
    supply_disruption_probability: int
    estimated_disruption_days: int
    risk_categories: List[str] = Field(default_factory=list)
    summary: str
    business_impact: BusinessImpact
    risk_reasoning: List[RiskFactor] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    agent_2_payload: Agent2Payload
    activate_agent_2: bool
    assessment_metadata: AgentMetadata = Field(default_factory=AgentMetadata)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")