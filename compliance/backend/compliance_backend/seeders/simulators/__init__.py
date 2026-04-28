"""
Compliance demo data simulators.

This sub-package generates realistic synthetic activity data for a tenant
so every screen has data and every workflow can be exercised end-to-end
during demos and integration tests.

Architectural pattern (mirrors connectors/extended_simulator.py):
  - Each simulator is a standalone module exposing one or more
    `simulate_*` async functions that accept a session + tenant_id +
    deterministic seed.
  - Simulators are tenant-scoped (never write data for "all tenants").
  - Simulators are idempotent (re-running does not duplicate records).
  - Simulators write realistic data — no "test_X" placeholders.

Simulator manifest:
  control_run_simulator     — ControlCheckRun history (90 days, pass/fail mix)
  policy_ack_simulator      — PolicyAcknowledgment records (~85% coverage)
  vendor_response_simulator — VendorQuestionnaire responses + VendorRiskScore + VendorDocument
  evidence_simulator        — Evidence + actual placeholder files in storage
  incident_simulator        — Incident records with realistic lifecycles
  asset_simulator           — Asset inventory (laptops, servers, cloud)
  access_review_simulator   — Quarterly access review campaigns + decisions
  auditor_activity_simulator— Auditor sessions + access-pattern logs
  compliance_score_simulator— ComplianceScoreSnapshot (90-day trend)

Master orchestrator:
  run_simulators            — CLI entry: runs all 10 in dependency order
"""
