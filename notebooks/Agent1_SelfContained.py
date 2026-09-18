# COMMAND ----------
# MAGIC %md
# MAGIC # Agent 1 — Risk Detection (100% self-contained)
# MAGIC # MAGIC
# MAGIC # MAGIC Everything needed is embedded in this notebook: the full Agent 1 source code,
# MAGIC # MAGIC the LLM prompt, and 6 demo scenarios. **No repo upload required, nothing to
# MAGIC # MAGIC download from any laptop — it runs completely on Databricks.**
# MAGIC # MAGIC
# MAGIC # MAGIC ---- What it does ----
# MAGIC # MAGIC 1. Installs the exact packages we use (FreeFlow -> Groq, Gemini fallback)
# MAGIC # MAGIC 2. Reads your API keys (you provide them once — see Step 2)
# MAGIC # MAGIC 3. Loads Agent 1 (risk scoring engine + LLM enrichment) into memory
# MAGIC # MAGIC 4. Runs all 6 demo events and prints `Agent1_output` for each
# MAGIC # MAGIC 5. **Saves results to Databricks**: a Delta table + JSON files, so Agent 2 can
# MAGIC # MAGIC    pick them up right here on Databricks
# MAGIC # MAGIC 6. Lets you analyze your own custom event
# MAGIC # MAGIC
# MAGIC # MAGIC Expected final line: `Risk score: 82 | Level: HIGH | activate_agent_2: True`
# MAGIC # MAGIC
# MAGIC # MAGIC Just attach a cluster and click **Run All**.
# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install the same packages we use locally
# COMMAND ----------
# MAGIC %pip install freeflow-llm openai google-genai pydantic>=2 python-dotenv
# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Provide the API keys (done once per notebook run)
# MAGIC # MAGIC
# MAGIC # MAGIC Two ways — pick one:
# MAGIC # MAGIC  - **Widgets (quick):** click the Run bar and fill `groq_api_key` / `gemini_api_key`.
# MAGIC # MAGIC  - **Secrets (permanent):** run once in any notebook:
# MAGIC # MAGIC    `dbutils.secrets.createScope("agent-scope")` then
# MAGIC # MAGIC    `dbutils.secrets.put("agent-scope","groq_api_key","gsk_...")` and
# MAGIC # MAGIC    `dbutils.secrets.put("agent-scope","gemini_api_key","AIza...")`.
# MAGIC # MAGIC
# MAGIC # MAGIC If no keys are provided, the LLM part is skipped and Agent 1 still works
# MAGIC # MAGIC (pure rule engine) — it degrades gracefully.
# COMMAND ----------
import os

# Widgets first (fill the boxes in the Run bar)
GROQ_KEY = dbutils.widgets.get('groq_api_key')
GEM_KEY = dbutils.widgets.get('gemini_api_key')

# Fallback to secrets if widgets are blank
try:
    GROQ_KEY = GROQ_KEY or dbutils.secrets.get('agent-scope', 'groq_api_key')
except Exception:
    pass
try:
    GEM_KEY = GEM_KEY or dbutils.secrets.get('agent-scope', 'gemini_api_key')
except Exception:
    pass

os.environ['GROQ_API_KEY'] = GROQ_KEY or ''
os.environ['GEMINI_API_KEY'] = GEM_KEY or ''
os.environ['LLM_ENABLED'] = 'true'
os.environ['LLM_PRIMARY_MODEL'] = 'openai/gpt-oss-120b'
os.environ['LLM_FALLBACK_MODEL'] = 'gemini-3.6-flash'

print('Groq key loaded:', bool(os.environ['GROQ_API_KEY']))
print('Gemini key loaded:', bool(os.environ['GEMINI_API_KEY']))
# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Load Agent 1 into memory (embedded source, nothing from disk)
# MAGIC # MAGIC
# MAGIC # MAGIC This rebuilds the exact same `config.py`, `models/`, `services/` modules we run
# MAGIC # MAGIC locally — inside the notebook, so nothing needs to be uploaded.
# COMMAND ----------
import sys, types

def _boot_module(name, src):
    m = types.ModuleType(name)
    exec(compile(src, name, 'exec'), m.__dict__)
    sys.modules[name] = m
    return m

