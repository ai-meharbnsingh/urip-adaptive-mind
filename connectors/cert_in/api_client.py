"""
Thin HTTPX client wrapper for CERT-In.

Handles:
- RSS feed parsing (feedparser-style manual parse via xml.etree)
- HTML scraper fallback (BeautifulSoup) for advisories listing
- Public source — no auth headers required
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from connectors.cert_in.schemas import CertInAdvisory

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.cert-in.org.in"
DEFAULT_TIMEOUT = 30.0
RSS_PATH = "/s2cMainServlet?pageid=PUBVLNOTES01"


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Best-effort RSS date parse."""
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%d %b %Y",
        "%B %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_table_date(date_str: str) -> Optional[datetime]:
    """Best-effort table date parse."""
    formats = [
        "%B %d, %Y",
        "%d %b %Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.replace(tzinfo=timezone(offset=__import__("datetime").timedelta(hours=5, minutes=30)))
        except ValueError:
            continue
    return None


class CertInAPIClient:
    """Synchronous HTTPX client for CERT-In RSS + HTML advisories."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def validate_connectivity(self) -> bool:
        """Check that the CERT-In site is reachable via the RSS/advisories path."""
        try:
            resp = self._client.get(f"{self.base_url}{RSS_PATH}")
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("CERT-In connectivity check failed")
            return False

    def fetch_rss(self) -> list[CertInAdvisory]:
        """Fetch and parse the CERT-In RSS feed."""
        url = f"{self.base_url}{RSS_PATH}"
        resp = self._client.get(url)
        resp.raise_for_status()
        return self._parse_rss(resp.text)

    def _parse_rss(self, xml_text: str) -> list[CertInAdvisory]:
        advisories: list[CertInAdvisory] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("CERT-In RSS parse error: %s", exc)
            return advisories

        # Handle both rss/channel/item and feed/entry
        channel = root.find("channel")
        if channel is not None:
            items = channel.findall("item")
        else:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if not items:
                items = root.findall("entry")

        for item in items:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_date_el = item.find("pubDate")
            desc_el = item.find("description")

            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            pub_date = (pub_date_el.text or "").strip() if pub_date_el is not None else ""
            description = (desc_el.text or "").strip() if desc_el is not None else ""

            # Extract CERT-In ID from link or title
            cert_in_id = self._extract_cert_in_id(link, title)

            # Parse description for CVE / severity / products / mitigation hints
            cve_refs = self._extract_cves(description)
            severity = self._extract_severity(description, title)
            products = self._extract_products(description)
            mitigation = self._extract_mitigation(description)

            advisories.append(
                CertInAdvisory(
                    cert_in_id=cert_in_id,
                    title=title,
                    severity=severity,
                    affected_products=products,
                    cve_refs=cve_refs,
                    description=description or title,
                    mitigation=mitigation,
                    published_at=_parse_rss_date(pub_date),
                    source_url=link or None,
                )
            )

        return advisories

    def fetch_scrape(self) -> list[CertInAdvisory]:
        """Scrape the CERT-In advisories HTML listing page."""
        url = f"{self.base_url}{RSS_PATH}"
        resp = self._client.get(url)
        resp.raise_for_status()
        return self._parse_html(resp.text)

    def _parse_html(self, html_text: str) -> list[CertInAdvisory]:
        advisories: list[CertInAdvisory] = []
        soup = BeautifulSoup(html_text, "html.parser")
        table = soup.find("table", {"id": "idTable"})
        if table is None:
            table = soup.find("table")
        if table is None:
            logger.warning("CERT-In HTML scrape: no table found")
            return advisories

        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            cert_in_id = (cols[0].get_text(strip=True)) or ""
            title = (cols[1].get_text(strip=True)) or ""
            severity = (cols[2].get_text(strip=True)) or "Medium"
            date_str = (cols[3].get_text(strip=True)) or ""

            if not cert_in_id:
                continue

            advisories.append(
                CertInAdvisory(
                    cert_in_id=cert_in_id,
                    title=title,
                    severity=severity,
                    affected_products=[],
                    cve_refs=[],
                    description=title,
                    mitigation=None,
                    published_at=_parse_table_date(date_str),
                    source_url=f"{self.base_url}/s2cMainServlet?pageid=PUBVLNOTES01&noteno={cert_in_id}",
                )
            )

        return advisories

    @staticmethod
    def _extract_cert_in_id(link: str, title: str) -> str:
        import re
        m = re.search(r"noteno=([A-Z0-9\-]+)", link, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r"(CIVN-\d{4}-\d+)", title)
        if m:
            return m.group(1)
        return ""

    @staticmethod
    def _extract_cves(text: str) -> list[str]:
        import re
        return re.findall(r"CVE-\d{4}-\d+", text, re.IGNORECASE)

    @staticmethod
    def _extract_severity(text: str, title: str) -> str:
        for word in ("Critical", "High", "Medium", "Low"):
            if word.lower() in text.lower() or word.lower() in title.lower():
                return word
        return "Medium"

    @staticmethod
    def _extract_products(text: str) -> list[str]:
        # Heuristic: look for product names after "Product:" or "Affected:"
        import re
        m = re.search(r"(?:Product|Affected)\s*:?\s*([^|]+)", text, re.IGNORECASE)
        if m:
            return [p.strip() for p in m.group(1).split(",") if p.strip()]
        return []

    @staticmethod
    def _extract_mitigation(text: str) -> Optional[str]:
        import re
        m = re.search(r"(?:Mitigation|Solution|Workaround|Upgrade)\s*:?\s*([^|]+)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CertInAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
