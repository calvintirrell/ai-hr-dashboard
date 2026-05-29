"""
Talent Growth Agent — internal HR dashboard.

Three focused Pydantic AI agents, all sharing the same tool kit (db.py wrappers):
  - skill_gap_agent      -> SkillGapReport
  - promotion_agent      -> PromotionCandidates
  - recommendation_agent -> CertRecommendation
"""

from typing import Literal
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from dotenv import load_dotenv
from agent_tracer import print_agent_trace
import datetime as dt
import nest_asyncio
import db

load_dotenv()
nest_asyncio.apply()

MODEL = "google:gemini-3-flash-preview"


# --- Structured outputs ---

class CandidateSummary(BaseModel):
    employee_id: str
    name: str
    rationale: str = Field(description="Why this person is a strong candidate, citing specific certifications and review evidence.")
    suggested_next_role: str | None = Field(default=None, description="A concrete next title or scope.")


class PromotionCandidates(BaseModel):
    candidates: list[CandidateSummary]
    overall_summary: str = Field(description="One short paragraph summarizing the slate.")


class SkillGap(BaseModel):
    skill_or_category: str
    current_coverage: str = Field(description="How thin the coverage currently is, with specific numbers or names.")
    risk_level: Literal["low", "medium", "high"]
    recommended_action: str


class SkillGapReport(BaseModel):
    scope: str = Field(description="Team, department, or 'company-wide'.")
    gaps: list[SkillGap]
    summary: str


class RecommendedCert(BaseModel):
    cert_name: str
    issuer: str
    reasoning: str = Field(description="Why this specific cert fits this employee.")


class CertRecommendation(BaseModel):
    employee_id: str
    employee_name: str
    recommended_certs: list[RecommendedCert]
    overall_reasoning: str


# --- Tools (shared across all three agents) ---

def get_today() -> str:
    """Return today's date in ISO format. Use this to check which certifications have expired."""
    return dt.date.today().isoformat()


def list_all_employees() -> list[dict]:
    """List every employee with id, name, role, department, level, hire_date, manager_id."""
    return db.list_employees()


def list_employees_in_department(department: str) -> list[dict]:
    """List employees in a specific department. Exact match. Valid values include: Engineering, Product, Design, Research, Data Science, People."""
    return db.list_employees(department=department)


def list_employees_at_level(level: str) -> list[dict]:
    """List employees at a specific level. Exact match (e.g. 'IC2', 'IC3', 'IC4', 'IC5', 'M3', 'M4', 'D5')."""
    return db.list_employees(level=level)


def search_employees_semantic(query: str) -> list[dict]:
    """Semantic search across employee profile blurbs. Use for fuzzy queries like 'senior ML engineers' or 'people working on infrastructure'."""
    return db.search_employees(query, k=10)


def get_employee_detail(employee_id: str) -> dict:
    """Get the full record for one employee: roster info + all certifications + all performance reviews. Always call this when reasoning about a single person."""
    emp = db.get_employee(employee_id)
    if not emp:
        return {"error": f"No employee found with id {employee_id}"}
    return {
        "employee": emp,
        "certifications": db.list_certifications(employee_id=employee_id),
        "reviews": db.list_reviews(employee_id=employee_id),
    }


def list_certifications_in_category(category: str) -> list[dict]:
    """List all certifications in a given category across the whole company. Valid categories: Cloud, Infra, ML, Data, Product, Management, Recruiting, Design, Leadership."""
    return db.list_certifications(category=category)


def list_all_certifications() -> list[dict]:
    """List every certification held by every employee."""
    return db.list_certifications()


def search_certifications_semantic(query: str) -> list[dict]:
    """Semantic search across certifications. Use for fuzzy queries like 'cloud architecture' or 'agile project management'."""
    return db.search_certifications(query, k=10)


def list_reviews_above_score(min_score: int) -> list[dict]:
    """List performance reviews with overall_score >= min_score (scale 1-5)."""
    return db.list_reviews(min_score=min_score)


def search_reviews_semantic(query: str) -> list[dict]:
    """Semantic search across performance review text (strengths and growth_areas). Use for fuzzy queries like 'strong mentorship' or 'collaboration challenges'."""
    return db.search_reviews(query, k=10)


def get_review_trajectory(employee_id: str) -> dict:
    """Get review trajectory for one employee sorted by period. Returns scores over time plus a trend label: 'rising', 'declining', 'stable', or 'insufficient_data'."""
    reviews = db.list_reviews(employee_id=employee_id)
    if not reviews:
        return {"employee_id": employee_id, "trajectory": [], "trend": "no_data"}
    sorted_reviews = sorted(reviews, key=lambda r: r["review_period"])
    scores = [r["overall_score"] for r in sorted_reviews]
    if len(scores) < 2:
        trend = "insufficient_data"
    elif scores[-1] > scores[0]:
        trend = "rising"
    elif scores[-1] < scores[0]:
        trend = "declining"
    else:
        trend = "stable"
    return {
        "employee_id": employee_id,
        "trajectory": [{"period": r["review_period"], "score": r["overall_score"]} for r in sorted_reviews],
        "trend": trend,
    }