# -- config --
_boot_module('config', 'from __future__ import annotations\n\nimport os\n\nfrom dotenv import load_dotenv\n\nload_dotenv()\n\nAGENT_NAME = "Predictive Event Ingestion Agent"\nVERSION = "1.0"\n\n# --- Risk score formula weights (Risk_Score_Formula.txt) ---\nWEIGHT_SEVERITY = 0.30\nWEIGHT_GEOGRAPHIC = 0.25\nWEIGHT_LOGISTICS = 0.20\nWEIGHT_COMMODITY = 0.15\nWEIGHT_INVENTORY = 0.10\n\n# --- Risk bands (30/60 split) ---\n# LOW: 0-30, MEDIUM: 31-60, HIGH: 61-100\nLOW_MAX = 30\nMEDIUM_MAX = 60\n\n# --- Severity mapping ---\nSEVERITY_SCORES = {\n    "SEVERE": 90,\n    "HIGH": 75,\n    "MODERATE": 55,\n    "LOW": 25,\n    "MILD": 25,\n    "MINOR": 10,\n}\nSEVERITY_DEFAULT = 50\n\n# --- Natural disaster event types (case-insensitive substring match) ---\nNATURAL_DISASTER_KEYWORDS = [\n    "TYPHOON",\n    "CYCLONE",\n    "HURRICANE",\n    "EARTHQUAKE",\n    "FLOOD",\n    "TSUNAMI",\n    "VOLCANO",\n    "ERUPTION",\n    "STORM",\n    "DROUGHT",\n    "LANDSLIDE",\n]\n\nNATURAL_DISASTER_BONUS = 5\n\n# --- Geographic scoring ---\nGEO_REGION_SCORES = {\n    0: 20,\n    1: 30,\n    2: 55,\n    3: 55,\n    4: 70,\n    5: 70,\n    6: 80,\n    7: 80,\n}\nGEO_REGION_FLAT = 90  # applied when more regions than the map handles\nPRODUCTION_COUNTRY_BONUS = 20\n\n# --- Major cashew producing / exporting countries (for context scoring) ---\nMAJOR_CASHEW_COUNTRIES = {\n    "VIETNAM",\n    "INDIA",\n    "PHILIPPINES",\n    "IVORY COAST",\n    "COTE D\'IVOIRE",\n    "CÔTE D\'IVOIRE",\n    "TANZANIA",\n    "BRAZIL",\n    "INDONESIA",\n    "NIGERIA",\n    "MOZAMBIQUE",\n    "GHANA",\n    "BENIN",\n    "BURKINA FASO",\n    "GUINEA-BISSAU",\n}\n\n# --- Logistics scoring (expected_impact flags) ---\nLOGISTICS_POINTS = {\n    "port_disruption": 45,\n    "road_disruption": 25,\n    "power_outage_risk": 20,\n    "manufacturing_disruption": 20,\n}\n\n# --- Commodity scoring ---\nCOMMODITY_STRATEGIC_BASE = 70  # cashew (strategic material)\nCOMMODITY_GENERIC_BASE = 40\nCOMMODITY_MULTI_MATERIAL_BONUS = 10\nCOMMODITY_PRODUCTION_COUNTRY_BONUS = 10\n\n# --- Inventory scoring (no inventory data in Agent1 input) ---\nINVENTORY_SCORE_BASE = int(os.getenv("INVENTORY_SCORE_BASE", "30"))\n\n# --- Confidence scoring ---\nCONFIDENCE_BASE = 0.80\nCONFIDENCE_DESCRIPTION_BONUS = 0.05\nCONFIDENCE_SOURCE_BONUS = 0.04\nCONFIDENCE_REGIONS_BONUS = 0.03\nCONFIDENCE_CAP = 0.98\n\n# --- Supply disruption probability mapping ---\nDISRUPTION_PROBABILITY_FACTOR = 0.95\nDISRUPTION_PROBABILITY_CAP = 95\n\n# --- Recommended actions by risk level ---\nACTIONS = {\n    "LOW": [\n        "Monitor situation",\n        "Log event for reference",\n        "Notify standby contact",\n    ],\n    "MEDIUM": [\n        "Prepare contingency plan",\n        "Review supplier availability",\n        "Monitor event for next 48 hours",\n    ],\n    "HIGH": [\n        "Identify alternate approved suppliers",\n        "Review available inventory",\n        "Initiate procurement contingency plan",\n    ],\n}\n\n# --- LLM provider configuration ---\nGROQ_API_KEY = os.getenv("GROQ_API_KEY", "")\nGEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")\nLLM_PRIMARY_MODEL = os.getenv("LLM_PRIMARY_MODEL", "openai/gpt-oss-120b")\nLLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "gemini-3.6-flash")\n\n# Whether LLM enrichment is enabled (default on, but degrades gracefully)\nLLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("1", "true", "yes")\n\nGROQ_BASE_URL = "https://api.groq.com/openai/v1"')

