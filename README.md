# Aressa AI HR Dashboard

An agentic AI dashboard for internal HR talent development at a fictional company called **Aressa**. The agent helps HR with three things:

1. **Skill-gap analysis** — identify thin coverage of skills or certifications across teams and categories.
2. **Promotion-candidate identification** — surface employees ready for the next level based on certification trajectory and performance reviews.
3. **Personalized certification recommendations** — for one named employee, recommend 2–4 real-world certifications that close growth-area gaps, prepare them for the next level, or renew expired credentials.

## Tech stack

- **Python 3.12** — uses `str | None` union syntax (requires ≥3.10)
- **[Pydantic AI](https://ai.pydantic.dev/) 1.104** with **Google Gemini** (`gemini-3-flash-preview`) — agent framework and LLM
- **[ChromaDB](https://www.trychroma.com/) 1.5** — persistent vector store for semantic search across employees, certifications, and performance reviews
- **[Streamlit](https://streamlit.io/) 1.58** *(planned)* — local web UI for the dashboard
- **pandas** — CSV ingestion

## Repository contents

| File | Purpose |
|------|---------|
| `agent.py` | Three Pydantic AI agents (`skill_gap_agent`, `promotion_agent`, `recommendation_agent`) sharing one 12-tool kit. Includes a CLI driver. |
| `agent_tracer.py` | Pretty-prints the agent's tool-call trace for CLI inspection. Will be adapted for Streamlit rendering in upcoming work. |
| `db.py` | ChromaDB wrapper exposing three collections (`employees`, `certifications`, `performance_reviews`) with filtered list, semantic search, and bulk-seed functions. |
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

# 5. Run the agent's CLI
python agent.py
```

The CLI presents three modes:
- `1` — skill-gap analysis
- `2` — promotion candidates
- `3` — personalized certification recommendations

On first run, ChromaDB will be empty; the agent / app seeds it from the three CSVs automatically.

## Architecture

```
agent.py (3 agents)
    │
    ├── skill_gap_agent      → SkillGapReport
    ├── promotion_agent      → PromotionCandidates
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

Steps 1–6 of the build plan are complete:

- Virtual environment + dependencies pinned
- Three seed CSVs (employees, certifications, performance reviews) with intentional signal for testing
- `db.py` ChromaDB layer with three collections + bulk-seed orchestrator (validated end-to-end)
- `agent.py` with three structured-output agents sharing a common toolkit, plus a CLI driver

## Upcoming work

1. **Live API validation of `agent.py`.** The agents were authored but not yet exercised against the live Gemini API. First task on resume: run one query per agent end-to-end and confirm tool calls fire and outputs serialize cleanly.
2. **Adapt `agent_tracer.py` for Streamlit.** Add `build_agent_trace(result) -> list[dict]` returning step records the UI can render inside `st.expander`. Keep the existing `print_agent_trace` as a thin wrapper so the CLI still works.
3. **Build `app.py` (Streamlit dashboard).** Single-file app with a sidebar (mode selector, CSV uploader, reset button) and a main panel per agent — color-coded risk levels for skill gaps, candidate cards for promotions, expandable cert recommendations.
4. **Local golden + edge-path validation.** Confirm expected behaviors (e.g. *"who is ready for promotion?"* should return e001/e005/e008 and exclude declining-trajectory e006; *"recommend certs for Priya"* should suggest renewing the expired AWS Pro cert). Handle empty queries, malformed CSV uploads, and zero-result agent responses.
5. **(Optional, post-MVP)** Wire ingestion sources beyond CSV — e.g. cert data from Credly, performance reviews from an HRIS API.
