"""
Framework-specific report generation API.

Endpoints:
  POST /reports/{framework_short_code}/generate
        Body: {org_name?, format?: "pdf"|"html", framework_version?, ...optional template ctx}
        Returns 202 with {job_id, status, framework_short_code, format}.

  GET  /reports/{job_id}
        Returns the job metadata (status, format, framework_short_code, created_at).

  GET  /reports/{job_id}/download
        Streams the rendered PDF / HTML bytes.

  GET  /reports
        Lists past report generations (most recent first).

Storage
-------
For now, generated reports are kept in an in-process dict.  The dict is
intentionally simple — Phase 4 will swap it for a SQL-backed store + S3 blobs.
The dict is keyed by job_id (a server-side UUID) and survives the lifetime
of the process, which is enough for unit tests + dev demos.

Auth
----
All endpoints require a valid JWT (require_auth dependency, same as every other
compliance router).  Generation is allowed for any authenticated caller; we do
NOT gate on compliance-admin yet because auditors should be able to download
their own reports — we will revisit RBAC when the auditor portal wires this in.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from compliance_backend.middleware.auth import require_auth
from compliance_backend.services.reports import (
    REPORT_REGISTRY,
    get_report_template,
)


router = APIRouter(prefix="/reports", tags=["framework-reports"])


# ─────────────────────────────────────────────────────────────────────────────
# In-memory job store (process-local). Threadsafe via _lock.
# ─────────────────────────────────────────────────────────────────────────────


class _ReportJob:
    __slots__ = (
        "job_id",
        "framework_short_code",
        "format",
        "status",
        "created_at",
        "tenant_id",
        "org_name",
        "content",  # bytes for pdf, str for html
        "error",
    )

    def __init__(
        self,
        framework_short_code: str,
        fmt: str,
        tenant_id: str,
        org_name: str,
    ) -> None:
        self.job_id = str(uuid.uuid4())
        self.framework_short_code = framework_short_code
        self.format = fmt
        self.status: Literal["queued", "running", "completed", "failed"] = "queued"
        self.created_at = datetime.now(timezone.utc)
        self.tenant_id = tenant_id
        self.org_name = org_name
        self.content: Optional[bytes | str] = None
        self.error: Optional[str] = None


_JOB_STORE: Dict[str, _ReportJob] = {}
_LOCK = threading.Lock()


def _record_job(job: _ReportJob) -> None:
    with _LOCK:
        _JOB_STORE[job.job_id] = job


def _get_job(job_id: str) -> Optional[_ReportJob]:
    with _LOCK:
        return _JOB_STORE.get(job_id)


def _list_jobs(tenant_id: Optional[str]) -> List[_ReportJob]:
    with _LOCK:
        items = list(_JOB_STORE.values())
    if tenant_id is not None:
        items = [j for j in items if j.tenant_id == tenant_id]
    items.sort(key=lambda j: j.created_at, reverse=True)
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Request / response schemas
# ─────────────────────────────────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    """Request body for POST /reports/{short_code}/generate."""

    org_name: str = Field(default="Acme Corp")
    format: Literal["pdf", "html"] = Field(default="pdf")
    framework_version: Optional[str] = None
    auditor_name: Optional[str] = None
    overall_compliance_pct: Optional[float] = None
    # Free-form template context.  Each report subclass declares the keys it
    # consumes; unknown keys are silently ignored.
    context_overrides: Dict[str, Any] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    framework_short_code: str
    format: str


class JobDetail(BaseModel):
    job_id: str
    framework_short_code: str
    format: str
    status: str
    created_at: str
    org_name: str
    error: Optional[str] = None


class JobListItem(BaseModel):
    job_id: str
    framework_short_code: str
    format: str
    status: str
    created_at: str
    org_name: str


class JobList(BaseModel):
    items: List[JobListItem]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_context(req: GenerateRequest) -> Dict[str, Any]:
    """Build the template context dict from a generate request."""
    ctx: Dict[str, Any] = {
        "org_name": req.org_name,
        "framework_version": req.framework_version or "",
        "auditor_name": req.auditor_name or "",
        "overall_compliance_pct": req.overall_compliance_pct or 0.0,
    }
    # Merge user-supplied overrides (allows passing tsc_coverage, soa_controls,
    # asset_inventory, etc. through this generic endpoint).
    ctx.update(req.context_overrides or {})
    return ctx


def _render_job(job: _ReportJob, ctx: Dict[str, Any]) -> None:
    """Render the report content synchronously and stash on the job."""
    job.status = "running"
    try:
        cls = get_report_template(job.framework_short_code)
        if cls is None:
            raise RuntimeError(
                f"Unknown framework_short_code: {job.framework_short_code!r}"
            )
        instance = cls()
        if job.format == "pdf":
            job.content = instance.render_pdf(ctx)
        else:
            job.content = instance.render_html(ctx)
        job.status = "completed"
    except Exception as exc:  # noqa: BLE001 — we want to capture all errors
        job.status = "failed"
        job.error = str(exc)


def _job_to_detail(job: _ReportJob) -> JobDetail:
    return JobDetail(
        job_id=job.job_id,
        framework_short_code=job.framework_short_code,
        format=job.format,
        status=job.status,
        created_at=job.created_at.isoformat(),
        org_name=job.org_name,
        error=job.error,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/{framework_short_code}/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_report(
    framework_short_code: str,
    body: GenerateRequest,
    claims: dict = Depends(require_auth),
) -> GenerateResponse:
    """
    Kick off generation of a framework report.

    Synchronous in-process implementation: the report is rendered before
    this request returns, so the response status is "completed" by the time
    the client receives it.  We still return 202 because the API contract
    is async (so the same shape works when we move to a queue worker).
    """
    code = framework_short_code.upper()
    if code not in REPORT_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Framework '{framework_short_code}' has no report template",
        )

    tenant_id = str(claims.get("tenant_id", "unknown"))
    job = _ReportJob(
        framework_short_code=code,
        fmt=body.format,
        tenant_id=tenant_id,
        org_name=body.org_name,
    )
    _record_job(job)

    ctx = _build_context(body)
    _render_job(job, ctx)

    return GenerateResponse(
        job_id=job.job_id,
        status=job.status,
        framework_short_code=job.framework_short_code,
        format=job.format,
    )


@router.get("", response_model=JobList)
async def list_reports(claims: dict = Depends(require_auth)) -> JobList:
    """List past report generations for the caller's tenant (most recent first)."""
    tenant_id = str(claims.get("tenant_id", "unknown"))
    jobs = _list_jobs(tenant_id)
    items = [
        JobListItem(
            job_id=j.job_id,
            framework_short_code=j.framework_short_code,
            format=j.format,
            status=j.status,
            created_at=j.created_at.isoformat(),
            org_name=j.org_name,
        )
        for j in jobs
    ]
    return JobList(items=items, total=len(items))


@router.get("/{job_id}", response_model=JobDetail)
async def get_report(
    job_id: str,
    claims: dict = Depends(require_auth),
) -> JobDetail:
    """Return job metadata for the given job_id."""
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report job '{job_id}' not found",
        )
    tenant_id = str(claims.get("tenant_id", "unknown"))
    if job.tenant_id != tenant_id:
        # Don't leak existence — same 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report job '{job_id}' not found",
        )
    return _job_to_detail(job)


@router.get("/{job_id}/download")
async def download_report(
    job_id: str,
    claims: dict = Depends(require_auth),
) -> Response:
    """Stream the rendered PDF/HTML bytes."""
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report job '{job_id}' not found",
        )
    tenant_id = str(claims.get("tenant_id", "unknown"))
    if job.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report job '{job_id}' not found",
        )
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Report job '{job_id}' status is {job.status!r}",
        )
    assert job.content is not None  # for type-checker

    if job.format == "pdf":
        return Response(
            content=job.content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{job.framework_short_code}_'
                    f'{job.job_id[:8]}.pdf"'
                ),
            },
        )
    # html
    return Response(
        content=job.content,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'inline; filename="{job.framework_short_code}_'
                f'{job.job_id[:8]}.html"'
            ),
        },
    )
