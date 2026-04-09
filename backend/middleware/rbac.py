from fastapi import Depends, HTTPException, status

from backend.middleware.auth import get_current_user
from backend.models.user import User

ROLE_HIERARCHY = {
    "board": 0,
    "executive": 1,
    "it_team": 2,
    "ciso": 3,
}


def role_required(min_role: str):
    min_level = ROLE_HIERARCHY.get(min_role, 0)

    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' insufficient. Requires '{min_role}' or higher.",
            )
        return current_user

    return check_role
