from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class ExpectedImpact(BaseModel):
    port_disruption: bool = False
    road_disruption: bool = False
    power_outage_risk: bool = False
    manufacturing_disruption: bool = False


class Agent1Input(BaseModel):
    event_id: str
    event_timestamp: datetime
    event_type: str
    event_name: str = ""
    country: str = ""
    affected_regions: List[str] = Field(default_factory=list)
    severity: str = ""
    source: str = ""
    description: str = ""
    expected_impact: ExpectedImpact = Field(default_factory=ExpectedImpact)
    affected_materials: List[str] = Field(default_factory=list)