"""
Reproducible eval suite for the Aressa HR agents.

Each eval runs one query against one of the live agents and applies a small
set of intentionally loose assertions — strict enough to catch real
regressions (wrong employee surfaced, wrong risk level, missing growth-area
coverage) but loose enough to survive LLM phrasing variation.

Run with: python evals.py

Hits the live Gemini API. ~5 calls × ~20-40s each = ~2-3 minutes per full run.
Not intended for every commit — run after prompt, model, or data changes.
"""

import asyncio
from dataclasses import dataclass

from agent import skill_gap_agent, recommendation_agent


@dataclass
class EvalResult:
    name: str
    passed: bool
    failures: list[str]


def _text_blob(report) -> str:
    """Lowercase concatenation of every string field in a report — for substring checks."""
    parts: list[str] = []
    for field, value in report.model_dump().items():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    parts.extend(str(v) for v in item.values() if isinstance(v, str))
                elif isinstance(item, str):
                    parts.append(item)
    return " ".join(parts).lower()


def _mentions_any(text: str, candidates: list[str]) -> bool:
    return any(c.lower() in text for c in candidates)


# --- Skill-gap evals ---

async def eval_skill_gap_expired_certs() -> EvalResult:
    """The expired-certs query should surface multiple gaps tagged MEDIUM/HIGH
    and name several of the employees with at least one expired cert."""
    result = await skill_gap_agent.run("expired certifications across the company")
    report = result.output
    blob = _text_blob(report)
    failures: list[str] = []

    if len(report.gaps) < 3:
        failures.append(f"expected >=3 gaps, got {len(report.gaps)}")

    for g in report.gaps:
        if "expired" in g.current_coverage.lower() and g.risk_level == "low":
            failures.append(f"expired-cert gap marked LOW risk: {g.skill_or_category!r}")

    # Of the 5 employees with at least one expired cert (e002, e003, e005, e008, e009),
    # the agent should name at least 3 by name or id.
    expired_owner_names = ["priya", "jordan", "riley", "casey", "drew"]
    expired_owner_ids = ["e002", "e003", "e005", "e008", "e009"]
    name_hits = sum(1 for n in expired_owner_names if n in blob)
    id_hits = sum(1 for i in expired_owner_ids if i in blob)
    if max(name_hits, id_hits) < 3:
        failures.append(
            f"expected >=3 expired-cert employees named/id'd; got {name_hits} names + {id_hits} ids"
        )

    return EvalResult("skill_gap_expired_certs", not failures, failures)


async def eval_skill_gap_kubernetes() -> EvalResult:
    """Kubernetes query should flag the single-holder situation (Priya/e002 is the
    only person with CKA/CKAD certs)."""
    result = await skill_gap_agent.run("kubernetes coverage across the company")
    report = result.output
    blob = _text_blob(report)
    failures: list[str] = []

    if not report.gaps:
        failures.append("expected at least 1 gap, got 0")

    if not _mentions_any(blob, ["kubernetes", "cka", "ckad"]):
        failures.append("output never mentions kubernetes/cka/ckad")

    if not _mentions_any(blob, ["priya", "e002"]):
        failures.append("output never mentions Priya (e002), the only Kubernetes-cert holder")

    has_med_or_high = any(g.risk_level in ("medium", "high") for g in report.gaps)
    if report.gaps and not has_med_or_high:
        failures.append("expected at least one MEDIUM or HIGH risk gap; all gaps were LOW")

    return EvalResult("skill_gap_kubernetes", not failures, failures)


# --- Cert-recommendation evals ---

