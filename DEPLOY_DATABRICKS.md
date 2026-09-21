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
hosted on Databricks. Prereqs: a **Unity-Catalog-enabled** workspace and **Databricks
Apps enabled** by the admin. Databricks Apps uses managed compute (no cluster needed).

## 1. One-time project files (already in the repo — required for Apps)
| File | Purpose |
|---|---|
| `app.py` | Entry point: `python app.py` launches uvicorn on `DATABRICKS_APP_PORT` |
| `app.yaml` | Runtime command + non-secret env vars (`LLM_ENABLED`, models) |
| `requirements.txt` | Python deps installed automatically at deploy (pip, Python 3.11). FastAPI/uvicorn are pre-installed anyway |
| `databricks.yml` | Optional bundle metadata (not needed for the UI/Git flow) |

## 2. Deploy from the UI (recommended — no local CLI needed)

1. **Publish this code to a Git repo** (GitHub/GitLab/Bitbucket) — e.g. the `Project-Nexus`
   repo (branch `main`). This is what you deploy from.
2. **Link the repo in the workspace**: `Create → Git folder → Link to remote repository`,
   paste the repo URL, branch `main`. (First time, Databricks asks to connect GitHub.)
3. **Create the API-key secrets once** — in any notebook cell (or CLI):
   ```python
   dbutils.secrets.createScope("agent-scope")
   dbutils.secrets.put("agent-scope", "groq_api_key", "gsk_...")
   dbutils.secrets.put("agent-scope", "gemini_api_key", "AIza...")
   ```
4. **Create the app**: app switcher (top-left) → `Databricks Apps` → `Create app` →
   `Create custom app`. Name it `agent1-risk-detection`. For source choose the git
   folder (or `From Git`) → branch `main`.
5. **Attach the secret keys**: on the app page open **Environment variables**, add
   `GROQ_API_KEY` and `GEMINI_API_KEY`, each via "Add from Databricks secret" →
   scope `agent-scope` → key `groq_api_key` / `gemini_api_key`. (`app.yaml` `env` is
   applied automatically on deploy.)
6. **Deploy**, then **Run**. Databricks builds the image (`pip install -r
   requirements.txt`) and starts the app.

## 3. Verify
You get a public URL like `https://agent1-risk-detection.<workspace>.cloud.databricksapps.com`:
```bash
curl https://agent1-risk-detection.<workspace>.cloud.databricksapps.com/health
curl -X POST https://agent1-risk-detection.<workspace>.cloud.databricksapps.com/api/v1/analyze \
  -H "Content-Type: application/json" -d @data/Agent1_input.json
```
Open the app URL in a browser for the dashboard demo (click any supply-chain card →
live Agent 1 run).

## 4. Updates later
Edit code → `git push` → on the app page **Deploy** (re-run after deploy).

## 5. Alternative: deploy with the Databricks CLI (config-as-code)
```bash
# Windows: winget install Databricks.DatabricksCLI   (or curl the installer)
databricks auth login --host https://<your-workspace-url>   # browser SSO
databricks apps create agent1-risk-detection
databricks workspace import-dir . /Workspace/Users/<you>/apps/agent1-risk-detection
databricks apps deploy agent1-risk-detection \
  --source-code-path /Workspace/Users/<you>/apps/agent1-risk-detection
databricks apps get agent1-risk-detection   # status + URL
```
Notes:
- The `env` block for secrets like `valueFrom:` requires the secret to be attached
  to the app as a *resource* (app's **Resources** tab), matching the name you use.
- `app.yaml` (not `databricks.yml config:`) owns runtime env — never reference
  `{{secrets/...}}` inside `app.yaml` `value:`. Use the secret picker instead.

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