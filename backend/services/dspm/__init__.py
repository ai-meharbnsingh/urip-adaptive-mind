"""DSPM service package — Project_33a §13 LIVE (MVP scaffold)."""
from backend.services.dspm.scan_service import (
    create_data_asset,
    list_data_assets,
    list_sensitive_discoveries,
    list_access_paths,
    record_sensitive_discovery,
    record_access_path,
    ingest_from_cloud_assets,
    SCAN_SOURCE_CSPM,
    SCAN_SOURCE_COLLAB,
)

__all__ = [
    "create_data_asset",
    "list_data_assets",
    "list_sensitive_discoveries",
    "list_access_paths",
    "record_sensitive_discovery",
    "record_access_path",
    "ingest_from_cloud_assets",
    "SCAN_SOURCE_CSPM",
    "SCAN_SOURCE_COLLAB",
]
