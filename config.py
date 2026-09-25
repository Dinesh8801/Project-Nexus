from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

AGENT_NAME = "Predictive Event Ingestion Agent"
VERSION = "1.0"

# --- Risk score formula weights (Risk_Score_Formula.txt) ---
WEIGHT_SEVERITY = 0.30
WEIGHT_GEOGRAPHIC = 0.25
WEIGHT_LOGISTICS = 0.20
WEIGHT_COMMODITY = 0.15
WEIGHT_INVENTORY = 0.10

# --- Risk bands (30/60 split) ---
# LOW: 0-30, MEDIUM: 31-60, HIGH: 61-100
LOW_MAX = 30
MEDIUM_MAX = 60

# --- Severity mapping ---
SEVERITY_SCORES = {
    "SEVERE": 90,
    "HIGH": 75,
    "MODERATE": 55,
    "LOW": 25,
    "MILD": 25,
    "MINOR": 10,
}
SEVERITY_DEFAULT = 50

# --- Natural disaster event types (case-insensitive substring match) ---
NATURAL_DISASTER_KEYWORDS = [
    "TYPHOON",
    "CYCLONE",
    "HURRICANE",
    "EARTHQUAKE",
    "FLOOD",
    "TSUNAMI",
    "VOLCANO",
    "ERUPTION",
    "STORM",
    "DROUGHT",
    "LANDSLIDE",
    "AVALANCHE",
]

NATURAL_DISASTER_BONUS = 5

# --- Geographic scoring ---
GEO_REGION_SCORES = {
    0: 20,
    1: 30,
    2: 55,
    3: 55,
    4: 70,
    5: 70,
    6: 80,
    7: 80,
}
GEO_REGION_FLAT = 90  # applied when more regions than the map handles
PRODUCTION_COUNTRY_BONUS = 20

# --- Major cashew producing / exporting countries (for context scoring) ---
MAJOR_CASHEW_COUNTRIES = {
    "VIETNAM",
    "INDIA",
    "PHILIPPINES",
    "IVORY COAST",
    "COTE D'IVOIRE",
    "CÔTE D'IVOIRE",
    "TANZANIA",
    "BRAZIL",
    "INDONESIA",
    "NIGERIA",
    "MOZAMBIQUE",
    "GHANA",
    "BENIN",
    "BURKINA FASO",
    "GUINEA-BISSAU",
}

# --- Logistics scoring (expected_impact flags) ---
LOGISTICS_POINTS = {
    "port_disruption": 45,
    "road_disruption": 25,
    "power_outage_risk": 20,
    "manufacturing_disruption": 20,
}

# --- Commodity scoring ---
COMMODITY_STRATEGIC_BASE = 70  # cashew (strategic material)
COMMODITY_GENERIC_BASE = 40
COMMODITY_MULTI_MATERIAL_BONUS = 10
COMMODITY_PRODUCTION_COUNTRY_BONUS = 10

# --- Inventory scoring (no inventory data in Agent1 input) ---
INVENTORY_SCORE_BASE = int(os.getenv("INVENTORY_SCORE_BASE", "30"))

# --- Confidence scoring ---
CONFIDENCE_BASE = 0.80
CONFIDENCE_DESCRIPTION_BONUS = 0.05
CONFIDENCE_SOURCE_BONUS = 0.04
CONFIDENCE_REGIONS_BONUS = 0.03
CONFIDENCE_CAP = 0.98

# --- Supply disruption probability mapping ---
DISRUPTION_PROBABILITY_FACTOR = 0.95
DISRUPTION_PROBABILITY_CAP = 95

# --- Recommended actions by risk level ---
ACTIONS = {
    "LOW": [
        "Monitor situation",
        "Log event for reference",
        "Notify standby contact",
    ],
    "MEDIUM": [
        "Prepare contingency plan",
        "Review supplier availability",
        "Monitor event for next 48 hours",
    ],
    "HIGH": [
        "Identify alternate approved suppliers",
        "Review available inventory",
        "Initiate procurement contingency plan",
    ],
}

# --- LLM provider configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_PRIMARY_MODEL = os.getenv("LLM_PRIMARY_MODEL", "openai/gpt-oss-120b")
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "gemini-3.6-flash")

# Whether LLM enrichment is enabled (default on, but degrades gracefully)
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("1", "true", "yes")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"