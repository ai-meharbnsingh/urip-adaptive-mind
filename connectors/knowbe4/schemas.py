"""
Schema dataclasses for KnowBe4 API responses.

Kept lightweight — connector.normalize() does the heavy lifting; these
dataclasses are mostly documentation + a sanity-check shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TrainingEnrollment:
    id: str
    user_email: str
    module_name: str
    status: str  # "in_progress" | "completed" | "past_due" | "not_started"
    enrollment_date: Optional[str] = None
    due_date: Optional[str] = None
    completion_date: Optional[str] = None


@dataclass
class PhishingRecipient:
    id: str
    user_email: str
    campaign_name: str
    clicked: bool
    reported: bool
    delivered_at: Optional[str] = None
