"""Risk Quantification service — Project_33a §13 LIVE (MVP scaffold)."""
from backend.services.risk_quantification.fair_engine import (
    DEFAULT_ASSUMPTIONS,
    compute_loss_magnitude,
    compute_ale,
    upsert_assumptions,
    get_assumptions,
    record_assessment,
    list_assessments,
    aggregate,
    get_assessment_by_risk_id,
)

__all__ = [
    "DEFAULT_ASSUMPTIONS",
    "compute_loss_magnitude",
    "compute_ale",
    "upsert_assumptions",
    "get_assumptions",
    "record_assessment",
    "list_assessments",
    "aggregate",
    "get_assessment_by_risk_id",
]
