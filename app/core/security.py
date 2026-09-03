from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from app.core.config import settings

OPS_TOKEN_HEADER = APIKeyHeader(name="X-Ops-Token", auto_error=False)


async def verify_ops_token(api_key: str = Security(OPS_TOKEN_HEADER)) -> str:
    """
    Phase 1 Ops authentication: checks for static shared secret in X-Ops-Token header.
    Can be upgraded to full JWT / OAuth2 once user accounts are introduced.
    """
    if not api_key or api_key != settings.OPS_AUTH_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Ops authentication token (X-Ops-Token header required).",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
