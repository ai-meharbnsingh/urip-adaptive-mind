from backend.models.tenant import Tenant  # must be first — others FK into tenants
from backend.models.user import User
from backend.models.risk import Risk, RiskHistory
from backend.models.acceptance import AcceptanceRequest
from backend.models.remediation import RemediationTask
from backend.models.connector import ConnectorConfig
from backend.models.audit_log import AuditLog
from backend.models.tenant_connector_credential import TenantConnectorCredential  # P1.6
from backend.models.asset_taxonomy import TenantAssetTaxonomy  # P1.4
from backend.models.asset import Asset  # P33a — first-class asset model
# Phase 4 — Hybrid-SaaS agent ingest
from backend.models.agent_ingest import (
    AgentRegistration,
    ConnectorHealthSummary,
    DrilldownRequest,
    RiskScoreSummary,
)
# P33a — VAPT Vendor Portal
from backend.models.vapt_vendor import (
    VaptSubmission,
    VaptVendor,
    VaptVendorInvitation,
)
# Project_33a Roadmap-2 — Trust Center
from backend.models.trust_center import (
    TrustCenterAccessRequest,
    TrustCenterDocument,
)
# Project_33a Roadmap-3 — Auto-Remediation execution log
from backend.models.auto_remediation import (
    AutoRemediationExecution,
)
# Project_33a §13 — promoted ROADMAP → LIVE (MVP scaffold) modules
from backend.models.dspm import (
    DataAccessPath,
    DataAsset,
    SensitiveDataDiscovery,
)
from backend.models.ai_security import (
    AIModel,
    GovernanceAssessment,
    PromptInjectionEvent,
)
from backend.models.ztna import (
    ZTNAAccessDecision,
    ZTNAPolicy,
    ZTNAPostureViolation,
)
from backend.models.attack_path import (
    AttackPath,
    AttackPathEdge,
    AttackPathNode,
)
from backend.models.risk_quantification import (
    FAIRAssumptions,
    FAIRRiskAssessment,
)

__all__ = [
    "Tenant",
    "User",
    "Risk",
    "RiskHistory",
    "AcceptanceRequest",
    "RemediationTask",
    "ConnectorConfig",
    "AuditLog",
    "TenantConnectorCredential",
    "TenantAssetTaxonomy",
    "Asset",
    "AgentRegistration",
    "RiskScoreSummary",
    "ConnectorHealthSummary",
    "DrilldownRequest",
    "VaptVendor",
    "VaptVendorInvitation",
    "VaptSubmission",
    "TrustCenterDocument",
    "TrustCenterAccessRequest",
    "AutoRemediationExecution",
    # Project_33a §13 LIVE (MVP scaffold)
    "DataAsset",
    "SensitiveDataDiscovery",
    "DataAccessPath",
    "AIModel",
    "PromptInjectionEvent",
    "GovernanceAssessment",
    "ZTNAPolicy",
    "ZTNAAccessDecision",
    "ZTNAPostureViolation",
    "AttackPathNode",
    "AttackPathEdge",
    "AttackPath",
    "FAIRAssumptions",
    "FAIRRiskAssessment",
]