async def eval_cert_rec_priya_renewal() -> EvalResult:
    """Recs for Priya (e002) should include renewing the expired AWS Solutions
    Architect Professional cert."""
    result = await recommendation_agent.run("Recommend certifications for employee e002")
    report = result.output
    failures: list[str] = []

    if report.employee_id != "e002":
        failures.append(f"wrong employee_id in output: {report.employee_id!r}")

    if not (2 <= len(report.recommended_certs) <= 4):
        failures.append(f"expected 2-4 recommendations, got {len(report.recommended_certs)}")

    rec_blob = " ".join(
        f"{c.cert_name} {c.reasoning}" for c in report.recommended_certs
    ).lower()
    if "aws" not in rec_blob:
        failures.append("no AWS-related recommendation surfaced")
    if not _mentions_any(rec_blob, ["renew", "expired", "lapsed", "re-cert", "recertif"]):
        failures.append("no recommendation framed as a renewal of an expired cert")

    return EvalResult("cert_rec_priya_renewal", not failures, failures)


async def eval_cert_rec_quinn_junior() -> EvalResult:
    """Recs for Quinn (e010, IC2 backend) should target a mid-level next step,
    ideally referencing the growth area around designing/launching features."""
    result = await recommendation_agent.run("Recommend certifications for employee e010")
    report = result.output
    failures: list[str] = []

    if report.employee_id != "e010":
        failures.append(f"wrong employee_id in output: {report.employee_id!r}")

    if not (2 <= len(report.recommended_certs) <= 4):
        failures.append(f"expected 2-4 recommendations, got {len(report.recommended_certs)}")

    rec_blob = " ".join(
        f"{c.cert_name} {c.reasoning}" for c in report.recommended_certs
    ).lower()
    if not _mentions_any(
        rec_blob, ["design", "architect", "rfc", "launch", "next level", "ic3", "scope"]
    ):
        failures.append("no recommendation tied to Quinn's design / launch growth area")

    return EvalResult("cert_rec_quinn_junior", not failures, failures)


async def eval_cert_rec_morgan_collaboration() -> EvalResult:
    """Recs for Morgan (e006, declining-engagement researcher) should address the
    collaboration / responsiveness growth area, not just more research certs."""
    result = await recommendation_agent.run("Recommend certifications for employee e006")
    report = result.output
    failures: list[str] = []

    if report.employee_id != "e006":
        failures.append(f"wrong employee_id in output: {report.employee_id!r}")

    rec_blob = " ".join(
        f"{c.cert_name} {c.reasoning}" for c in report.recommended_certs
    ).lower()
    reasoning_blob = report.overall_reasoning.lower() + " " + rec_blob

    if not _mentions_any(
        reasoning_blob,
        ["collaboration", "communication", "engagement", "scrum", "agile", "team",
         "leadership", "mentor", "stakeholder", "cross-team", "cross-functional",
         "responsiveness"],
    ):
        failures.append(
            "no recommendation addresses Morgan's collaboration / engagement growth area"
        )

    return EvalResult("cert_rec_morgan_collaboration", not failures, failures)


# --- Runner ---

EVALS = [
    eval_skill_gap_expired_certs,
    eval_skill_gap_kubernetes,
    eval_cert_rec_priya_renewal,
    eval_cert_rec_quinn_junior,
    eval_cert_rec_morgan_collaboration,
]


async def main() -> int:
    results: list[EvalResult] = []
    for evl in EVALS:
        print(f"running {evl.__name__}...", flush=True)
        try:
            r = await evl()
        except Exception as e:
            r = EvalResult(evl.__name__, False, [f"raised {type(e).__name__}: {e}"])
        results.append(r)
        if r.passed:
            print(f"  PASS\n", flush=True)
        else:
            for f in r.failures:
                print(f"  - {f}")
            print(f"  FAIL\n", flush=True)

    n_pass = sum(1 for r in results if r.passed)
    n_total = len(results)
    print("=" * 60)
    print(f"  {n_pass}/{n_total} passed")
    print("=" * 60)
    for r in results:
        marker = "PASS" if r.passed else "FAIL"
        print(f"  [{marker}] {r.name}")
    return 0 if n_pass == n_total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
