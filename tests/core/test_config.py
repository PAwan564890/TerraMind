import pytest

from backend.core.config import PROJECT_ROOT, ConfigError, load_settings


def test_default_config_loads():
    settings = load_settings()
    assert settings.project.name == "TerraMind"
    assert settings.languages.supported == ["en", "hi", "ne"]
    assert settings.input.max_query_chars > 0


def test_paths_are_resolved_against_project_root():
    settings = load_settings()
    assert settings.paths.models_dir.is_absolute()
    assert settings.paths.models_dir == PROJECT_ROOT / "models"


def test_missing_file_raises_config_error():
    with pytest.raises(ConfigError, match="not found"):
        load_settings("configs/does_not_exist.yaml")


def test_unknown_key_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "project: {name: T, region: S, seed: 1}\n"
        "languages: {supported: [en]}\n"
        "input: {max_query_chars: 10, typo_key: 1}\n"
        "paths: {data_dir: d, models_dir: m, ontology_dir: o}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="typo_key"):
        load_settings(bad)


def test_unsupported_language_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "project: {name: T, region: S, seed: 1}\n"
        "languages: {supported: [en, fr]}\n"
        "input: {max_query_chars: 10}\n"
        "paths: {data_dir: d, models_dir: m, ontology_dir: o}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_settings(bad)


def test_env_var_selects_config(tmp_path, monkeypatch):
    alt = tmp_path / "alt.yaml"
    alt.write_text(
        "project: {name: Alt, region: S, seed: 7}\n"
        "languages: {supported: [ne]}\n"
        "input: {max_query_chars: 10}\n"
        "paths: {data_dir: d, models_dir: m, ontology_dir: o}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TERRAMIND_CONFIG", str(alt))
    assert load_settings().project.name == "Alt"
