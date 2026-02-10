"""JWT validation matching Open Testimony's auth (same secret + algorithm)."""
from fastapi import HTTPException, Request
from jose import JWTError, jwt

from config import settings


def get_current_user(request: Request) -> dict:
    """Validate JWT from cookie and return decoded payload.

    The bridge doesn't query the users table — it only validates the token
    signature so that unauthenticated requests are rejected.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_auth(request: Request) -> dict:
    """Dependency alias for endpoints that require authentication."""
    return get_current_user(request)
