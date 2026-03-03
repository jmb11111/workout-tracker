"""
User profile endpoints.

Provides read and update access to the authenticated user's profile
and preferences. No password management (OIDC only).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.oidc import get_current_user
from app.core.database import get_db
from app.models.user import User, WeightUnit
from app.api.schemas import UserResponse, UserUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
):
    """
    Get the current authenticated user's profile, including
    display name, email, weight_unit preference, and dark_mode setting.
    """
    return UserResponse.model_validate(user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update the current user's preferences.

    Supported fields:
    - weight_unit: "lbs" or "kg"
    - dark_mode: true or false
    """
    if payload.weight_unit is not None:
        try:
            user.weight_unit = WeightUnit(payload.weight_unit)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid weight_unit: {payload.weight_unit}. Must be 'lbs' or 'kg'.",
            )

    if payload.dark_mode is not None:
        user.dark_mode = payload.dark_mode

    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)