# -- models package --
_models = types.ModuleType('models'); _models.__path__ = []
sys.modules['models'] = _models
_boot_module('models.input_schema', 'from __future__ import annotations\n\nfrom datetime import datetime\nfrom typing import List\n\nfrom pydantic import BaseModel, Field\n\n\nclass ExpectedImpact(BaseModel):\n    port_disruption: bool = False\n    road_disruption: bool = False\n    power_outage_risk: bool = False\n    manufacturing_disruption: bool = False\n\n\nclass Agent1Input(BaseModel):\n    event_id: str\n    event_timestamp: datetime\n    event_type: str\n    event_name: str = ""\n    country: str = ""\n    affected_regions: List[str] = Field(default_factory=list)\n    severity: str = ""\n    source: str = ""\n    description: str = ""\n    expected_impact: ExpectedImpact = Field(default_factory=ExpectedImpact)\n    affected_materials: List[str] = Field(default_factory=list)')
_boot_module('models.output_schema', 'from __future__ import annotations\n\nfrom enum import Enum\nfrom typing import List, Optional\n\nfrom pydantic import BaseModel, Field\n\n\nclass RiskLevel(str, Enum):\n    LOW = "LOW"\n    MEDIUM = "MEDIUM"\n    HIGH = "HIGH"\n\n\nclass BusinessImpact(BaseModel):\n    procurement_risk: RiskLevel\n    price_escalation_risk: RiskLevel\n    inventory_shortage_risk: RiskLevel\n\n\nclass RiskFactor(BaseModel):\n    factor: str\n    impact: RiskLevel\n\n\nclass Agent2Payload(BaseModel):\n    commodity: str\n    affected_country: str\n    risk_level: RiskLevel\n    risk_score: int\n    estimated_disruption_days: int\n\n\nclass AgentMetadata(BaseModel):\n    agent_name: str = "Predictive Event Ingestion Agent"\n    version: str = "1.0"\n\n\nclass DimensionScores(BaseModel):\n    severity: int\n    geographic: int\n    logistics: int\n    commodity: int\n    inventory: int\n\n\nclass Agent1Output(BaseModel):\n    risk_assessment_id: str\n    event_id: str\n    affected_country: str\n    affected_material: str\n    event_type: str\n    event_severity: str\n    risk_level: RiskLevel\n    risk_score: int\n    confidence_score: float\n    supply_disruption_probability: int\n    estimated_disruption_days: int\n    risk_categories: List[str] = Field(default_factory=list)\n    summary: str\n    business_impact: BusinessImpact\n    risk_reasoning: List[RiskFactor] = Field(default_factory=list)\n    recommended_actions: List[str] = Field(default_factory=list)\n    agent_2_payload: Agent2Payload\n    activate_agent_2: bool\n    assessment_metadata: AgentMetadata = Field(default_factory=AgentMetadata)\n\n    def to_dict(self) -> dict:\n        return self.model_dump(mode="json")')
_models.input_schema = sys.modules['models.input_schema']
_models.output_schema = sys.modules['models.output_schema']

