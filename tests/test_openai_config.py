from cognitive_os.core.config import Settings


def test_openai_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    settings = Settings(_env_file=None)
    assert settings.openai_api_key.get_secret_value() == "test-only-not-a-real-key"
    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.openai_base_url == "https://api.openai.com/v1"
    assert "test-only-not-a-real-key" not in repr(settings)
    assert "test-only-not-a-real-key" not in settings.model_dump_json()


def test_openai_key_is_optional(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert Settings(_env_file=None).openai_api_key is None
