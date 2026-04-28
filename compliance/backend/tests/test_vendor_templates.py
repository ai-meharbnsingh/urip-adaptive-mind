"""
TDD — vendor questionnaire templates (P2B.7.3).

Verifies:
  - All 3 templates load
  - Structural validity for each question
"""
from __future__ import annotations

import pytest

from compliance_backend.seeders.vendor_templates import get_vendor_questionnaire_templates


@pytest.mark.anyio
async def test_vendor_templates_load_all_three():
    templates = get_vendor_questionnaire_templates()
    assert isinstance(templates, dict)
    assert "SOC 2 Vendor Questionnaire" in templates
    assert "GDPR Data Processor Questionnaire" in templates
    assert "Security Baseline Questionnaire" in templates


@pytest.mark.anyio
async def test_vendor_templates_structure_is_valid():
    templates = get_vendor_questionnaire_templates()
    for template_name, template in templates.items():
        assert template["name"] == template_name
        questions = template["questions"]
        assert isinstance(questions, list)
        assert len(questions) >= 10
        for q in questions:
            assert "id" in q and isinstance(q["id"], str) and q["id"]
            assert "text" in q and isinstance(q["text"], str) and q["text"]
            assert q["answer_type"] in ("yes_no", "text", "scale_1_5")
            assert isinstance(q["required"], bool)