# -- services package --
_services = types.ModuleType('services'); _services.__path__ = []
sys.modules['services'] = _services
_boot_module('services.risk_scorer', '"""Pure-rule (deterministic) risk scoring engine.\n\nComputes the 5 dimension scores from the input event and applies the\nweighted Risk Score formula from Risk_Score_Formula.txt:\n\n    Risk Score = Severity*0.30 + Geographic*0.25 + Logistics*0.20\n                 + Commodity*0.15 + Inventory*0.10\n"""\n\nfrom __future__ import annotations\n\nimport re\nfrom typing import List\n\nimport config\nfrom models.input_schema import Agent1Input\nfrom models.output_schema import DimensionScores\n\n\ndef _cap(value: int, upper: int = 100) -> int:\n    return max(0, min(upper, value))\n\n\ndef is_natural_disaster(event_type: str) -> bool:\n    et = (event_type or "").upper()\n    return any(kw in et for kw in config.NATURAL_DISASTER_KEYWORDS)\n\n\ndef score_severity(event: Agent1Input) -> int:\n    sev = (event.severity or "").upper()\n    base = config.SEVERITY_SCORES.get(sev, config.SEVERITY_DEFAULT)\n    if is_natural_disaster(event.event_type):\n        base += config.NATURAL_DISASTER_BONUS\n    return _cap(base)\n\n\ndef score_geographic(event: Agent1Input) -> int:\n    n = len(event.affected_regions)\n    base = config.GEO_REGION_SCORES.get(n, config.GEO_REGION_FLAT)\n    if event.country.strip().upper() in config.MAJOR_CASHEW_COUNTRIES:\n        base += config.PRODUCTION_COUNTRY_BONUS\n    return _cap(base)\n\n\ndef score_logistics(event: Agent1Input) -> int:\n    impact = event.expected_impact\n    total = 0\n    for flag, points in config.LOGISTICS_POINTS.items():\n        if getattr(impact, flag, False):\n            total += points\n    return _cap(total)\n\n\ndef score_commodity(event: Agent1Input) -> int:\n    materials = [m.strip().lower() for m in event.affected_materials]\n    if not materials:\n        return _cap(config.COMMODITY_GENERIC_BASE - 10)\n    is_cashew = any("cashew" in m for m in materials)\n    base = config.COMMODITY_STRATEGIC_BASE if is_cashew else config.COMMODITY_GENERIC_BASE\n    if len(materials) >= 2:\n        base += config.COMMODITY_MULTI_MATERIAL_BONUS\n    if event.country.strip().upper() in config.MAJOR_CASHEW_COUNTRIES:\n        base += config.COMMODITY_PRODUCTION_COUNTRY_BONUS\n    return _cap(base)\n\n\ndef score_inventory(event: Agent1Input, override: int | None = None) -> int:\n    if override is not None:\n        return _cap(override)\n    return _cap(config.INVENTORY_SCORE_BASE)\n\n\ndef compute_dimensions(event: Agent1Input, inventory_override: int | None = None) -> DimensionScores:\n    return DimensionScores(\n        severity=score_severity(event),\n        geographic=score_geographic(event),\n        logistics=score_logistics(event),\n        commodity=score_commodity(event),\n        inventory=score_inventory(event, inventory_override),\n    )\n\n\ndef compute_risk_score(dimensions: DimensionScores) -> int:\n    raw = (\n        dimensions.severity * config.WEIGHT_SEVERITY\n        + dimensions.geographic * config.WEIGHT_GEOGRAPHIC\n        + dimensions.logistics * config.WEIGHT_LOGISTICS\n        + dimensions.commodity * config.WEIGHT_COMMODITY\n        + dimensions.inventory * config.WEIGHT_INVENTORY\n    )\n    return _cap(int(round(raw)))\n\n\ndef extract_disruption_days_from_description(event: Agent1Input) -> int:\n    """Deterministic extraction of disruption duration from the description text.\n\n    Supports patterns like \'5-7 days\', \'next 5 days\', \'3 days\', \'for 2 weeks\'.\n    Returns 0 when no duration can be parsed.\n    """\n    text = (event.description or "")[:400]\n    m = re.search(r"(\\d+)\\s*-\\s*(\\d+)\\s*(?:days|day)", text, re.IGNORECASE)\n    if m:\n        low, high = int(m.group(1)), int(m.group(2))\n        return max(low, high)\n    m = re.search(r"(?:next|up to|within|for)\\s+(\\d+)\\s*(?:days|day)", text, re.IGNORECASE)\n    if m:\n        return int(m.group(1))\n    m = re.search(r"(\\d+)\\s*(?:days|day)", text, re.IGNORECASE)\n    if m:\n        return int(m.group(1))\n    m = re.search(r"(\\d+)\\s*(?:weeks|week)", text, re.IGNORECASE)\n    if m:\n        return int(m.group(1)) * 7\n    return 0\n\n\ndef compute_confidence(event: Agent1Input) -> float:\n    conf = config.CONFIDENCE_BASE\n    if event.description.strip():\n        conf += config.CONFIDENCE_DESCRIPTION_BONUS\n    if event.source.strip():\n        conf += config.CONFIDENCE_SOURCE_BONUS\n    if event.affected_regions:\n        conf += config.CONFIDENCE_REGIONS_BONUS\n    return round(min(config.CONFIDENCE_CAP, conf), 2)\n\n\ndef compute_disruption_probability(risk_score: int) -> int:\n    return min(config.DISRUPTION_PROBABILITY_CAP, round(risk_score * config.DISRUPTION_PROBABILITY_FACTOR))\n\n\ndef classify_risk(risk_score: int) -> str:\n    if risk_score <= config.LOW_MAX:\n        return "LOW"\n    if risk_score <= config.MEDIUM_MAX:\n        return "MEDIUM"\n    return "HIGH"\n\n\ndef build_risk_categories(event: Agent1Input, risk_level: str) -> List[str]:\n    categories: List[str] = []\n    natural = is_natural_disaster(event.event_type)\n    if natural:\n        categories.append("NATURAL_DISASTER")\n    impact = event.expected_impact\n    logistic_flags = [getattr(impact, flag, False) for flag in config.LOGISTICS_POINTS]\n    if not natural and any(logistic_flags):\n        categories.append("LOGISTICS_DISRUPTION")\n    if event.affected_materials:\n        categories.append("PROCUREMENT_RISK")\n        categories.append("SUPPLY_DISRUPTION")\n    if not categories and any(logistic_flags):\n        categories.append("LOGISTICS_DISRUPTION")\n    if not categories:\n        categories.append("SUPPLY_DISRUPTION")\n    return categories\n\n\ndef default_summary(event: Agent1Input, risk_level: str) -> str:\n    country = event.country or "the affected region"\n    material = ", ".join(event.affected_materials) or "supply"\n    evt = event.event_type or "event"\n    return (\n        f"A {risk_level} supply risk is assessed for \'{material}\' from {country} "\n        f"following the reported {evt} event ({event.event_id})."\n    )\n\n\ndef build_rule_reasoning(event: Agent1Input, dimensions: DimensionScores, risk_level: str) -> List[dict]:\n    reasons: List[dict] = []\n    sev_label = risk_level if dimensions.severity >= 61 else ("MEDIUM" if dimensions.severity >= 31 else "LOW")\n    reasons.append({"factor": f"{event.event_type or \'Event\'} severity", "impact": sev_label})\n    geo_label = risk_level if dimensions.geographic >= 61 else ("MEDIUM" if dimensions.geographic >= 31 else "LOW")\n    reasons.append({"factor": "Geographic impact concentration", "impact": geo_label})\n    log_label = risk_level if dimensions.logistics >= 61 else ("MEDIUM" if dimensions.logistics >= 31 else "LOW")\n    reasons.append({"factor": "Logistics disruption exposure", "impact": log_label})\n    if event.affected_materials:\n        reasons.append({"factor": "Supply concentration", "impact": risk_level})\n    return reasons')
_boot_module('services.classifier', '"""Risk classification per the 30/60 split and action mapping."""\n\nfrom __future__ import annotations\n\nimport config\nfrom models.input_schema import Agent1Input\nfrom models.output_schema import RiskLevel\n\n\ndef classify(risk_score: int) -> RiskLevel:\n    if risk_score <= config.LOW_MAX:\n        return RiskLevel.LOW\n    if risk_score <= config.MEDIUM_MAX:\n        return RiskLevel.MEDIUM\n    return RiskLevel.HIGH\n\n\ndef recommended_actions(risk_level: RiskLevel) -> "list[str]":\n    return list(config.ACTIONS[risk_level.value])\n\n\ndef business_impact(risk_level: RiskLevel) -> dict:\n    if risk_level is RiskLevel.HIGH:\n        return {\n            "procurement_risk": "HIGH",\n            "price_escalation_risk": "HIGH",\n            "inventory_shortage_risk": "HIGH",\n        }\n    if risk_level is RiskLevel.MEDIUM:\n        return {\n            "procurement_risk": "MEDIUM",\n            "price_escalation_risk": "MEDIUM",\n            "inventory_shortage_risk": "LOW",\n        }\n    return {\n        "procurement_risk": "LOW",\n        "price_escalation_risk": "LOW",\n        "inventory_shortage_risk": "LOW",\n    }\n\n\ndef activate_agent_2(risk_level: RiskLevel) -> bool:\n    return risk_level is RiskLevel.HIGH\n\n\ndef affected_material_label(event: Agent1Input) -> str:\n    if event.affected_materials:\n        return ", ".join(event.affected_materials)\n    return "Unknown"')
_boot_module('services.llm_service', '"""LLM-based risk enrichment using FreeFlow (Groq primary, Gemini fallback).\n\nEnrichment is OPTIONAL. The deterministic rule engine produces the risk score\nindependently; the LLM only adds qualitative fields (summary, risk_reasoning,\nestimated_disruption_days). If the LLM is unavailable (no API keys, rate\nlimited, network down) this module degrades gracefully to None and the caller\nfalls back to rule-generated content.\n"""\n\nfrom __future__ import annotations\n\nimport json\nimport logging\nfrom pathlib import Path\nfrom typing import Optional\n\nimport config\n\nlogger = logging.getLogger(__name__)\n\nPROMPT_TEMPLATE = \'You are the Predictive Event Ingestion Agent, a supply chain risk intelligence\\nspecialist for a cashew procurement company.\\n\\nYou are given a structured JSON describing an external event (weather disaster,\\nport closure, geopolitical tension, etc.) that may disrupt the supply of a\\nprocured material (typically cashew nuts).\\n\\nYour ONLY job is to enrich the risk assessment with qualitative judgment using\\nsemantic reasoning. Return strictly valid JSON — no markdown, no commentary.\\n\\nAnalyze this event JSON:\\n{event_json}\\n\\nReturn JSON with this exact structure:\\n{\\n  "summary": "one to two sentence business-oriented summary of the event and its\\n              likely impact on procurement and supply of the affected material",\\n  "risk_reasoning": [\\n    {\\n      "factor": "short name of the contributing factor",\\n      "impact": "LOW or MEDIUM or HIGH"\\n    }\\n  ],\\n  "estimated_disruption_days": <integer number of days the disruption may last>\\n}\\n\\nRules:\\n- "summary" must be factual and grounded only in the event data given.\\n- "risk_reasoning" should list 2 to 4 distinct contributing factors, each with a\\n  LOW / MEDIUM / HIGH impact judgement based on the event\\\'s severity, geographic\\n  concentration, and logistics exposure.\\n- "estimated_disruption_days" is an integer; if the description mentions a\\n  duration use it, otherwise reason from the event type and severity.\'\n\n\ndef load_prompt(event_json: str) -> str:\n    template = PROMPT_TEMPLATE\n    return template.replace("{event_json}", event_json)\n\n\ndef _parse_json_response(content: str) -> Optional[dict]:\n    if not content:\n        return None\n    text = content.strip()\n    # Strip markdown code fences if present\n    if text.startswith("```"):\n        text = text.strip("`")\n        if text.startswith("json"):\n            text = text[4:]\n        text = text.strip()\n    try:\n        data = json.loads(text)\n    except json.JSONDecodeError:\n        # Attempt to extract the first {...} block\n        start, end = text.find("{"), text.rfind("}")\n        if start == -1 or end == -1:\n            return None\n        try:\n            data = json.loads(text[start : end + 1])\n        except json.JSONDecodeError:\n            return None\n    if not isinstance(data, dict):\n        return None\n    return data\n\n\ndef _try_freeflow(event_dict: dict) -> Optional[dict]:\n    try:\n        from freeflow_llm import FreeFlowClient  # type: ignore\n    except Exception:\n        return None\n    if not (config.GROQ_API_KEY or config.GEMINI_API_KEY):\n        return None\n    try:\n        with FreeFlowClient() as client:\n            response = client.chat(\n                model=config.LLM_PRIMARY_MODEL,\n                messages=[\n                    {"role": "system", "content": load_prompt(json.dumps(event_dict))},\n                    {"role": "user", "content": "Enrich this event\'s risk assessment."},\n                ],\n                temperature=0.1,\n                max_tokens=800,\n            )\n        return _parse_json_response(response.content)\n    except Exception as exc:  # pragma: no cover - rate limit / provider failure\n        logger.warning("FreeFlow enrichment failed: %s", exc)\n        return None\n\n\ndef _try_groq_direct(event_dict: dict) -> Optional[dict]:\n    if not config.GROQ_API_KEY:\n        return None\n    try:\n        from openai import OpenAI  # type: ignore\n    except Exception:\n        return None\n    try:\n        client = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)\n        completion = client.chat.completions.create(\n            model=config.LLM_PRIMARY_MODEL,\n            messages=[\n                {"role": "system", "content": load_prompt(json.dumps(event_dict))},\n                {"role": "user", "content": "Enrich this event\'s risk assessment."},\n            ],\n            temperature=0.1,\n            max_tokens=800,\n            response_format={"type": "json_object"},\n        )\n        return _parse_json_response(completion.choices[0].message.content)\n    except Exception as exc:  # pragma: no cover\n        logger.warning("Groq direct enrichment failed: %s", exc)\n        return None\n\n\ndef _try_gemini_direct(event_dict: dict) -> Optional[dict]:\n    if not config.GEMINI_API_KEY:\n        return None\n    try:\n        from google import genai  # type: ignore\n\n        client = genai.Client(api_key=config.GEMINI_API_KEY)\n        response = client.models.generate_content(\n            model=config.LLM_FALLBACK_MODEL,\n            contents=[\n                ("You are a supply chain risk analyst. Return strictly valid JSON only.\\n"),\n                load_prompt(json.dumps(event_dict)),\n            ],\n            config={"temperature": 0.1},\n        )\n        return _parse_json_response(response.text)\n    except Exception as exc:  # pragma: no cover\n        logger.warning("Gemini enrichment failed: %s", exc)\n        return None\n\n\ndef enrich(event_dict: dict) -> Optional[dict]:\n    """Attempt LLM enrichment. Returns a dict or None on total failure."""\n    if not config.LLM_ENABLED:\n        return None\n\n    result = _try_freeflow(event_dict)\n    if result is not None:\n        logger.info("LLM enrichment used FreeFlow provider")\n        return result\n\n    result = _try_groq_direct(event_dict)\n    if result is not None:\n        logger.info("LLM enrichment used Groq provider")\n        return result\n\n    result = _try_gemini_direct(event_dict)\n    if result is not None:\n        logger.info("LLM enrichment used Gemini provider")\n        return result\n\n    logger.info("LLM enrichment unavailable; using rule-based content")\n    return None')
_boot_module('services.output_generator', '"""Assembles the final Agent1_output.json by merging the deterministic rule\nengine output with optional LLM enrichment."""\n\nfrom __future__ import annotations\n\nimport uuid\nfrom datetime import datetime, timezone\nfrom typing import List, Optional\n\nimport config\nfrom models.input_schema import Agent1Input\nfrom models.output_schema import (\n    Agent1Output,\n    Agent2Payload,\n    AgentMetadata,\n    BusinessImpact,\n    DimensionScores,\n    RiskFactor,\n    RiskLevel,\n)\nfrom services import classifier, llm_service, risk_scorer\n\n\ndef build_assessment_id(event_id: str) -> str:\n    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")\n    suffix = uuid.uuid4().hex[:4].upper()\n    return f"RA-{date_part}-{event_id}"\n\n\ndef _sanitize_llm_enrichment(data: Optional[dict]) -> dict:\n    """Return a safe, validated subset of the LLM response."""\n    if not isinstance(data, dict):\n        return {}\n    safe: dict = {}\n    summary = data.get("summary")\n    if isinstance(summary, str) and summary.strip():\n        safe["summary"] = summary.strip()\n\n    reasoning = data.get("risk_reasoning")\n    cleaned_reasoning: List[dict] = []\n    if isinstance(reasoning, list):\n        for item in reasoning:\n            if isinstance(item, dict):\n                factor = str(item.get("factor", "")).strip()\n                impact = str(item.get("impact", "")).upper().strip()\n                if factor and impact in {"LOW", "MEDIUM", "HIGH"}:\n                    cleaned_reasoning.append({"factor": factor, "impact": impact})\n    if cleaned_reasoning:\n        safe["risk_reasoning"] = cleaned_reasoning[:5]\n\n    days = data.get("estimated_disruption_days")\n    if isinstance(days, str) and days.strip().isdigit():\n        days = int(days.strip())\n    if isinstance(days, (int, float)) and 0 <= days <= 365:\n        safe["estimated_disruption_days"] = int(days)\n\n    return safe\n\n\ndef generate(event: Agent1Input, inventory_override: Optional[int] = None) -> Agent1Output:\n    # ---- Deterministic rule engine ----\n    dimensions: DimensionScores = risk_scorer.compute_dimensions(event, inventory_override)\n    risk_score: int = risk_scorer.compute_risk_score(dimensions)\n    risk_level: RiskLevel = classifier.classify(risk_score)\n    affected_material = classifier.affected_material_label(event)\n    disruption_probability: int = risk_scorer.compute_disruption_probability(risk_score)\n    confidence: float = risk_scorer.compute_confidence(event)\n    risk_categories: List[str] = risk_scorer.build_risk_categories(event, risk_level.value)\n    business = classifier.business_impact(risk_level)\n    actions = classifier.recommended_actions(risk_level)\n    rule_reasoning = risk_scorer.build_rule_reasoning(event, dimensions, risk_level.value)\n    rule_days = risk_scorer.extract_disruption_days_from_description(event)\n\n    # ---- Fallback fields (rule-derived) ----\n    fallback_summary = risk_scorer.default_summary(event, risk_level.value)\n    reasoning = rule_reasoning\n    estimated_days = rule_days\n    final_summary = fallback_summary\n\n    # ---- Optional LLM enrichment (graceful degradation) ----\n    llm_payload = llm_service.enrich(event.model_dump(mode="json"))\n\n    if llm_payload:\n        safe = _sanitize_llm_enrichment(llm_payload)\n        if safe.get("summary"):\n            final_summary = safe["summary"]\n        if safe.get("risk_reasoning"):\n            reasoning = safe["risk_reasoning"]\n        if safe.get("estimated_disruption_days") is not None:\n            estimated_days = safe["estimated_disruption_days"]\n\n    output = Agent1Output(\n        risk_assessment_id=build_assessment_id(event.event_id),\n        event_id=event.event_id,\n        affected_country=event.country,\n        affected_material=affected_material,\n        event_type=event.event_type,\n        event_severity=event.severity,\n        risk_level=risk_level,\n        risk_score=risk_score,\n        confidence_score=confidence,\n        supply_disruption_probability=disruption_probability,\n        estimated_disruption_days=estimated_days,\n        risk_categories=risk_categories,\n        summary=final_summary,\n        business_impact=BusinessImpact(\n            procurement_risk=RiskLevel(business["procurement_risk"]),\n            price_escalation_risk=RiskLevel(business["price_escalation_risk"]),\n            inventory_shortage_risk=RiskLevel(business["inventory_shortage_risk"]),\n        ),\n        risk_reasoning=[RiskFactor(factor=r["factor"], impact=RiskLevel(r["impact"])) for r in reasoning],\n        recommended_actions=actions,\n        agent_2_payload=Agent2Payload(\n            commodity=affected_material,\n            affected_country=event.country,\n            risk_level=risk_level,\n            risk_score=risk_score,\n            estimated_disruption_days=estimated_days,\n        ),\n        activate_agent_2=classifier.activate_agent_2(risk_level),\n        assessment_metadata=AgentMetadata(agent_name=config.AGENT_NAME, version=config.VERSION),\n    )\n    return output')
for _n in ('risk_scorer', 'classifier', 'llm_service', 'output_generator'):
    setattr(_services, _n, sys.modules['services.' + _n])

