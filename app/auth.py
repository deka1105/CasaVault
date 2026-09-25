import logging
from typing import Optional

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions, AuthStatus
from fastapi import HTTPException, Request

from app.config import CLERK_SECRET_KEY

logger = logging.getLogger(__name__)


async def get_optional_user_id(request: Request) -> Optional[str]:
    """Returns the Clerk user id (JWT `sub` claim) if the request carries a
    valid session token, else None. Never raises — sign-in is optional
    everywhere this is used; anonymous vault-id/share-token access (the
    original design) keeps working completely unchanged whether or not
    Clerk is configured or the caller is signed in."""
    if not CLERK_SECRET_KEY or "authorization" not in request.headers:
        return None

    try:
        # async with: a fresh Clerk() per call left its underlying HTTP
        # client open with nothing to close it — a real leak risk on a warm,
        # reused Fluid Compute instance handling many requests. Caught on
        # review, not by a test (nothing here would fail functionally on a
        # single request; it only compounds over many).
        async with Clerk(bearer_auth=CLERK_SECRET_KEY) as clerk:
            state = await clerk.authenticate_request_async(request, AuthenticateRequestOptions())
    except Exception:
        logger.exception("Clerk authentication check failed")
        return None

    if state.status != AuthStatus.SIGNED_IN or not state.payload:
        return None
    return state.payload.get("sub")


async def require_user_id(request: Request) -> str:
    """Use as a dependency on routes that must be signed in (e.g. listing
    'my vaults') — 401s rather than silently treating the caller as
    anonymous."""
    user_id = await get_optional_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="sign-in required")
    return user_id
