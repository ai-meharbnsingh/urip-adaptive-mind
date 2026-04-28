"""
URIP-side demo data simulators.

Companion package to compliance_backend.seeders.simulators — these populate
URIP-side data (tenant connector credentials, audit log activity) so the
demo tenant has a "rich state" across both sides of the platform.

Modules:
  connector_credential_simulator — seed encrypted dummy credentials so the
                                    tenant appears "configured" for each connector.
  audit_log_activity_simulator   — synthetic user activity (logins,
                                    risk acceptances, comments).
"""