from services.output_generator import generate
from models.input_schema import Agent1Input
print('Agent 1 loaded. Version:', sys.modules['config'].VERSION)
# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Run all 6 demo scenarios and save results to Databricks
# MAGIC # MAGIC
# MAGIC # MAGIC Expected scores:
# MAGIC # MAGIC  - Typhoon Vietnam (SEVERE)             -> HIGH 82
# MAGIC # MAGIC  - Ghana Port Strike (MODERATE)         -> MEDIUM 59
# MAGIC # MAGIC  - Kenya Road Maintenance (MINOR)       -> LOW 24
# MAGIC # MAGIC  - Belgium Ransomware (HIGH)            -> HIGH 63
# MAGIC # MAGIC  - India Earthquake (SEVERE)            -> HIGH 82
# MAGIC # MAGIC  - Tanzania Drought (SEVERE)            -> HIGH 66
# COMMAND ----------
import json

SCENARIOS = [
    {'event_id': 'EVT-2026-001', 'event_timestamp': '2026-09-15T04:30:00Z', 'event_type': 'Typhoon', 'event_name': 'Typhoon Hai Phong', 'country': 'Vietnam', 'affected_regions': ['Hai Phong', 'Quang Ninh', 'Da Nang'], 'severity': 'SEVERE', 'source': 'National Weather Authority', 'description': 'Typhoon warning issued across northern and central Vietnam. Ports may face closures and transportation interruptions for the next 5-7 days.', 'expected_impact': {'port_disruption': True, 'road_disruption': True, 'power_outage_risk': True, 'manufacturing_disruption': True}, 'affected_materials': ['Cashew Nuts']},
    {'event_id': 'EVT-2026-002', 'event_timestamp': '2026-09-20T06:00:00Z', 'event_type': 'Port Strike', 'event_name': 'Tema Port Dockworker Strike', 'country': 'Ghana', 'affected_regions': ['Tema', 'Accra'], 'severity': 'MODERATE', 'source': 'Ghana Ports and Harbours Authority', 'description': 'Planned indefinite strike by dockworkers at Tema Port. Container and bulk cargo handling may be reduced by up to 40%. The port authority expects normal operations to resume within 2-3 days as negotiations progress.', 'expected_impact': {'port_disruption': True, 'road_disruption': False, 'power_outage_risk': False, 'manufacturing_disruption': False}, 'affected_materials': ['Cashew Nuts']},
    {'event_id': 'EVT-2026-003', 'event_timestamp': '2026-09-22T10:00:00Z', 'event_type': 'Road Maintenance', 'event_name': 'Temporary Bridge Works on Mombasa Road', 'country': 'Kenya', 'affected_regions': ['Mombasa'], 'severity': 'MINOR', 'source': 'Kenya National Highway Authority', 'description': 'Scheduled lane closures for central median repairs on the approach road. Minor temporary delays expected; operations return to normal the same day.', 'expected_impact': {'port_disruption': False, 'road_disruption': True, 'power_outage_risk': False, 'manufacturing_disruption': False}, 'affected_materials': ['Steel Billets']},
    {'event_id': 'EVT-2026-004', 'event_timestamp': '2026-09-23T02:15:00Z', 'event_type': 'Cyberattack', 'event_name': 'Ransomware on Antwerp Terminal Operating System', 'country': 'Belgium', 'affected_regions': ['Antwerp', 'Zeebrugge', 'Ghent'], 'severity': 'HIGH', 'source': 'Port of Antwerp-Bruges Cybersecurity Unit', 'description': 'Ransomware disrupted the terminal operating system controlling container stacking and customs clearance. Automated gates and crane scheduling are offline. Manual fallback reduces throughput to around 60%. Full recovery is expected within one week.', 'expected_impact': {'port_disruption': True, 'road_disruption': False, 'power_outage_risk': True, 'manufacturing_disruption': False}, 'affected_materials': ['Cashew Nuts']},
    {'event_id': 'EVT-2026-005', 'event_timestamp': '2026-09-25T01:40:00Z', 'event_type': 'Earthquake', 'event_name': 'M6.9 Earthquake off Gujarat Coast', 'country': 'India', 'affected_regions': ['Mundra', 'Gandhidham', 'Jamnagar'], 'severity': 'SEVERE', 'source': 'National Centre for Seismology', 'description': 'Strong earthquake caused damage at Mundra port, the largest private cargo terminal. Cranes and berths damaged; parts of the power grid are down. Vessel schedules are suspended for an estimated 6-8 days.', 'expected_impact': {'port_disruption': True, 'road_disruption': True, 'power_outage_risk': True, 'manufacturing_disruption': True}, 'affected_materials': ['Cashew Nuts']},
    {'event_id': 'EVT-2026-006', 'event_timestamp': '2026-09-28T00:00:00Z', 'event_type': 'Drought', 'event_name': 'Severe Drought in Southern Tanzania', 'country': 'Tanzania', 'affected_regions': ['Mtwara', 'Lindi', 'Ruvuma', 'Tabora', 'Mbeya'], 'severity': 'SEVERE', 'source': 'Tanzania Meteorological Authority', 'description': 'Seasonal rains have failed across the major cashew growing belts. Crop yields are projected down 30-45%. The harvest window is expected to extend by up to one month while yield losses are assessed.', 'expected_impact': {'port_disruption': False, 'road_disruption': False, 'power_outage_risk': False, 'manufacturing_disruption': False}, 'affected_materials': ['Cashew Nuts']},
    ]

