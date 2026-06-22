from fastapi.testclient import TestClient


def test_llm_connection_api_returns_success(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    async def fake_test_llm_connection(**kwargs):
        assert kwargs["api_key"] == "test-key"
        assert kwargs["base_url"] == "https://example.com/v1"
        assert kwargs["model"] == "gpt-test"
        return "https://example.com/v1", "gpt-test"

    monkeypatch.setattr("app.api.routes.llm.test_llm_connection", fake_test_llm_connection)

    response = client.post(
        "/llm/test-connection",
        json={
            "provider_type": "openai_compatible",
            "api_key": "test-key",
            "base_url": "https://example.com/v1",
            "model": "gpt-test",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["provider_type"] == "openai_compatible"
    assert data["base_url"] == "https://example.com/v1"
    assert data["model"] == "gpt-test"


def test_llm_connection_api_returns_502_when_provider_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    from app.services.llm import LLMConnectionTestError

    async def fake_test_llm_connection(**kwargs):
        raise LLMConnectionTestError("boom")

    monkeypatch.setattr("app.api.routes.llm.test_llm_connection", fake_test_llm_connection)

    response = client.post(
        "/llm/test-connection",
        json={
            "provider_type": "openai_compatible",
            "api_key": "test-key",
            "base_url": "https://example.com/v1",
            "model": "gpt-test",
        },
        headers=auth_headers,
    )

    assert response.status_code == 502
