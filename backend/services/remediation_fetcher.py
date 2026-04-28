from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_NVD_CACHE_TTL_SECONDS = 24 * 60 * 60
_nvd_cache: dict[str, tuple[list[str], float]] = {}


class NormalizedFinding(BaseModel):
    source: str
    finding_type: str

    cve_id: str | None = None
    advisory_text: str | None = None

    remediation_recommendation: str | None = None
    researcher_recommendation: str | None = None

    alert_type: str | None = None

    indicator_type: str | None = None
    indicator_value: str | None = None

    dmarc_rua_email: str | None = None

    remediation_steps: list[str] = Field(default_factory=list)


def fetch_remediation(finding: NormalizedFinding) -> list[str]:
    """
    v3 §4.1 — Remediation Steps per risk
    """
    ft = (finding.finding_type or "").strip().lower()

    if ft == "cve":
        steps: list[str] = []
        if finding.cve_id:
            steps.extend(_fetch_nvd_remediation(finding.cve_id))
        steps.extend(_extract_action_items(finding.advisory_text))
        return _dedupe_steps(steps)

    if ft in {"cert_in", "cert-in", "certin"}:
        return _dedupe_steps(_extract_action_items(finding.advisory_text))

    if ft == "vapt":
        if finding.remediation_recommendation and finding.remediation_recommendation.strip():
            return [finding.remediation_recommendation.strip()]
        return []

    if ft in {"bug_bounty", "bugbounty"}:
        if finding.researcher_recommendation and finding.researcher_recommendation.strip():
            return [finding.researcher_recommendation.strip()]
        return []

    if ft in {"soc_alert", "soc"}:
        return _soc_playbook_steps(finding.alert_type)

    if ft == "ioc_match":
        return _ioc_playbook_steps(finding.indicator_type, finding.indicator_value)

    if ft == "ssl_expired":
        return [
            "Renew SSL certificate.",
            "Update DNS A/AAAA records if needed.",
            "Verify via SSL Labs after renewal.",
        ]

    if ft == "missing_dmarc":
        email = (finding.dmarc_rua_email or "admin@example.com").strip()
        return [
            f"Add DMARC TXT record to DNS: v=DMARC1; p=quarantine; rua=mailto:{email}",
        ]

    # Default: if caller already provided steps, respect them.
    if finding.remediation_steps:
        return _dedupe_steps(finding.remediation_steps)
    return []


def _soc_playbook_steps(alert_type: str | None) -> list[str]:
    key = (alert_type or "").strip().lower()
    playbook: dict[str, list[str]] = {
        "rogue_device": [
            "Isolate device via NAC/EDR (e.g., Forescout).",
            "Identify owner and confirm device registration.",
            "Remove device from network if unauthorized.",
        ],
        "malware_detected": [
            "Isolate host via EDR.",
            "Collect forensic triage (process tree, persistence, network connections).",
            "Reimage or remediate, then re-scan.",
        ],
    }
    return playbook.get(key, ["Follow the relevant incident response playbook for this alert type."])


def _ioc_playbook_steps(indicator_type: str | None, indicator_value: str | None) -> list[str]:
    it = (indicator_type or "").strip().lower()
    val = (indicator_value or "").strip()
    target = f"{it}:{val}" if it and val else (val or it or "indicator")
    return [
        f"Block {target} at firewall/DNS/EDR as appropriate.",
        "Revoke any active sessions or tokens associated with the indicator.",
        "Hunt for lateral movement and persistence in logs.",
    ]


_ACTION_SENTENCE_RE = re.compile(
    r"(?i)\b(apply|update|upgrade|disable|enable|restart|remove|renew|add|block|isolate|rotate)\b[^.\n]*",
)


def _extract_action_items(text: str | None) -> list[str]:
    if not text:
        return []
    t = " ".join(text.split())
    matches = [m.group(0).strip().rstrip(";,:") for m in _ACTION_SENTENCE_RE.finditer(t)]
    return [m for m in matches if m]


def _dedupe_steps(steps: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in steps:
        if not isinstance(s, str):
            continue
        step = s.strip()
        if not step:
            continue
        key = step.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(step)
    return out


def _fetch_nvd_remediation(cve_id: str) -> list[str]:
    cve = (cve_id or "").strip().upper()
    if not cve:
        return []

    now = time.monotonic()
    cached = _nvd_cache.get(cve)
    if cached is not None:
        steps, loaded_at = cached
        if (now - loaded_at) < _NVD_CACHE_TTL_SECONDS:
            return list(steps)

    steps = _fetch_nvd_remediation_uncached(cve)
    _nvd_cache[cve] = (list(steps), now)
    return steps


def _fetch_nvd_remediation_uncached(cve_id: str) -> list[str]:
    try:
        resp = httpx.get(_NVD_CVE_API, params={"cveId": cve_id}, timeout=20.0)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
        logger.warning("NVD remediation fetch failed for %s (%s)", cve_id, type(exc).__name__)
        return []

    urls: list[str] = []
    for vuln in payload.get("vulnerabilities", []) or []:
        cve = (vuln or {}).get("cve") or {}
        for ref in (cve.get("references") or []):
            url = (ref or {}).get("url")
            if url:
                urls.append(str(url))

    urls = _dedupe_steps(urls)
    steps: list[str] = []
    if urls:
        steps.append(f"Review NVD/vendor references for {cve_id}:")
        steps.extend(urls[:5])
    return steps
