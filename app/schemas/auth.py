"""
schemas.auth
=============
Pydantic schemas for signup, login, and role upgrade requests.
"""

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name of the user")
    email: str = Field(..., max_length=255, description="Unique email address")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    confirm_password: str = Field(..., min_length=6, description="Password confirmation")


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(...)


class AdminUpgradeRequest(BaseModel):
    admin_secret: str = Field(..., description="Secret key to verify admin privileges")
