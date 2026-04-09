import uuid

from fastapi import HTTPException


def parse_uuid(value: str, field_name: str = "id") -> uuid.UUID:
    """Parse a UUID string, returning 400 on invalid format."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")
