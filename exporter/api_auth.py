"""api_auth.py — JWT authentication for the Fleet Health API.

In production:
  - Replace SECRET_KEY with a secret fetched from AWS Secrets Manager
  - Replace FAKE_CLIENTS with a DynamoDB / RDS lookup
  - Use short-lived tokens (15 min) and a refresh-token pattern
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-ops-platform")
ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "30"))

# Simulated client store — replace with DB lookup in production
FAKE_CLIENTS: dict[str, str] = {
    "grafana-agent": "grafana-secret",
    "alertmanager": "am-secret",
    "ops-dashboard": "dashboard-secret",
}

bearer_scheme = HTTPBearer(auto_error=True)


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=TOKEN_TTL_MINUTES)
    )
    return jwt.encode(
        {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_client(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency — validates Bearer JWT, returns client_id."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: str = payload.get("sub", "")
        if not client_id:
            raise JWTError("missing sub")
        return client_id
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
