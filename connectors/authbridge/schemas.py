"""Lightweight dataclasses for AuthBridge API responses."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Verification:
    id: str
    employee_email: str
    employee_name: str
    status: str  # initiated | in_progress | completed | failed
    checks_done: List[str] = field(default_factory=list)
    checks_pending: List[str] = field(default_factory=list)
    initiated_at: Optional[str] = None
    completed_at: Optional[str] = None
