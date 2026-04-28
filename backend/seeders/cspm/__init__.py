"""
CSPM CIS Benchmark seeders.

Usage:
    from backend.seeders.cspm import run_all
    await run_all.seed_all(session)
"""

from backend.seeders.cspm.cis_aws_v2 import seed_cis_aws_v2
from backend.seeders.cspm.cis_azure_v2 import seed_cis_azure_v2
from backend.seeders.cspm.cis_gcp_v3 import seed_cis_gcp_v3

__all__ = ["seed_cis_aws_v2", "seed_cis_azure_v2", "seed_cis_gcp_v3"]
