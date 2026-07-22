"""JWT protections for the Platform Dashboard APIs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from sentinelai_platform.api import create_app


class _Repository:
    async def count(self, **_kwargs: object) -> int:
        return 0

    async def list(self, **_kwargs: object) -> list[object]:
        return []


def _client() -> TestClient:
    app = create_app()
    app.state.execution_repository = _Repository()
    return TestClient(app)


def test_protected_route_requires_bearer_token_when_secret_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-signing-secret-at-least-thirty-two-bytes")
    monkeypatch.delenv("SENTINELAI_AUTH_DISABLED", raising=False)

    response = _client().get("/api/v1/executions")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_protected_route_accepts_valid_supabase_hs256_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "test-signing-secret-at-least-thirty-two-bytes"
    issuer = "https://project-ref.supabase.co/auth/v1"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    monkeypatch.setenv("SUPABASE_URL", "https://project-ref.supabase.co")
    token = jwt.encode(
        {
            "sub": "user-123",
            "role": "authenticated",
            "iss": issuer,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )

    response = _client().get(
        "/api/v1/executions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