results = []
for data in SCENARIOS:
    out = generate(Agent1Input.model_validate(data))
    d = out.to_dict()
    results.append(d)
    row = ('{}  {:>14s} -> score {:>3d} | {:>6s} | activate_agent_2: {:>5s} | '
           'disruption: ~{:>2d}d').format(d['event_id'], d['event_type'], out.risk_score,
           out.risk_level.value, str(out.activate_agent_2), out.estimated_disruption_days)
    print(row)

first = results[0]
print()
print('=== FULL Agent1_output - Typhoon Vietnam ===')
print(json.dumps(first, indent=2))
# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Persist results on Databricks (Delta table + JSON files)
# MAGIC # MAGIC
# MAGIC # MAGIC Agent 2's team can read from the `agent1_risk_assessments` table, or the JSON files
# MAGIC # MAGIC under `/FileStore/agent1/outputs/` — all inside Databricks.
# COMMAND ----------
from pyspark.sql import Row

# Delta table (Unity Catalog location of your choice)
table_name = 'agent1_risk_assessments'  # or 'catalog.schema.agent1_risk_assessments'
try:
    df = spark.createDataFrame([Row(**r) for r in results])
    df.write.mode('overwrite').saveAsTable(table_name)
    print('Saved Delta table:', table_name, '| rows:', df.count())
