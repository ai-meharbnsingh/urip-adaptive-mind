"""Lightweight dataclasses for Hoxhunt API responses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HoxhuntUser:
    id: str
    email: str
    training_status: str  # "active" | "inactive" | "paused"
    behaviour_score: float
    last_engaged_at: Optional[str] = None


@dataclass
class HoxhuntSimulation:
    id: str
    user_email: str
    outcome: str  # "clicked" | "reported" | "ignored"
    campaign: Optional[str] = None
    delivered_at: Optional[str] = None
