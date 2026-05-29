"""
Pluggable ingestion sources for the Aressa HR dashboard.

Defines the contract any external HR system must satisfy to feed the
ChromaDB layer (db.py): three list_* methods returning plain dicts that
match the columns of the seed CSVs, plus a human-readable source_name.

CsvFileSource is the reference implementation backed by local CSVs.

BambooHRSource and CredlySource are stubs documenting the pattern for a
real adapter — endpoints, auth, and field mappings are commented in
their docstrings so someone with API access can fill them in without
re-deriving the design.
"""

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class IngestionSource(ABC):
    """Contract for any system that can supply HR data to the dashboard.

    All list_* methods return lists of plain dicts whose keys exactly match
    the column names db.upsert_* expects (see db.py). This keeps the source
    decoupled from the storage layer — implementations only need to adapt
    their API's response shape into these dicts.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name shown in the UI (e.g. 'CSV files', 'BambooHR', 'Credly')."""

    @abstractmethod
    def list_employees(self) -> list[dict]:
        """Each dict: employee_id, name, role, department, level, hire_date, manager_id."""

    @abstractmethod
    def list_certifications(self) -> list[dict]:
        """Each dict: employee_id, cert_name, issuer, category, date_earned, expires_on."""

    @abstractmethod
    def list_performance_reviews(self) -> list[dict]:
        """Each dict: employee_id, review_period, overall_score, strengths, growth_areas, reviewer_id."""


class CsvFileSource(IngestionSource):
    """Reference implementation: reads from three local CSV files.

    Used by the dashboard on first launch. Also serves as the contract test —
    any real adapter should produce dicts indistinguishable from what this
    source returns for the same logical data.
    """

    def __init__(
        self,
        employees_csv: str | Path,
        certifications_csv: str | Path,
        reviews_csv: str | Path,
    ):
        self._employees_csv = str(employees_csv)
        self._certifications_csv = str(certifications_csv)
        self._reviews_csv = str(reviews_csv)

    @property
    def source_name(self) -> str:
        return "CSV files"

    def list_employees(self) -> list[dict]:
        return pd.read_csv(self._employees_csv).fillna("").to_dict("records")

    def list_certifications(self) -> list[dict]:
        return pd.read_csv(self._certifications_csv).fillna("").to_dict("records")

    def list_performance_reviews(self) -> list[dict]:
        return pd.read_csv(self._reviews_csv).fillna("").to_dict("records")


# ----------------------------------------------------------------------------
# The classes below are intentional stubs. They document the pattern for a
# real integration so that someone with API access can fill them in without
# re-deriving the design from scratch.
# ----------------------------------------------------------------------------


class BambooHRSource(IngestionSource):
    """STUB — BambooHR adapter. Not implemented.

    A real implementation would:

    Auth:
      BambooHR uses basic auth with the API key as the username and any
      string as the password (their convention is "x").
      Construct with `httpx.Client(auth=(api_key, "x"))`.

    Base URL:
      https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/

    Employees: GET employees/directory
      Maps `id` -> employee_id, `displayName` -> name, `jobTitle` -> role,
      `department` -> department, `hireDate` -> hire_date. BambooHR doesn't
      expose level out of the box — typically lives in a custom field
      (e.g. `customFields.jobLevel`).

    Certifications: BambooHR has no native cert object. Two common patterns:
      (1) Custom table — GET employees/{id}/tables/{custom_table_name}
      (2) Federate from Credly via [[CredlySource]] and join by employee email.

    Performance reviews: GET reports/custom + filter to perf review fields.
      The exact field names depend on the customer's BambooHR configuration.

    Pagination / rate limits: BambooHR is rate-limited at 1000 req/hr per
    account. Bulk endpoints like employees/directory return everything in
    one response so paging is rarely needed for a 10-1000 employee org.
    """

    def __init__(self, subdomain: str, api_key: str):
        self.subdomain = subdomain
        self.api_key = api_key

    @property
    def source_name(self) -> str:
        return f"BambooHR ({self.subdomain})"

    def list_employees(self) -> list[dict]:
        raise NotImplementedError("BambooHR adapter is a documented stub — see class docstring.")

    def list_certifications(self) -> list[dict]:
        raise NotImplementedError("BambooHR adapter is a documented stub — see class docstring.")

    def list_performance_reviews(self) -> list[dict]:
        raise NotImplementedError("BambooHR adapter is a documented stub — see class docstring.")


class CredlySource(IngestionSource):
    """STUB — Credly adapter. Cert-only source. Not implemented.

    Credly is the most realistic free target for cert data — their public
    credentialing API is queryable without OAuth for basic lookups.

    Base URL: https://api.credly.com/v1/

    Auth: Bearer token in `Authorization` header. For org-level data
    (issued credentials within your organization), you need the org
    admin to provision a token.

    Earned credentials: GET organizations/{org_id}/badges?filter[user_email]={email}
      Returns badge records. Map `badge_template.name` -> cert_name,
      `badge_template.issuer.name` -> issuer, `issued_at` -> date_earned,
      `expires_at` -> expires_on. Category is harder — Credly's taxonomy
      uses skill tags rather than a single category, so you'd either pick
      the first tag or maintain a mapping.

    Employee join: Credly identifies people by email, not by internal id.
    The list_certifications method needs the roster first (typically from
    [[BambooHRSource]] or similar) to know which emails to query.

    Rate limits: Credly's public API limits to ~600 req/hr. For a 10-1000
    employee org you'd batch with one request per employee, well under
    that ceiling.

    Note: Credly is cert-only. list_employees and list_performance_reviews
    raise NotImplementedError unconditionally because that data isn't
    in Credly's domain. In practice you'd compose this with another
    source (CompositeSource pattern) rather than using it standalone.
    """

    def __init__(self, organization_id: str, bearer_token: str, employee_emails: dict[str, str]):
        """employee_emails maps employee_id -> email so credentials can be
        joined back to the internal roster."""
        self.organization_id = organization_id
        self.bearer_token = bearer_token
        self.employee_emails = employee_emails

    @property
    def source_name(self) -> str:
        return f"Credly (org {self.organization_id})"

    def list_employees(self) -> list[dict]:
        raise NotImplementedError("Credly does not provide employee data — compose with an HRIS source.")

    def list_certifications(self) -> list[dict]:
        raise NotImplementedError("Credly adapter is a documented stub — see class docstring.")

    def list_performance_reviews(self) -> list[dict]:
        raise NotImplementedError("Credly does not provide review data — compose with an HRIS source.")
