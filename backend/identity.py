# backend/identity.py
"""Device-key identity.

A key generated in the browser and kept in localStorage, exchanged for a
`users` row on first contact. This is deliberately not authentication —
anyone holding the key is that user — but it replaces the current build's
single global watchlist that any visitor can edit.

Keys must be long enough not to be guessable; a UUID v4 satisfies this.
"""
from fastapi import Header, HTTPException

from database import get_or_create_user

MIN_KEY_LENGTH = 32


def current_user(x_device_key: str | None = Header(default=None)) -> dict:
    if not x_device_key or len(x_device_key.strip()) < MIN_KEY_LENGTH:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Device-Key")
    return get_or_create_user(x_device_key.strip())
