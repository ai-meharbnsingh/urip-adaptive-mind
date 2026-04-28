"""
connectors/base/registry.py — Plugin discovery and connector registry.

P1.6: Connector Framework Abstraction
P33-Z3: Metadata-aware listing for the Tool Catalog UI.

Design decisions
----------------
- ConnectorRegistry is a simple dict-backed store keyed by connector name.
- The module-level _global_registry instance is the canonical registry used
  by the scheduler and all decorators.
- @register_connector("name") is a class decorator that calls
  _global_registry.register(name, cls) at import time — no discovery magic,
  no file scanning needed.  Connectors self-register when their module is imported.
- Double-registration raises ValueError to catch copy-paste naming mistakes early.
- The registry stores classes (not instances); the scheduler instantiates on demand
  so each tick can get a fresh connector without shared state.
- Factory callables are also accepted (register("x", lambda: MyConnector()))
  to allow test injection of pre-configured instances.
- ``list_connectors_with_metadata()`` extracts the Tool-Catalog metadata from
  each registered class WITHOUT instantiation — class attribute access only.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Type

from connectors.base.connector import (
    CONNECTOR_CATEGORIES,
    BaseConnector,
    CredentialFieldSpec,
)
from connectors.base.setup_guide import SetupGuideSpec

logger = logging.getLogger(__name__)


# Metadata fields that MUST be set (non-empty) on every concrete connector
# for the Tool Catalog UI to render correctly.
_REQUIRED_METADATA_FIELDS: tuple[str, ...] = (
    "DISPLAY_NAME",
    "CATEGORY",
    "SHORT_DESCRIPTION",
    "STATUS",
    "MODULE_CODE",
)
_VALID_STATUSES: tuple[str, ...] = ("live", "building", "simulated", "roadmap")


class ConnectorRegistry:
    """
    Thread-safe (GIL-protected) connector name → class/factory registry.

    Usage
    -----
    registry = ConnectorRegistry()
    registry.register("tenable", TenableConnector)
    cls = registry.get("tenable")
    instance = cls()
    """

    def __init__(self) -> None:
        self._store: dict[str, Callable] = {}

    def register(self, name: str, factory: Callable) -> None:
        """
        Register a connector class or factory under `name`.

        Parameters
        ----------
        name : str
            Unique connector identifier (e.g. "tenable", "sentinelone").
        factory : Callable
            A class (subclass of BaseConnector) or a zero-arg callable that
            returns a BaseConnector instance.

        Raises
        ------
        ValueError
            If `name` is already registered.

        Notes
        -----
        Z3: Logs a WARNING (not error — backward compat) for every required
        metadata field that is missing on `factory`.  We can't raise: parallel
        workers might land their connector before metadata is filled in.
        """
        if name in self._store:
            raise ValueError(
                f"Connector '{name}' is already registered.  "
                "Use a unique name or unregister the existing one first."
            )
        self._store[name] = factory
        _warn_if_metadata_incomplete(name, factory)
        logger.debug("Registered connector: %s", name)

    def get(self, name: str) -> Callable:
        """
        Look up a connector factory by name.

        Raises
        ------
        KeyError
            If `name` is not registered.
        """
        if name not in self._store:
            raise KeyError(f"No connector registered with name '{name}'.")
        return self._store[name]

    def list_names(self) -> list[str]:
        """Return sorted list of all registered connector names."""
        return sorted(self._store.keys())

    def list_connectors_with_metadata(self) -> list[dict[str, Any]]:
        """
        Return one dict per registered connector with all Tool-Catalog metadata.

        Reads class attributes only — no instantiation, no I/O, safe to call
        on every request.  Output sorted by `name` for stable UI ordering.

        Each item:
            {
              "name": str,
              "display_name": str,
              "category": str,
              "short_description": str,
              "status": "live" | "building" | "simulated" | "roadmap",
              "vendor_docs_url": str | None,
              "supported_products": list[str] | None,
              "module_code": str,
              "credential_fields": list[dict],
            }
        """
        return [
            self._extract_metadata(name, factory)
            for name, factory in sorted(self._store.items())
        ]

    def get_connector_metadata(self, name: str) -> dict[str, Any]:
        """
        Return the full metadata dict for a single connector.

        Raises
        ------
        KeyError
            If `name` is not registered.
        """
        if name not in self._store:
            raise KeyError(f"No connector registered with name '{name}'.")
        return self._extract_metadata(name, self._store[name])

    @staticmethod
    def _extract_metadata(name: str, factory: Callable) -> dict[str, Any]:
        """
        Pull metadata off a factory (class) without calling it.

        For zero-arg lambda factories that don't expose class attrs, the
        returned dict still has the placeholder shape — the catalog will then
        show "(metadata missing)" rather than blowing up.
        """
        cls = factory if isinstance(factory, type) else getattr(factory, "__self__", None)

        # Read attributes off the class (or factory), defaulting to base values.
        display_name = getattr(factory, "DISPLAY_NAME", "") or name
        category = getattr(factory, "CATEGORY", "") or "UNCATEGORIZED"
        short_description = getattr(factory, "SHORT_DESCRIPTION", "") or ""
        status = getattr(factory, "STATUS", "live") or "live"
        vendor_docs_url = getattr(factory, "VENDOR_DOCS_URL", None)
        supported_products = getattr(factory, "SUPPORTED_PRODUCTS", None)
        module_code = getattr(factory, "MODULE_CODE", "CORE") or "CORE"

        # CREDENTIAL_FIELDS is a list of CredentialFieldSpec; serialize.
        raw_fields = getattr(factory, "CREDENTIAL_FIELDS", None) or []
        credential_fields: list[dict[str, Any]] = []
        for f in raw_fields:
            if isinstance(f, CredentialFieldSpec):
                credential_fields.append(f.to_dict())
            elif isinstance(f, dict):
                credential_fields.append(f)
            # Unknown shapes are dropped — keeps response JSON-clean.

        # SETUP_GUIDE — inline onboarding content rendered on the catalog tile.
        # Returns ``None`` if the connector has not declared one yet (registry
        # already warned at register-time).
        raw_guide = getattr(factory, "SETUP_GUIDE", None)
        setup_guide: Optional[dict[str, Any]] = None
        if isinstance(raw_guide, SetupGuideSpec):
            setup_guide = raw_guide.to_dict()
        elif isinstance(raw_guide, dict):
            # Tolerate already-serialised dicts (e.g. test injection).
            setup_guide = raw_guide

        return {
            "name": name,
            "display_name": display_name,
            "category": category,
            "short_description": short_description,
            "status": status,
            "vendor_docs_url": vendor_docs_url,
            "supported_products": supported_products,
            "module_code": module_code,
            "credential_fields": credential_fields,
            "setup_guide": setup_guide,
        }

    def __contains__(self, name: str) -> bool:
        return name in self._store

    def __len__(self) -> int:
        return len(self._store)


def _warn_if_metadata_incomplete(name: str, factory: Callable) -> None:
    """
    Emit a single WARNING per missing/invalid metadata field.

    Why warn (not raise)?  Parallel workers (CSPM team, advisory team) may land
    their connector class with TODO metadata; we don't want their import to
    crash the app — we want a loud log line so the gap is visible.
    """
    missing: list[str] = []
    for field_name in _REQUIRED_METADATA_FIELDS:
        value = getattr(factory, field_name, "")
        if not value:
            missing.append(field_name)

    if missing:
        logger.warning(
            "Connector '%s' is missing required metadata fields: %s. "
            "Tool Catalog UI will fall back to placeholder values.",
            name, missing,
        )

    # CATEGORY must be in our allow-list (or empty — already warned above).
    category = getattr(factory, "CATEGORY", "")
    if category and category not in CONNECTOR_CATEGORIES:
        logger.warning(
            "Connector '%s' has CATEGORY=%r which is not in the allow-list %s.",
            name, category, CONNECTOR_CATEGORIES,
        )

    # STATUS must be in our allow-list.
    status = getattr(factory, "STATUS", "")
    if status and status not in _VALID_STATUSES:
        logger.warning(
            "Connector '%s' has STATUS=%r which is not one of %s.",
            name, status, _VALID_STATUSES,
        )

    # SETUP_GUIDE — inline onboarding content.  Warn (not raise) when missing
    # or invalid so parallel-team imports never crash, but the gap is visible
    # in logs.  Tests then assert no warnings/missing guides at CI time.
    guide = getattr(factory, "SETUP_GUIDE", None)
    if guide is None:
        logger.warning(
            "Connector '%s' has no SETUP_GUIDE — Tool Catalog will not render "
            "inline onboarding for this tile.",
            name,
        )
    elif isinstance(guide, SetupGuideSpec):
        problems = guide.validate()
        if problems:
            logger.warning(
                "Connector '%s' SETUP_GUIDE has issues: %s", name, problems,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton — the one registry everything shares
# ─────────────────────────────────────────────────────────────────────────────

_global_registry = ConnectorRegistry()


def register_connector(name: str) -> Callable:
    """
    Class decorator that registers the decorated class with the global registry.

    Example
    -------
    @register_connector("tenable")
    class TenableConnector(BaseConnector):
        NAME = "tenable"
        ...

    After importing this module, _global_registry.get("tenable") works.
    """
    def _decorator(cls: Type[BaseConnector]) -> Type[BaseConnector]:
        # Idempotent: if already registered (e.g., module imported twice in tests)
        # just log and skip rather than raising.
        if name in _global_registry:
            logger.debug(
                "Connector '%s' already in global registry — skipping re-registration.", name
            )
            return cls
        _global_registry.register(name, cls)
        return cls
    return _decorator
