# Aressa AI HR Dashboard

An agentic AI dashboard for internal HR talent development at a fictional company called **Aressa**. The agent helps HR with two things:

1. **Skill-gap analysis** — identify thin coverage of skills or certifications across teams and categories.
2. **Personalized certification recommendations** — for one named employee, recommend 2–4 real-world certifications that close growth-area gaps, prepare them for the next level, or renew expired credentials.

Earlier iterations also included AI-driven promotion-candidate identification and flight-risk monitoring. Both were removed: people-level verdicts (promotion readiness, retention risk) felt like the wrong place for AI without a human in the loop. The remaining features stay at the capability level rather than passing judgment on individuals.

## Tech stack

- **Python 3.12** — uses `str | None` union syntax (requires ≥3.10)
- **[Pydantic AI](https://ai.pydantic.dev/) 1.104** with **Google Gemini** (`gemini-3-flash-preview`) — agent framework and LLM
- **[ChromaDB](https://www.trychroma.com/) 1.5** — persistent vector store for semantic search across employees, certifications, and performance reviews
- **[Streamlit](https://streamlit.io/) 1.58** — local web UI for the dashboard (`app.py`)
- **pandas** — CSV ingestion

## Repository contents

| File | Purpose |
|------|---------|
| `app.py` | Streamlit dashboard. Sidebar with mode selector + CSV uploader + danger-zone reset; per-mode main panels for skill-gap analysis and cert recommendations; collapsible agent trace below each result. |
| `agent.py` | Two Pydantic AI agents (`skill_gap_agent`, `recommendation_agent`) sharing one 12-tool kit. Includes a CLI driver. |
| `agent_tracer.py` | `build_agent_trace(result) -> list[dict]` for structured trace records used by the Streamlit UI, plus `print_agent_trace(result)` as a CLI pretty-printer wrapping it. |
| `db.py` | ChromaDB wrapper exposing three collections (`employees`, `certifications`, `performance_reviews`) with filtered list, semantic search, and bulk-seed functions. Client is eager-initialized at module load to avoid a thread-race when pydantic-ai dispatches tools in parallel. |
| `employees.csv` | Seed roster of 10 fictional employees (`e001`–`e010`) — id, name, role, department, level, hire date, manager. |
| `certifications.csv` | 25 cert records across the 10 employees. 7 are intentionally expired as of mid-2026 to exercise the expired-cert reasoning paths. |
| `performance_reviews.csv` | 20 review records (2 cycles per employee). Trajectories engineered to include rising, stable, and declining performers. |
| `requirements.txt` | Pinned Python dependencies. |
| `.env` *(not in git)* | Holds `GEMINI_API_KEY`. |
| `.chroma/` *(not in git)* | Persistent ChromaDB data, generated on first run. |

## Setup

```bash
# 1. Clone
git clone https://github.com/calvintirrell/ai-hr-dashboard.git
cd ai-hr-dashboard

# 2. Create a Python 3.12 virtual environment
# (macOS Homebrew path shown; adjust for your system)
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env with your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env

# 5a. Launch the Streamlit dashboard (recommended)
streamlit run app.py

# 5b. ...or use the bare CLI
python agent.py
```

**Streamlit dashboard (`app.py`)** opens at `http://localhost:8501` with a sidebar mode selector, a CSV uploader for ad-hoc data ingestion, and a danger-zone reset button. Pick a mode and a query, click Run, and the agent's tool-call trace is collapsed below each result.

**CLI driver (`python agent.py`)** presents two modes:
- `1` — skill-gap analysis
- `2` — personalized certification recommendations

On first run, ChromaDB will be empty; the dashboard / CLI seeds it from the three CSVs automatically.

## Architecture

```
agent.py (2 agents)
    │
    ├── skill_gap_agent      → SkillGapReport
    └── recommendation_agent → CertRecommendation
            │
            └── shared 12-tool kit (get_today, list/search by department/level/category,
                                    get_employee_detail, get_review_trajectory, ...)
                    │
                    └── db.py (3 ChromaDB collections)
                            │
                            ├── employees
                            ├── certifications
                            └── performance_reviews
```

Each Chroma collection embeds different document text:
- **employees** — a synthesized profile blurb (*"Alex Rivera — Senior ML Engineer in Engineering, level IC4, hired 2023-04-15, reports to manager e005"*)
- **certifications** — `cert_name + issuer + category`
- **performance_reviews** — `strengths + growth_areas`

This means semantic search can answer questions like *"who works on infrastructure?"*, *"any Kubernetes certs?"*, or *"who has strong mentorship reviews?"* — without needing per-question SQL.

## Current status

**MVP complete and shipping on `main`.** All nine build steps are done:

- Virtual environment on Python 3.12 + dependencies pinned in `requirements.txt`
- Three seed CSVs (employees, certifications, performance reviews) with intentional signal for testing (uneven cert distribution, mixed performance trajectories, 7 expired credentials)
- `db.py` ChromaDB layer with three collections + bulk-seed orchestrator (validated end-to-end)
- `agent.py` with two structured-output agents (`skill_gap_agent`, `recommendation_agent`) sharing a common 12-tool kit, plus a CLI driver
- `agent_tracer.py` exposing both structured trace records and a CLI pretty-printer
- `app.py` Streamlit dashboard wiring the agents to a local web UI with mode selector, CSV uploader, danger-zone reset, color-coded risk levels, expandable cert recommendations, and a per-run agent trace
- Browser-driven validation completed: skill-gap correctly surfaces single-points-of-failure (e.g. Priya as the lone Kubernetes-certified engineer) and expired certs; cert recommendations correctly target review-stated growth areas (e.g. a Scrum Master cert for an employee whose recent review flagged collaboration issues)

## Upcoming work

1. **Tighten skill-gap prompt against count hallucinations.** During validation, one skill-gap card said *"Coverage: 4 of 5 certs are expired"* while only naming 2 expired certs (the recommendation was still correct; the headline number was wrong). Adding *"Always recount before stating any quantity in your output, and only cite numbers you can name the source rows for"* to `skill_gap_agent`'s system prompt should fix it.
2. **Add a "manager review required" disclaimer** in the Cert Recommendations panel footer. Individual development plans should never be acted on without manager involvement; the UI should say so explicitly even though the agent itself stays at the capability level.
3. **Improve cert-recommendation grounding with a live catalog.** The agent currently suggests real-sounding certs but doesn't verify they exist or fetch up-to-date pricing, prerequisites, or curricula. A future step could call out to a real catalog (Credly, Coursera, AWS Skill Builder, etc.) and ground recommendations in actual offerings.
4. **Add a reproducible eval suite.** Run a fixed set of queries through both agents and snapshot expected outputs (e.g. "recommend certs for e002 Priya" must include AWS Pro renewal). Catches regressions when the prompt, model, or data changes.
5. **(Optional, post-MVP)** Wire ingestion sources beyond CSV — cert data pulled from Credly, performance reviews from an HRIS API, employee roster from BambooHR / Rippling / etc.
