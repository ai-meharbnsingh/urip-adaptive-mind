from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class SeverityNormalizer:
    """
    Normalize vendor-native severity formats into a CVSS-equivalent 0-10 float.

    v3 §3.4 — Normalization Engine
    """

    _CERTIN_MAP: dict[str, float] = {
        "critical": 9.0,
        "high": 7.5,
        "medium": 5.0,
        "low": 3.0,
    }
    _SOC_MAP = _CERTIN_MAP

    _GENERIC_STR_MAP: dict[str, float] = {
        "info": 1.0,
        "informational": 1.0,
        "low": 3.0,
        "medium": 5.0,
        "med": 5.0,
        "high": 7.5,
        "critical": 9.0,
        "crit": 9.0,
    }

    _BUG_BOUNTY_BASE: dict[str, float] = {
        "p1": 9.0,
        "p2": 7.0,
        "p3": 5.0,
        "p4": 3.0,
    }
    _BUG_BOUNTY_IMPACT_MOD: dict[str, float] = {
        "high": 0.5,
        "medium": 0.0,
        "low": -0.5,
    }
    _BUG_BOUNTY_EXPLOIT_MOD: dict[str, float] = {
        "active": 0.5,
        "weaponized": 1.0,
        "poc": 0.25,
        "none": 0.0,
        "unknown": 0.0,
    }

    def normalize(self, raw_severity: Any, source: str) -> float:
        """
        Args:
            raw_severity: source-native severity (number/string/dict).
            source: vendor/source label (case-insensitive).

        Returns:
            Float in [0.0, 10.0].

        Raises:
            ValueError: unknown source or unparseable severity for that source.
        """
        src = (source or "").strip().lower()
        if not src:
            raise ValueError("source is required")

        if src in {"crowdstrike", "spotlight", "easm", "cnapp"}:
            return self._clamp_0_10(self._to_float(raw_severity) / 10.0)

        if src == "armis":
            val = self._to_float(raw_severity)
            # Auto-detect 0-100 scale by max value.
            if val > 10.0:
                val = val / 10.0
            return self._clamp_0_10(val)

        if src == "vapt":
            return self._clamp_0_10(self._to_float(raw_severity))

        if src in {"threat_intel", "threat-intel", "threatintel"}:
            # Internal URIP feed — expected to already be CVSS-like 0-10.
            return self._clamp_0_10(self._to_float(raw_severity))

        if src in {"cert_in", "certin", "cert-in"}:
            # Some pipelines already emit CVSS-like numbers; accept them.
            try:
                return self._clamp_0_10(self._to_float(raw_severity))
            except ValueError:
                label = self._to_str(raw_severity)
                try:
                    return self._CERTIN_MAP[label]
                except KeyError as exc:
                    raise ValueError(f"Unknown CERT-In severity: {raw_severity!r}") from exc

        if src in {"soc", "soc_alert", "soc_alerts"}:
            try:
                return self._clamp_0_10(self._to_float(raw_severity))
            except ValueError:
                label = self._to_str(raw_severity)
                try:
                    return self._SOC_MAP[label]
                except KeyError as exc:
                    raise ValueError(f"Unknown SoC severity: {raw_severity!r}") from exc

        if src in {"bug_bounty", "bugbounty"}:
            return self._normalize_bug_bounty(raw_severity)

        if src == "generic":
            label = self._to_str(raw_severity)
            try:
                return self._GENERIC_STR_MAP[label]
            except KeyError as exc:
                raise ValueError(f"Unknown generic severity: {raw_severity!r}") from exc

        raise ValueError(f"Unknown source for severity normalization: {source!r}")

    def _normalize_bug_bounty(self, raw: Any) -> float:
        # Some connectors/reporting pipelines already emit a CVSS-like number.
        try:
            return self._clamp_0_10(self._to_float(raw))
        except ValueError:
            pass

        # Accept "P1" or {"priority": "P1", "impact": "...", "exploit": "..."}.
        priority: str | None = None
        impact: str | None = None
        exploit: str | None = None

        if isinstance(raw, Mapping):
            priority = raw.get("priority") or raw.get("p") or raw.get("severity")
            impact = raw.get("impact")
            exploit = raw.get("exploit") or raw.get("exploitability")
        else:
            priority = raw

        p = (str(priority).strip().lower()) if priority is not None else ""
        if p not in self._BUG_BOUNTY_BASE:
            raise ValueError(f"Unknown Bug Bounty priority: {priority!r}")

        base = self._BUG_BOUNTY_BASE[p]

        impact_key = (str(impact).strip().lower()) if impact is not None else "medium"
        exploit_key = (str(exploit).strip().lower()) if exploit is not None else "unknown"

        score = base
        score += self._BUG_BOUNTY_IMPACT_MOD.get(impact_key, 0.0)
        score += self._BUG_BOUNTY_EXPLOIT_MOD.get(exploit_key, 0.0)
        return self._clamp_0_10(score)

    @staticmethod
    def _to_float(value: Any) -> float:
        if value is None:
            raise ValueError("severity value is required")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                raise ValueError("severity value is empty")
            return float(s)
        raise ValueError(f"severity value is not numeric: {value!r}")

    @staticmethod
    def _to_str(value: Any) -> str:
        if value is None:
            raise ValueError("severity label is required")
        s = str(value).strip().lower()
        if not s:
            raise ValueError("severity label is empty")
        return s

    @staticmethod
    def _clamp_0_10(value: float) -> float:
        v = max(0.0, min(10.0, float(value)))
        # Keep one decimal of precision (CVSS-like).
        return round(v, 1)
