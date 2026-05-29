"""
ChromaDB wrapper for the HR talent-development dashboard.

Three persistent collections under ./.chroma:
  - employees: one record per employee. Document = synthesized profile blurb.
  - certifications: one record per (employee, cert). Document = cert_name + issuer + category.
  - performance_reviews: one record per (employee, review_period). Document = strengths + growth_areas.

All metadata is flat scalars (Chroma constraint). Composite IDs make upserts idempotent.
"""

from pathlib import Path
import pandas as pd
import chromadb

CHROMA_DIR = Path(__file__).parent / ".chroma"
EMPLOYEES = "employees"
CERTIFICATIONS = "certifications"
REVIEWS = "performance_reviews"

# Eager init on the main thread at import time — Pydantic AI dispatches
# sync tools to anyio worker threads in parallel, and Chroma's singleton
# tracker corrupts if PersistentClient is constructed concurrently.
_client = chromadb.PersistentClient(path=str(CHROMA_DIR))


def _collection(name: str):
    return _client.get_or_create_collection(name=name)


def _where(filters: dict) -> dict | None:
    filters = {k: v for k, v in filters.items() if v is not None and v != ""}
    if not filters:
        return None
    if len(filters) == 1:
        return filters
    return {"$and": [{k: v} for k, v in filters.items()]}


# --- Empty / reset ---

def is_empty() -> bool:
    """True if any of the three collections has zero records."""
    return any(_collection(name).count() == 0 for name in (EMPLOYEES, CERTIFICATIONS, REVIEWS))


def reset_all() -> None:
    for name in (EMPLOYEES, CERTIFICATIONS, REVIEWS):
        try:
            _client.delete_collection(name)
        except Exception:
            pass
        _client.get_or_create_collection(name=name)


# --- Employees ---

def _employee_document(name: str, role: str, department: str, level: str, hire_date: str, manager_id: str) -> str:
    manager_phrase = f", reports to manager {manager_id}" if manager_id else ""
    return f"{name} - {role} in {department}, level {level}, hired {hire_date}{manager_phrase}"


def upsert_employee(employee_id: str, name: str, role: str, department: str, level: str, hire_date: str, manager_id: str = "") -> str:
    manager_id = manager_id or ""
    doc = _employee_document(name, role, department, level, hire_date, manager_id)
    meta = {
        "name": name,
        "role": role,
        "department": department,
        "level": level,
        "hire_date": hire_date,
        "manager_id": manager_id,
    }
    _collection(EMPLOYEES).upsert(ids=[employee_id], documents=[doc], metadatas=[meta])
    return employee_id


def get_employee(employee_id: str) -> dict | None:
    result = _collection(EMPLOYEES).get(ids=[employee_id], include=["documents", "metadatas"])
    if not result["ids"]:
        return None
    return {"employee_id": employee_id, "profile": result["documents"][0], **result["metadatas"][0]}


def list_employees(department: str | None = None, level: str | None = None) -> list[dict]:
    where = _where({"department": department, "level": level})
    kwargs = {"include": ["documents", "metadatas"]}
    if where:
        kwargs["where"] = where
    result = _collection(EMPLOYEES).get(**kwargs)
    return [
        {"employee_id": eid, "profile": doc, **meta}
        for eid, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
    ]


def search_employees(query: str, k: int = 5) -> list[dict]:
    result = _collection(EMPLOYEES).query(query_texts=[query], n_results=k)
    return [
        {"employee_id": eid, "profile": doc, "distance": dist, **meta}
        for eid, doc, meta, dist in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


# --- Certifications ---

def _cert_id(employee_id: str, cert_name: str) -> str:
    return f"{employee_id}::{cert_name}"


def upsert_certification(employee_id: str, cert_name: str, issuer: str, category: str, date_earned: str, expires_on: str = "") -> str:
    expires_on = expires_on or ""
    doc = f"{cert_name} - issued by {issuer}, category {category}"
    meta = {
        "employee_id": employee_id,
        "cert_name": cert_name,
        "issuer": issuer,
        "category": category,
        "date_earned": date_earned,
        "expires_on": expires_on,
    }
    cid = _cert_id(employee_id, cert_name)
    _collection(CERTIFICATIONS).upsert(ids=[cid], documents=[doc], metadatas=[meta])
    return cid


def list_certifications(employee_id: str | None = None, category: str | None = None) -> list[dict]:
    where = _where({"employee_id": employee_id, "category": category})
    kwargs = {"include": ["documents", "metadatas"]}
    if where:
        kwargs["where"] = where
    result = _collection(CERTIFICATIONS).get(**kwargs)
    return [
        {"cert_id": cid, "cert_text": doc, **meta}
        for cid, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
    ]


def search_certifications(query: str, k: int = 5) -> list[dict]:
    result = _collection(CERTIFICATIONS).query(query_texts=[query], n_results=k)
    return [
        {"cert_id": cid, "cert_text": doc, "distance": dist, **meta}
        for cid, doc, meta, dist in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


# --- Performance reviews ---

def _review_id(employee_id: str, review_period: str) -> str:
    return f"{employee_id}::{review_period}"


def upsert_review(employee_id: str, review_period: str, overall_score: int, strengths: str, growth_areas: str, reviewer_id: str = "") -> str:
    reviewer_id = reviewer_id or ""
    doc = f"Strengths: {strengths}\nGrowth areas: {growth_areas}"
    meta = {
        "employee_id": employee_id,
        "review_period": review_period,
        "overall_score": int(overall_score),
        "reviewer_id": reviewer_id,
    }
    rid = _review_id(employee_id, review_period)
    _collection(REVIEWS).upsert(ids=[rid], documents=[doc], metadatas=[meta])
    return rid


def list_reviews(employee_id: str | None = None, min_score: int | None = None) -> list[dict]:
    filters: dict = {"employee_id": employee_id}
    if min_score is not None:
        filters["overall_score"] = {"$gte": int(min_score)}
    where = _where(filters)
    kwargs = {"include": ["documents", "metadatas"]}
    if where:
        kwargs["where"] = where
    result = _collection(REVIEWS).get(**kwargs)
    return [
        {"review_id": rid, "review_text": doc, **meta}
        for rid, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
    ]


def search_reviews(query: str, k: int = 5) -> list[dict]:
    result = _collection(REVIEWS).query(query_texts=[query], n_results=k)
    return [
        {"review_id": rid, "review_text": doc, "distance": dist, **meta}
        for rid, doc, meta, dist in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


# --- Bulk seed ---

def seed_from_csvs(employees_csv: str, certifications_csv: str, reviews_csv: str) -> dict:
    """Ingest all three CSVs into their collections. Idempotent (uses upsert)."""
    emp_df = pd.read_csv(employees_csv).fillna("")
    cert_df = pd.read_csv(certifications_csv).fillna("")
    rev_df = pd.read_csv(reviews_csv).fillna("")

    for _, r in emp_df.iterrows():
        upsert_employee(**r.to_dict())
    for _, r in cert_df.iterrows():
        upsert_certification(**r.to_dict())
    for _, r in rev_df.iterrows():
        upsert_review(**r.to_dict())

    return {
        "employees": len(emp_df),
        "certifications": len(cert_df),
        "performance_reviews": len(rev_df),
    }
