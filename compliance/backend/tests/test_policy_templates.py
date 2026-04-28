"""
TDD — Policy template seeder tests.

Tests written BEFORE seeder implementation.
Ensures all 9 templates load and contain realistic markdown content.
"""
import pytest

from compliance_backend.seeders.policy_templates import (
    get_policy_templates,
    get_template_by_name,
    POLICY_TEMPLATES,
)


EXPECTED_TEMPLATES = [
    "Information Security Policy",
    "Acceptable Use Policy",
    "Business Continuity and Disaster Recovery Policy",
    "Incident Response Policy",
    "Access Control Policy",
    "Change Management Policy",
    "Vendor Management Policy",
    "Data Classification Policy",
    "Privacy Policy",
]


def test_all_nine_templates_present():
    """The seeder exposes exactly 9 policy templates."""
    templates = get_policy_templates()
    assert len(templates) == 9
    names = [t["name"] for t in templates]
    for expected in EXPECTED_TEMPLATES:
        assert expected in names, f"Missing template: {expected}"


def test_each_template_has_non_empty_markdown():
    """Every template has content that looks like markdown."""
    for template in POLICY_TEMPLATES:
        content = template["content"]
        assert content, f"Template '{template['name']}' has empty content"
        assert "# " in content, f"Template '{template['name']}' missing markdown headers"
        assert len(content.split()) >= 50, (
            f"Template '{template['name']}' seems too short (< 50 words)"
        )


def test_get_template_by_name_exact_match():
    """get_template_by_name returns the correct template."""
    tmpl = get_template_by_name("Privacy Policy")
    assert tmpl is not None
    assert tmpl["name"] == "Privacy Policy"
    assert "data subject" in tmpl["content"].lower()


def test_get_template_by_name_missing_returns_none():
    """get_template_by_name returns None for unknown names."""
    assert get_template_by_name("Nonexistent Policy XYZ") is None
