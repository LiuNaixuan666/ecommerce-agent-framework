from app.config import Settings


def test_settings_reads_existing_environment_variable_names(monkeypatch):
    monkeypatch.setenv("SESSION_STORAGE", "hybrid")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("POSTGRES_PORT", "5544")

    settings = Settings(_env_file=None)

    assert settings.session_storage == "hybrid"
    assert settings.llm_provider == "gemini"
    assert settings.postgres_port == 5544