except Exception as e:
    print('Delta table save skipped:', e)

# JSON files on DBFS/FileStore
import json as _json
out_dir = '/FileStore/agent1/outputs'
for r in results:
    p = out_dir + '/Agent1_output_' + str(r['event_id']) + '.json'
    dbutils.fs.put(p, _json.dumps(r, indent=2), True)
dbutils.fs.put(out_dir + '/index.json', _json.dumps(results, indent=2), True)
print('Wrote JSON outputs to', out_dir, '|', len(results), 'files + index.json')
# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Analyze your own event (paste JSON below)
# COMMAND ----------
import json as _json2
from models.input_schema import Agent1Input
from services.output_generator import generate

custom = {
  'event_id': 'EVT-2026-900',
  'event_timestamp': '2026-09-30T09:00:00Z',
  'event_type': 'Flood',
  'event_name': 'River Flooding near Ho Chi Minh City',
  'country': 'Vietnam',
  'affected_regions': ['HCM City', 'Long An'],
  'severity': 'HIGH',
  'source': 'Vietnam Meteorological Office',
  'description': 'Flood disrupted container trucking on main corridors for 3-4 days.',
  'expected_impact': {'port_disruption': False, 'road_disruption': True, 'power_outage_risk': False, 'manufacturing_disruption': False},
  'affected_materials': ['Cashew Nuts']
}

out = generate(Agent1Input.model_validate(custom))
print(_json2.dumps(out.to_dict(), indent=2))
# COMMAND ----------
# MAGIC %md
# MAGIC ## 7. One-line call (what Agent 2 / your code will use)
# COMMAND ----------
def risk_assessment(event_dict):
    """Drop-in function: dict -> Agent1_output dict. Same output schema as local."""
    from models.input_schema import Agent1Input
    from services.output_generator import generate
    return generate(Agent1Input.model_validate(event_dict)).to_dict()

sample = risk_assessment(SCENARIOS[0])
print('risk_assessment() works. agent_2_payload:', sample['agent_2_payload'])
