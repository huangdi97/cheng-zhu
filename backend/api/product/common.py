"""Shared error mapping for the v1.3 product API."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from fastapi import HTTPException


@contextmanager
def domain_errors() -> Iterator[None]:
    """Domain ValueErrors become 4xx with the user-facing message.

    "…不存在" → 404, a concurrent-edit conflict → 409 with the current row,
    anything else → 400. Unexpected exceptions propagate as 500.
    """
    try:
        yield
    except HTTPException:
        raise
    except ValueError as exc:
        current = getattr(exc, "current", None)
        if current is not None:
            raise HTTPException(status_code=409, detail={"message": str(exc), "current": current}) from None
        message = str(exc)
        status = 404 if "不存在" in message else 400
        raise HTTPException(status_code=status, detail=message) from None
