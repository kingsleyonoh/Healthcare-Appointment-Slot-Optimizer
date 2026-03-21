"""API key authentication dependency.

Usage in a router::

    verify = create_api_key_dependency(settings.api_keys_list)

    @router.get("/protected")
    async def protected(key=Depends(verify)):
        ...
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from fastapi.responses import JSONResponse


def create_api_key_dependency(valid_keys: list[str]):
    """Return a FastAPI dependency that validates ``X-API-Key``.

    Args:
        valid_keys: Allowed API keys.
    """

    async def _verify_api_key(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> str:
        if x_api_key is None or x_api_key not in valid_keys:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid or missing API key",
                        "details": [],
                    }
                },
            )
        return x_api_key

    return Depends(_verify_api_key)
