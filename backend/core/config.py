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


class DatasetConfig(_Strict):
    # How many filled sentences to draw from each template.
    fills_per_template: int = Field(default=12, gt=0)
    # Fractions of template FAMILIES (not rows) held out per intent.
    val_fraction: float = Field(default=0.15, gt=0, lt=0.5)
    test_fraction: float = Field(default=0.15, gt=0, lt=0.5)
    # In the test split, chance that a location slot takes a held-out place.
    heldout_location_rate: float = Field(default=0.5, ge=0, le=1)
    # Light noise: lowercase an English query / drop the final punctuation.
    lowercase_rate: float = Field(default=0.15, ge=0, le=1)
    drop_punctuation_rate: float = Field(default=0.2, ge=0, le=1)


class LanguageDetectionConfig(_Strict):
    # Character n-gram sizes for the Hindi-versus-Nepali classifier.
    ngram_min: int = Field(default=1, gt=0)
    ngram_max: int = Field(default=3, gt=0)
    # Short random word windows added per training row, to cover fragments.
    fragments_per_row: int = Field(default=2, ge=0)
    # Below this confidence the conversation's previous language is preferred.
    min_confidence: float = Field(default=0.6, ge=0.5, le=1)


class EncoderTrainingConfig(_Strict):
    """Fine-tuning settings shared by the intent classifier and the NER model.
    The values are sensible starting points, not tuned optima."""

    # Final model, fine-tuned on a GPU.
    model_name: str = "xlm-roberta-base"
    # Small model with the same kind of tokenizer, for CPU development runs.
    dev_model_name: str = "intfloat/multilingual-e5-small"
    # Which trained run the pipeline loads: a folder name under models/<task>/.
    active_run: str = "dev"
    max_length: int = Field(default=64, gt=0)
    batch_size: int = Field(default=16, gt=0)
    learning_rate: float = Field(default=2e-5, gt=0)
    weight_decay: float = Field(default=0.01, ge=0)
    warmup_ratio: float = Field(default=0.1, ge=0, lt=1)
    max_epochs: int = Field(default=10, gt=0)
    # Stop after this many epochs without a better validation score.
    patience: int = Field(default=2, gt=0)
    max_grad_norm: float = Field(default=1.0, gt=0)
    seeds: list[int] = Field(default=[42, 43, 44], min_length=1)


class IntentConfig(EncoderTrainingConfig):
    class_weighting: bool = False


class NerConfig(EncoderTrainingConfig):
    learning_rate: float = Field(default=3e-5, gt=0)


class NormalizationConfig(_Strict):
    # Minimum character similarity (0-1) for a fuzzy alias match.
    fuzzy_threshold: float = Field(default=0.85, gt=0.5, le=1)
    # Shorter strings are too easy to confuse and are never fuzzy-matched.
    fuzzy_min_chars: int = Field(default=4, gt=0)
    # The best match must beat the runner-up by at least this much.
    fuzzy_margin: float = Field(default=0.03, ge=0)


class EmbeddingCandidate(_Strict):
    name: str
    # Text put in front of every input. The E5 models expect "query: ".
    prefix: str = ""


class EmbeddingsConfig(_Strict):
    # The model the pipeline uses.
    model_name: str = "intfloat/multilingual-e5-small"
    prefix: str = "query: "
    # Models compared by scripts/evaluate_embeddings.py.
    candidates: list[EmbeddingCandidate] = Field(default_factory=lambda: [
        EmbeddingCandidate(name="intfloat/multilingual-e5-small", prefix="query: "),
        EmbeddingCandidate(name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
    ])
    max_length: int = Field(default=64, gt=0)
    batch_size: int = Field(default=32, gt=0)
    # Neighbours averaged for the domain-similarity score and the kNN vote.
    neighbours: int = Field(default=5, gt=0)
    # Parallel triples generated for the cross-language retrieval test.
    parallel_triples: int = Field(default=150, gt=0)
    # Embedding fallback in normalisation: minimum cosine similarity to an
    # alias, and minimum lead over the second-best concept.
    alias_threshold: float = Field(default=0.9, gt=0, le=1)
    alias_margin: float = Field(default=0.01, ge=0)


class ContextConfig(_Strict):
    # A stored slot can be inherited for this many turns after it was last stated.
    max_slot_age_turns: int = Field(default=5, gt=0)
    # A conversation is forgotten after this long without a message.
    max_idle_seconds: int = Field(default=1800, gt=0)
    # Upper bound on conversations held in memory; the least recent is dropped.
    max_sessions: int = Field(default=1000, gt=0)


class PipelineConfig(_Strict):
    # Resolve unknown variable/disaster words by embedding similarity. Off by
    # default: in evaluation it recovered about 30% of synonyms and mapped 4%
    # to the wrong concept. Adding synonyms to the ontology is more reliable.
    use_embedding_fallback: bool = False


class DecisionConfig(_Strict):
    """Targets from which scripts/select_thresholds.py derives the thresholds.
    The thresholds themselves depend on the trained models, so they are saved
    next to the models (models/decision/thresholds.json), not here."""

    # Among queries the pipeline answers without asking, at most this share
    # may have the wrong intent (measured on validation data).
    target_answered_error: float = Field(default=0.05, gt=0, lt=1)
    # The target is applied to an UPPER BOUND of that error rate, not to the
    # rate itself. Validation rows come from a few template families and a
    # whole family tends to be right or wrong together, so the plain rate is
    # far less certain than its row count suggests. The bound is this quantile
    # of the error rate over resamples of whole families.
    error_bound_quantile: float = Field(default=0.9, gt=0.5, lt=1)
    bootstrap_resamples: int = Field(default=1000, gt=0)
    # At most this share of genuine in-domain queries may be rejected by the
    # embedding-similarity check.
    in_domain_rejection_target: float = Field(default=0.02, gt=0, lt=1)
    # When the classifier says "off-topic" but the query is as close to known
    # in-domain queries as almost no off-topic query ever is, the two signals
    # disagree and the user is asked instead. This is the share of off-topic
    # validation queries allowed to be that close.
    ood_veto_target: float = Field(default=0.05, gt=0, lt=1)
    # A trend question with no time span gets this many past years.
    default_trend_years: int = Field(default=10, gt=0)
    # Scenario changes beyond these are treated as typing mistakes.
    max_percent_change: float = Field(default=500, gt=0)
    max_absolute_change: float = Field(default=20, gt=0)


class Settings(_Strict):
    project: ProjectConfig
    languages: LanguagesConfig
    input: InputConfig
    paths: PathsConfig
    dataset: DatasetConfig = DatasetConfig()
    language_detection: LanguageDetectionConfig = LanguageDetectionConfig()
    intent: IntentConfig = IntentConfig()
    ner: NerConfig = NerConfig()
    normalization: NormalizationConfig = NormalizationConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    context: ContextConfig = ContextConfig()
    pipeline: PipelineConfig = PipelineConfig()
    decision: DecisionConfig = DecisionConfig()


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
