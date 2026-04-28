"""
CSPM rule registry.

Usage:
    from backend.services.cspm_rules import register_cspm_rule, get_cspm_rule, list_cspm_rules

    @register_cspm_rule("check_root_mfa_enabled")
    def check_root_mfa_enabled(connector_data: dict) -> CspmRuleResult:
        ...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class CspmRuleResult:
    """Result of a single CSPM rule evaluation."""
    status: str  # pass | fail | inconclusive
    evidence: dict[str, Any] = field(default_factory=dict)
    failing_resource_ids: list[str] = field(default_factory=list)


# Global rule registry: name -> callable
_cspm_rules: dict[str, Callable[[dict], CspmRuleResult]] = {}


def register_cspm_rule(name: str) -> Callable:
    """Decorator to register a CSPM rule function."""
    def decorator(func: Callable[[dict], CspmRuleResult]) -> Callable[[dict], CspmRuleResult]:
        _cspm_rules[name] = func
        return func
    return decorator


def get_cspm_rule(name: str) -> Callable[[dict], CspmRuleResult] | None:
    """Lookup a rule by name."""
    return _cspm_rules.get(name)


def list_cspm_rules() -> list[str]:
    """List all registered rule names."""
    return sorted(_cspm_rules.keys())