SHARED_TOOLS = [
    get_today,
    list_all_employees,
    list_employees_in_department,
    list_employees_at_level,
    search_employees_semantic,
    get_employee_detail,
    list_certifications_in_category,
    list_all_certifications,
    search_certifications_semantic,
    list_reviews_above_score,
    search_reviews_semantic,
    get_review_trajectory,
]


# --- Agents ---

skill_gap_agent = Agent(
    MODEL,
    output_type=SkillGapReport,
    tools=SHARED_TOOLS,
    system_prompt=(
        "You are a talent analytics agent that identifies skill gaps at an internal HR dashboard for a company called Aressa. "
        "Use the available tools to inspect the roster, certifications by category, and review text. "
        "Surface concrete gaps with specific numbers and names — e.g. 'Only 1 of 5 Engineering employees holds a Kubernetes cert'. "
        "Always call get_today and compare against each cert's expires_on field — expired certs are a real gap. "
        "Each gap must have a risk_level (low / medium / high) and a concrete recommended_action. "
        "Do not speculate beyond what the tools return."
    ),
)


promotion_agent = Agent(
    MODEL,
    output_type=PromotionCandidates,
    tools=SHARED_TOOLS,
    system_prompt=(
        "You are a talent analytics agent that identifies promotion-ready employees at a company called Aressa. "
        "Strong candidates typically have: (1) a rising or consistently-high performance trajectory (call get_review_trajectory for each candidate), "
        "(2) recent relevant certifications, and (3) review text indicating leadership, mentorship, or readiness for next scope. "
        "Avoid recommending employees whose trajectory is declining or whose recent growth_areas flag engagement or collaboration concerns. "
        "For each candidate in your output, cite specific evidence from their certifications and review text in the rationale. "
        "Suggest a concrete next role where appropriate (e.g. 'Staff Software Engineer', 'Senior Engineering Manager')."
    ),
)


recommendation_agent = Agent(
    MODEL,
    output_type=CertRecommendation,
    tools=SHARED_TOOLS,
    system_prompt=(
        "You are a talent development agent that recommends certifications and training for one specific employee at a company called Aressa. "
        "Always start by calling get_employee_detail for the employee in question to see their role, level, existing certs, and recent reviews. "
        "Always call get_today and compare against the expires_on field of each existing cert — renewing an expired credential is a valid recommendation. "
        "Recommend 2-4 specific, real-world certifications that (a) close a stated growth_area from a recent review, "
        "(b) prepare them for the next level of their role, or (c) renew an expired credential. "
        "Avoid recommending certifications the employee already holds and which are still valid. "
        "For each recommendation, give the real cert name, the issuer, and concrete reasoning tied to this person's specific situation."
    ),
)


# --- CLI driver ---

if __name__ == "__main__":
    import asyncio

    print("Aressa Talent Growth Agent")
    print("Modes: (1) skill-gap  (2) promotion  (3) recommend  (q) quit")

    while True:
        try:
            mode = input("\nMode [1/2/3/q]: ").strip().lower()
            if mode in ("q", "exit", "quit"):
                break

            if mode == "1":
                query = input("Skill-gap question (e.g. 'cloud coverage in Engineering'): ").strip()
                if not query:
                    continue
                result = asyncio.run(skill_gap_agent.run(query))
                print_agent_trace(result)
                report = result.output
                print(f"\nScope: {report.scope}")
                print(f"Summary: {report.summary}")
                print(f"\nGaps ({len(report.gaps)}):")
                for g in report.gaps:
                    print(f"  - [{g.risk_level.upper()}] {g.skill_or_category}")
                    print(f"      Coverage: {g.current_coverage}")
                    print(f"      Action:   {g.recommended_action}")

            elif mode == "2":
                query = input("Promotion question (e.g. 'who is ready for promotion?'): ").strip()
                if not query:
                    continue
                result = asyncio.run(promotion_agent.run(query))
                print_agent_trace(result)
                report = result.output
                print(f"\nSummary: {report.overall_summary}")
                print(f"\nCandidates ({len(report.candidates)}):")
                for c in report.candidates:
                    next_role = c.suggested_next_role or "next-level scope"
                    print(f"  - {c.name} ({c.employee_id}) -> {next_role}")
                    print(f"      {c.rationale}")

            elif mode == "3":
                eid = input("Employee id (e.g. e001): ").strip()
                if not eid:
                    continue
                result = asyncio.run(recommendation_agent.run(f"Recommend certifications for employee {eid}"))
                print_agent_trace(result)
                report = result.output
                print(f"\nFor {report.employee_name} ({report.employee_id}):")
                print(f"{report.overall_reasoning}")
                print(f"\nRecommended certs ({len(report.recommended_certs)}):")
                for c in report.recommended_certs:
                    print(f"  - {c.cert_name} ({c.issuer})")
                    print(f"      {c.reasoning}")

            else:
                print("Unknown mode. Use 1, 2, 3, or q.")
        except KeyboardInterrupt:
            break

    print("\nGoodbye!")
