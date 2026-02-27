## SpikeTrace

SpikeTrace is an **AI-powered incident and sustainability investigator** for modern production systems.  
It treats **user-impacting failures**, **carbon/emissions spikes**, and **business impact** as first‑class operational incidents, and helps you:

- **Explain incidents** in terms of users, reliability, and revenue
- **Quantify carbon/compute waste** caused by failures and bad deployments
- **Trigger workflows** that create Jira incidents and notify your team on Slack
- **Visualize emissions and latency** in Kibana dashboards

---

## Key Features

- **Autonomous incident & sustainability agent**
  - Agent spec in `agents/spike_trac_agent.json`
  - Investigates incidents using logs, metrics, deployments, and historical impact
  - Always explains: **user impact**, **carbon/compute waste**, and **business impact**

- **Actionable workflow integration**
  - Workflow in `workflows/create_incident.yaml`
  - **Creates Jira Service Management incidents**
  - **Sends Slack notifications** when incidents are created
  - Designed to be called as `create_incident_ticket` / workflow tool from the agent

- **Prebuilt Kibana dashboards**
  - `dashboards/spiketrace_dashboard.ndjson` includes:
    - **Estimated CO₂ over time**
    - **Estimated CO₂ by service**
    - **Emissions deviation by region**
    - **Latency over time**
  - Backed by index patterns:
    - `spiketrace-carbon-metrics-*`
    - `spiketrace-logs-*`

- **Connectors for automation**
  - `connectors/connectors.ndjson` includes saved objects for:
    - **Jira** (`jira-connector`)
    - **Slack** (`slack-connector`)
    - **Gemini / Vertex AI** (`gemini-connector`)

---

## Architecture Overview

- **AI Agent**
  - Runs as an Elastic / AI assistant–style agent (Gemini 2.5 Flash by default)
  - Follows a structured **investigation flow** (confirm spike → correlate logs/errors → check deployments → quantify waste → summarize impact → recommend remediation)
  - Can optionally **create incidents** and **notify Slack** via the workflow tool

- **Data Plane**
  - Metrics and logs indexed into Elasticsearch:
    - Carbon metrics in `spiketrace-carbon-metrics-*`
    - Logs and latency in `spiketrace-logs-*`
  - Kibana visualizations power the SpikeTrace dashboard

- **Control Plane**
  - Connectors for Jira, Slack, and Gemini
  - Workflow to orchestrate Jira + Slack actions from the agent

- **Optional Backend**
  - `requirements.txt` suggests a small **FastAPI + Uvicorn** API layer (`fastapi`, `uvicorn`, `httpx`, `elasticsearch`, `python-dotenv`, `a2a`) if you choose to host additional APIs or tools around the agent.

---

## Getting Started

### Prerequisites

- Python **3.10+** (recommended)
- An **Elastic** deployment with Kibana (8.8+ recommended)
- Access to:
  - **Jira Service Management** project (for incident tickets)
  - **Slack** workspace & incoming webhook / app credentials
  - **Google Cloud** project with **Vertex AI / Gemini** enabled

---

## Setup

### 1. Install Python dependencies

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate  # on macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment (optional backend)

If you run a FastAPI / backend around SpikeTrace, create a `.env` file and configure:

- **Elasticsearch URL & credentials**
- Any API keys / secrets your tools and services need

(Use your own naming conventions here; keep secrets out of version control.)

### 3. Import Connectors into Kibana

1. In Kibana, go to **Stack Management → Saved Objects**.
2. Click **Import**, select `connectors/connectors.ndjson`.
3. After import:
   - Open each connector (Gemini, Jira, Slack).
   - Fill in **missing secrets** (API keys, tokens, project IDs, etc.).
   - Save.

These connectors will be referenced by ID in your workflow and agent tools.

### 4. Import Dashboards & Index Patterns

1. Still in **Stack Management → Saved Objects**.
2. **Import** `dashboards/spiketrace_dashboard.ndjson`.
3. Ensure:
   - Your carbon metrics index pattern matches `spiketrace-carbon-metrics-*`.
   - Your logs/metrics index pattern matches `spiketrace-logs-*`.
4. Open the **“SpikeTrace Dashboard Latest”** dashboard and verify charts populate:
   - CO₂ over time
   - CO₂ by service
   - Emissions deviation by region
   - Latency over time

### 5. Import the Workflow

1. In your workflows/automations UI (e.g. Elastic’s workflow/automation feature or equivalent), create/import from `workflows/create_incident.yaml`.
2. Ensure the connector IDs in the YAML:
   - `451d6a4e-1027-4d7d-9e70-e8064fc5a342` → your **Jira connector**
   - `4d58f484-1138-4316-ac7d-399cb555d3d1` → your **Slack connector**
3. Adjust defaults as needed:
   - Incident `summary`
   - `issueType` values matching your Jira project

### 6. Register the SpikeTrace Agent

1. In your AI assistant / agent configuration UI, create a new agent called **“SpikeTrace Commander”** (or similar).
2. Paste the content of `agents/spike_trac_agent.json` (or configure equivalently):
   - `agent-id`: `spiketrace`
   - `description` and `instructions` from the JSON
3. Wire the tools referenced in the instructions:
   - Carbon metrics (e.g. `carbon_spike_by_region`)
   - Logs (`search_logs`, `error_rate_by_service`)
   - Deployments (`deployment_timeline`)
   - Business impact (`incident_business_impact`)
   - Workflow tool (mapped to `create_incident_ticket` → your `Create SpikeTracer Incident` workflow)

---

## Using SpikeTrace

Once everything is wired up, you can chat with the agent using natural language, for example:

- **Carbon / emissions investigations**
  - “Why did emissions spike in `us-central1` yesterday?”
  - “Which services contributed most to CO₂ in the last 24 hours?”

- **Incident & reliability investigations**
  - “What’s going wrong with checkout in `us-central1`?”
  - “What incidents are affecting payments in `europe-west1` this week?”

For each investigation, SpikeTrace aims to return a **structured explanation**:

- **Overview**
- **User Impact** (errors, latency, failed checkouts, etc.)
- **Carbon/Compute Impact** (wasted CO₂, excess runtime, retries)
- **Business Impact** (orders affected, revenue lost)
- **Deployment Correlation** (versions, deployment IDs)
- **Recommendations** (rollback, tuning retries, right‑sizing, etc.)

At the end of a significant incident explanation, SpikeTrace will typically ask:

> “Do you want me to create a Jira ticket for this incident and notify the team on Slack?”

If you answer **yes**, it will call the `create_incident` workflow which:

- Creates a **Jira incident** with the provided summary/description
- Sends a **Slack notification** including key context

---

## Running an Optional API (FastAPI)

If your setup includes a small API around SpikeTrace (e.g. to expose tools, webhooks, or health endpoints), a common pattern is:

```bash
uvicorn app.main:app --reload
```

Adjust the module/path to match your actual application entrypoint.

---

## Customization

- **Adapt questions and terminology** to your own domain (e.g. SaaS, data pipelines, fintech).
- **Extend the workflow** with:
  - Additional connectors (PagerDuty, email, ServiceNow)
  - Custom routing based on severity, service, or region
- **Modify dashboards** to add:
  - Error rates by service
  - Cost estimates alongside emissions
  - SLO-like latency/error charts

---

## License

SpikeTrace is licensed under the **MIT License**.  
See `LICENSE` for full text.

