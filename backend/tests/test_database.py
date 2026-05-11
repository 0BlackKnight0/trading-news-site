# backend/tests/test_database.py
import os
os.environ["SUPABASE_URL"] = "http://fake.supabase.co"
# Supabase client validates key as JWT format — use a minimal valid-format token
os.environ["SUPABASE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmYWtlIn0.fake_signature"

import database
from database import get_client

def test_get_client_returns_client():
    database._client = None  # reset singleton so env vars above take effect
    client = get_client()
    assert client is not None
