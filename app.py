"""
Aressa AI HR Dashboard — Streamlit UI.

Two modes corresponding to the two agents in agent.py:
  - Skill Gap Analysis   -> skill_gap_agent
  - Cert Recommendations -> recommendation_agent
"""

import asyncio
import pandas as pd
import streamlit as st

import db
from agent import skill_gap_agent, recommendation_agent
from agent_tracer import build_agent_trace


st.set_page_config(page_title="Aressa HR Dashboard", layout="wide")


# --- Startup: auto-seed if DB is empty (runs once per session) ---

if "seed_check_done" not in st.session_state:
    if db.is_empty():
        with st.spinner("Seeding initial data into ChromaDB..."):
            counts = db.seed_from_csvs(
                "employees.csv", "certifications.csv", "performance_reviews.csv"
            )
            st.toast(
                f"Seeded {counts['employees']} employees, "
                f"{counts['certifications']} certs, "
                f"{counts['performance_reviews']} reviews"
            )
    st.session_state.seed_check_done = True


# --- Helpers ---

def run_agent(agent_obj, prompt: str):
    """Run an agent and surface any error as an st.error rather than a traceback."""
    try:
        return asyncio.run(agent_obj.run(prompt))
    except Exception as e:
        st.error(f"Agent run failed: {type(e).__name__}: {e}")
        return None


def render_trace(result) -> None:
    """Render the agent's tool-call trace inside a collapsed expander."""
    records = build_agent_trace(result)
    n_steps = sum(1 for r in records if r["type"] in ("tool_call", "final_response"))
    with st.expander(f"Agent trace ({n_steps} steps)"):
        for rec in records:
            if rec["type"] == "tool_call":
                if rec["tool_name"] == "final_result":
                    st.markdown(f"**Step {rec['step']}: Final result** *(structured output)*")
                else:
                    st.markdown(f"**Step {rec['step']}: Call** `{rec['tool_name']}`")
                    if rec["args"]:
                        st.code(str(rec["args"]), language=None)
            elif rec["type"] == "tool_return":
                preview = rec["content"][:300] + ("..." if len(rec["content"]) > 300 else "")
                st.markdown(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{rec['tool_name']}** returned: `{preview}`",
                    unsafe_allow_html=True,
                )
            elif rec["type"] == "final_response":
                st.markdown(f"**Step {rec['step']}: Final response**")
                st.write(rec["content"])


# --- Sidebar ---

with st.sidebar:
    st.header("Aressa HR Dashboard")
    mode = st.radio(
        "Mode",
        options=["Skill Gap Analysis", "Cert Recommendations"],
        key="mode",
    )

    st.divider()

    st.subheader("Upload data")
    st.caption("Append rows to the database from a CSV.")
    entity = st.selectbox(
        "Entity type",
        ["employees", "certifications", "performance_reviews"],
    )
    uploaded = st.file_uploader("CSV file", type=["csv"], key="csv_uploader")
    if uploaded is not None and st.button("Ingest CSV"):
        try:
            df = pd.read_csv(uploaded).fillna("")
            count = 0
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                if entity == "employees":
                    db.upsert_employee(**row_dict)
                elif entity == "certifications":
                    db.upsert_certification(**row_dict)
                else:
                    db.upsert_review(**row_dict)
                count += 1
            st.success(f"Ingested {count} {entity} rows.")
        except (pd.errors.ParserError, KeyError, TypeError) as e:
            st.error(f"CSV ingestion failed: {type(e).__name__}: {e}")

    st.divider()

    st.subheader("Danger zone")
    if st.checkbox("I want to reset all data"):
        if st.button("Reset DB and re-seed"):
            db.reset_all()
            counts = db.seed_from_csvs(
                "employees.csv", "certifications.csv", "performance_reviews.csv"
            )
            st.success(
                f"Reset complete. Re-seeded {counts['employees']} employees, "
                f"{counts['certifications']} certs, {counts['performance_reviews']} reviews."
            )
            st.rerun()


# --- Main panel ---

st.title(mode)


if mode == "Skill Gap Analysis":
    st.write("Identify thin coverage of skills or certifications across teams. Examples: *cloud coverage in Engineering*, *expired certifications company-wide*, *who can renew their AWS certs*.")
    query = st.text_input(
        "Describe the scope",
        placeholder="e.g. cloud coverage in Engineering, or expired certs",
    )
    if st.button("Run analysis", disabled=not query.strip(), key="skill_gap_run"):
        with st.spinner("Analyzing..."):
            result = run_agent(skill_gap_agent, query)
        if result:
            report = result.output
            st.subheader(report.scope)
            st.write(report.summary)

            if not report.gaps:
                st.info("No gaps identified.")
            else:
                color_for = {"low": "green", "medium": "orange", "high": "red"}
                for gap in report.gaps:
                    color = color_for.get(gap.risk_level, "gray")
                    with st.container(border=True):
                        st.markdown(
                            f":{color}[**{gap.risk_level.upper()}**] — **{gap.skill_or_category}**"
                        )
                        st.markdown(f"**Coverage:** {gap.current_coverage}")
                        st.markdown(f"**Action:** {gap.recommended_action}")
            render_trace(result)


elif mode == "Cert Recommendations":
    st.write("Recommend specific certifications and training for one employee. The agent looks at the employee's role, level, existing certs (including any that have expired), and recent review growth areas.")
    employees = db.list_employees()
    if not employees:
        st.warning("No employees in the database. Upload an employees CSV in the sidebar.")
    else:
        employees.sort(key=lambda e: e["employee_id"])
        options = {f"{e['employee_id']} — {e['name']} ({e['role']})": e["employee_id"] for e in employees}
        choice = st.selectbox("Employee", list(options.keys()))
        eid = options[choice]
        if st.button("Run analysis", key="rec_run"):
            with st.spinner("Analyzing..."):
                result = run_agent(
                    recommendation_agent,
                    f"Recommend certifications for employee {eid}",
                )
            if result:
                report = result.output
                st.subheader(f"For {report.employee_name} ({report.employee_id})")
                st.write(report.overall_reasoning)

                if not report.recommended_certs:
                    st.info("No certifications recommended.")
                else:
                    for c in report.recommended_certs:
                        with st.expander(f"{c.cert_name} — {c.issuer}"):
                            st.write(c.reasoning)
                render_trace(result)
