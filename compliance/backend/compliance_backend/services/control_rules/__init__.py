"""
Control rule plugin registry — P2B.3.

Decorator-based plugin system. Use @register_control_rule("rule_name") on any
class that subclasses BaseControlRule.

Usage:
    from compliance_backend.services.control_rules import register_control_rule, get_rule

    @register_control_rule("mfa_enforced")
    class MfaEnforcedRule(BaseControlRule):
        def check(self, tenant_id, context):
            ...

    rule = get_rule("mfa_enforced")
    result = rule.check("tenant-123", context)

The registry is populated at import time when builtin rules are loaded.
Call load_builtin_rules() to ensure all builtins are registered before use.
"""
from __future__ import annotations

import importlib
import logging
from typing import Dict, Optional, Type

from compliance_backend.services.control_rules.base import BaseControlRule

logger = logging.getLogger(__name__)

# Global registry: rule_name → class (not instance, so each check gets a fresh call)
_RULE_REGISTRY: Dict[str, Type[BaseControlRule]] = {}


def register_control_rule(rule_name: str):
    """
    Class decorator — registers a BaseControlRule subclass under the given name.

    Args:
        rule_name: Unique identifier used in Control.rule_function field.
                   Must be a valid Python identifier-like string.

    Raises:
        ValueError: if rule_name is already registered with a DIFFERENT class
                    (re-registering the same class is idempotent and safe).
    """
    def decorator(cls: Type[BaseControlRule]) -> Type[BaseControlRule]:
        if rule_name in _RULE_REGISTRY:
            existing = _RULE_REGISTRY[rule_name]
            if existing is not cls:
                raise ValueError(
                    f"Rule name '{rule_name}' is already registered by {existing.__name__}. "
                    f"Cannot register {cls.__name__} under the same name."
                )
            # Idempotent: same class re-registered (e.g. module reloaded) — OK
            return cls
        if not issubclass(cls, BaseControlRule):
            raise TypeError(
                f"{cls.__name__} must subclass BaseControlRule to be registered."
            )
        _RULE_REGISTRY[rule_name] = cls
        logger.debug("Registered control rule: %s → %s", rule_name, cls.__name__)
        return cls
    return decorator


def get_rule(rule_name: str) -> Optional[BaseControlRule]:
    """
    Retrieve a rule instance by name.

    Returns:
        An instance of the registered rule class, or None if not found.
    """
    cls = _RULE_REGISTRY.get(rule_name)
    if cls is None:
        return None
    return cls()


def list_rules() -> Dict[str, Type[BaseControlRule]]:
    """Return a copy of the full rule registry (name → class)."""
    return dict(_RULE_REGISTRY)


def load_builtin_rules() -> None:
    """
    Import all modules in services/control_rules/builtin/ so their
    @register_control_rule decorators fire and populate the registry.

    Call once at startup (control_engine.py does this automatically).
    Safe to call multiple times — registration is idempotent.
    """
    builtin_modules = [
        "compliance_backend.services.control_rules.builtin.mfa_enforced",
        "compliance_backend.services.control_rules.builtin.password_policy",
        "compliance_backend.services.control_rules.builtin.encryption_at_rest",
        "compliance_backend.services.control_rules.builtin.audit_logging_enabled",
        "compliance_backend.services.control_rules.builtin.access_review_completed",
        "compliance_backend.services.control_rules.builtin.incident_response_plan",
        "compliance_backend.services.control_rules.builtin.backup_configured",
        "compliance_backend.services.control_rules.builtin.vulnerability_scanning",
        "compliance_backend.services.control_rules.builtin.vendor_risk_review",
        "compliance_backend.services.control_rules.builtin.security_training_completed",
    ]
    for module_path in builtin_modules:
        try:
            importlib.import_module(module_path)
        except ImportError as exc:
            logger.error("Failed to load builtin rule module %s: %s", module_path, exc)
