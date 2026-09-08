"""
FlowMind AI - Authentication & Identity Resolution (Phase 3)
Resolves user identities server-side from bearer session tokens.
CRITICAL TRUST BOUNDARY: Client request bodies can NEVER specify or override
their own roles. Role validation is always performed against the resolved UserContext.
"""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.security.models import PRECONFIGURED_PERSONAS, UserContext, UserRole

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)


def resolve_user_from_token(token: Optional[str]) -> Optional[UserContext]:
    """
    Server-side lookup mapping bearer session tokens to authenticated UserContext.
    """
    if not token:
        return None
    # Strip any leading 'Bearer ' if present
    cleaned_token = token.strip()
    if cleaned_token.lower().startswith("bearer "):
        cleaned_token = cleaned_token[7:].strip()

    return PRECONFIGURED_PERSONAS.get(cleaned_token)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    x_user_token: Optional[str] = Header(None, alias="X-User-Token"),
) -> UserContext:
    """
    FastAPI dependency for authenticating requests.
    Inspects standard Authorization Bearer header, falling back to X-User-Token header.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif x_user_token:
        token = x_user_token

    user = resolve_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_default_agent_user() -> UserContext:
    """Convenience helper for automated evaluation and offline tasks."""
    return PRECONFIGURED_PERSONAS["flowmind-agent-token-001"]


def get_persona_by_role(role: UserRole) -> UserContext:
    """Retrieve preconfigured persona by role enum."""
    for persona in PRECONFIGURED_PERSONAS.values():
        if persona.role == role:
            return persona
    raise ValueError(f"No preconfigured persona found for role: {role}")
