"""Lightweight dataclasses for OnGrid API responses."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OnGridCheck:
    id: str
    candidate_email: str
    candidate_name: str
    verification_status: str  # pending | verified | rejected
    checks_completed: List[str] = field(default_factory=list)
    checks_remaining: List[str] = field(default_factory=list)
    rejection_reason: Optional[str] = None
