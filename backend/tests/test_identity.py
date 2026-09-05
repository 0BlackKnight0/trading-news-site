# backend/tests/test_identity.py
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from identity import MIN_KEY_LENGTH, current_user

VALID_KEY = "d" * MIN_KEY_LENGTH


def test_missing_device_key_is_rejected():
    with pytest.raises(HTTPException) as err:
        current_user(None)
    assert err.value.status_code == 401


def test_short_device_key_is_rejected():
    """A guessable key would let anyone assume another user's identity."""
    with pytest.raises(HTTPException) as err:
        current_user("abc")
    assert err.value.status_code == 401


def test_valid_device_key_resolves_to_a_user():
    with patch("identity.get_or_create_user", return_value={"id": "u1"}) as lookup:
        user = current_user(VALID_KEY)
    assert user["id"] == "u1"
    lookup.assert_called_once_with(VALID_KEY)
