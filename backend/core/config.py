"""Typed configuration for TerraMind.

The YAML file is read once and validated by Pydantic, so a typo or a missing
key fails at startup with a clear message instead of deep inside the pipeline.
"""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# backend/core/config.py -> project root is two levels above this file's folder.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = "configs/nlp.yaml"

LanguageCode = Literal["en", "hi", "ne"]


class _Strict(BaseModel):
    # extra="forbid" turns a misspelled key in the YAML into an error.
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectConfig(_Strict):
    name: str
    region: str
    seed: int


class LanguagesConfig(_Strict):
    supported: list[LanguageCode] = Field(min_length=1)


class InputConfig(_Strict):
    max_query_chars: int = Field(gt=0)


class PathsConfig(_Strict):
    data_dir: Path
    models_dir: Path
    ontology_dir: Path


class Settings(_Strict):
    project: ProjectConfig
    languages: LanguagesConfig
    input: InputConfig
    paths: PathsConfig


class ConfigError(Exception):
    """Raised when the config file is missing or invalid."""


def _resolve(path: Path) -> Path:
    """Make a config path absolute, anchored at the project root."""
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load and validate settings.

    Order of precedence: explicit argument, TERRAMIND_CONFIG environment
    variable, then the default configs/nlp.yaml.
    """
    chosen = config_path or os.environ.get("TERRAMIND_CONFIG") or DEFAULT_CONFIG
    path = _resolve(Path(chosen))

    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError(f"Config file is empty or not a mapping: {path}")

    try:
        settings = Settings.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"Invalid config in {path}:\n{e}") from e

    resolved_paths = PathsConfig(
        data_dir=_resolve(settings.paths.data_dir),
        models_dir=_resolve(settings.paths.models_dir),
        ontology_dir=_resolve(settings.paths.ontology_dir),
    )
    return settings.model_copy(update={"paths": resolved_paths})
