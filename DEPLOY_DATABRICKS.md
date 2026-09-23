# Agent 1 — Run 100% on Databricks (no laptop needed)

Agent 1 (risk-detection) is now **fully self-contained**. Nothing is read from a local
machine at runtime — code, scenario data, and LLM prompt are all either embedded in a
notebook or pushed to the Databricks workspace once.

Same LLM as before: **Groq (via FreeFlow) primary, Gemini fallback**. Same risk engine.
Agent 2 gets results straight from Databricks (Delta table / JSON files / API).

Two paths — pick the one that fits the demo:

| | A. Self-contained Notebook | B. Full App (dashboard + API) |
|---|---|---|
| What you get | Agent results + Delta table + JSON files | News dashboard UI + live `/api/v1/analyze` REST endpoint |
| Setup time | ~5 min | ~30 min (needs Databricks CLI) |
| Local dependency | **None** | **None once code is in a Databricks git folder** |
| Best for | The hackathon demo | A reusable "Agent 1 service" for Agent 2/3 |

---

# Path A — Self-contained Notebook (recommended) ✅

One file, no upload, no CLI: `notebooks/Agent1_SelfContained.py`.

> It embeds the **entire** Agent 1 source (config, models, services), the LLM prompt,
> and all 6 demo scenarios. It installs its own packages and saves results to Databricks.

## Steps
1. **Attach a running cluster.**
2. **Create → New Notebook**, then **File → Import** → choose `notebooks/Agent1_SelfContained.py`.
3. **Give the API keys once** (if you haven't). In any notebook, run once:
   ```python
   dbutils.secrets.createScope("agent-scope")
   dbutils.secrets.put("agent-scope", "groq_api_key", "gsk_...")     # from Dinesh
   dbutils.secrets.put("agent-scope", "gemini_api_key", "AIza...")   # from Dinesh
   ```
   (Or just fill the `groq_api_key` / `gemini_api_key` widgets in the notebook's Run bar instead.)
4. **Run All.**

## What happens (cell by cell)
1. `%pip install` — installs `freeflow-llm`, `openai`, `google-genai`, `pydantic`, `python-dotenv`
2. Loads Groq + Gemini keys from secrets/widgets
3. Bootstraps Agent 1 in memory (embedded source — exactly the code we run locally)
4. Runs all 6 scenarios → prints each `Agent1_output`
5. **Saves on Databricks**:
   - Delta table `agent1_risk_assessments` (or `catalog.schema.agent1_risk_assessments`)
   - JSON files under `/FileStore/agent1/outputs/Agent1_output_<event_id>.json` + `index.json`
6. Analyzes a custom event (edit the dict)
7. Exposes `risk_assessment(event_dict)` — a one-line drop-in for Agent 2

## Expected output
```
EVT-2026-001  Typhoon         -> score  82 | HIGH   | activate_agent_2:  True | disruption: ~ 7d
EVT-2026-002  Port Strike     -> score  59 | MEDIUM | activate_agent_2: False | disruption: ~ 3d
EVT-2026-003  Road Maintenance-> score  24 | LOW    | activate_agent_2: False | disruption: ~ 0d
EVT-2026-004  Cyberattack     -> score  63 | HIGH   | activate_agent_2:  True | disruption: ~ 0d
EVT-2026-005  Earthquake      -> score  82 | HIGH   | activate_agent_2:  True | disruption: ~ 8d
EVT-2026-006  Drought         -> score  66 | HIGH   | activate_agent_2:  True | disruption: ~ 0d
```
With keys set, the logs also show `LLM enrichment used FreeFlow provider`.

## Agent 2 reads results here (all on Databricks)
```sql
SELECT event_id, risk_level, risk_score, agent_2_payload
FROM agent1_risk_assessments;
```
or in Python:
```python
results = json.loads(dbutils.fs.head("/FileStore/agent1/outputs/index.json"))
```

---

# Path B — Full App: News Dashboard + Live API (Databricks Apps)

The MSN-style "Times of Tieto" dashboard and the `/api/v1/analyze` REST endpoint run
as a **Databricks App** — clicking a supply-chain card triggers Agent 1 live, entirely
hosted on Databricks.

## 1. Get the code onto Databricks (one time)
Easiest and keeps it git-versioned:
- **Create → Git folder → Link to remote repository** → paste the repo URL.
- Open the folder, which contains `agent1/`.
Once cloned, everything (`server.py`, `app.py`, `databricks.yml`, `models/`, `services/`,
`static/`, `data/`) lives on Databricks. Nothing runs from your laptop.

## 2. Files already in the repo (done)
- `app.py` — one-line Databricks entry point → `from server import app`
- `databricks.yml` — bundle config; reads keys from `agent-scope` secrets

## 3. Deploy (requires Databricks CLI)
```bash
pip install databricks-cli
databricks configure --host https://<your-workspace-url>

cd agent1                      # on your machine OR on a cluster via terminal
databricks bundle deploy
databricks bundle run agent1_risk_detection
```

## 4. Verify
You get a URL like `https://agent1-risk-detection.<workspace>.databricksapps.com`
```bash
curl https://agent1-risk-detection.<workspace>/health
curl -X POST https://agent1-risk-detection.<workspace>/api/v1/analyze \
  -H "Content-Type: application/json" -d @data/Agent1_input.json
```
Open the app URL in a browser for the dashboard demo.

## Updates later
```bash
databricks bundle deploy && databricks bundle run agent1_risk_detection
```

---

# Resources Agent 1 uses on Databricks

| Databricks resource | How Agent 1 uses it |
|---|---|
| Cluster | Runs the notebook / hosts the app |
| Secrets (`agent-scope`) | Groq + Gemini API keys |
| Delta table `agent1_risk_assessments` | Structured results for Agent 2/3 |
| DBFS `/FileStore/agent1/outputs/` | Per-event JSON + index for Agent 2/3 |
| Databricks Apps (Path B) | Dashboard + REST API for the live demo |
| Git folder (Path B) | Keeps the code versioned inside the workspace |

---

# Why it's "no local dependency"
- **Notebook path:** one self-contained file — no repo, no upload, no keys on disk.
- **App path:** code is cloned into the Databricks workspace via Git; deployment
  artifacts and runtime all live on Databricks.

# Questions / blockers
- Need Groq/Gemini keys? → Ask Dinesh
- `databricks bundle` fails? → Confirm CLI is logged in and Databricks Apps is enabled
- Want the Delta table in a Unity Catalog catalog? → change `table_name` in cell 5 of the notebook