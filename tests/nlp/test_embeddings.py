"""Tests for the embedding code path.

A tiny random BERT stands in for the real encoder (no download). Its vectors
carry no meaning, so these tests check mechanics only: shapes, normalisation,
batching, the index arithmetic and the metrics. Quality is measured by
scripts/evaluate_embeddings.py with the real models.
"""

import random

import numpy as np
import pytest
import torch
from transformers import BertConfig, BertModel, BertTokenizerFast

from backend.core import load_settings
from backend.nlp.dataset.generator import build_pools, load_lexicon
from backend.nlp.dataset.records import read_jsonl
from backend.nlp.embeddings.alias_matcher import AliasMatcher
from backend.nlp.embeddings.encoder import EmbeddingModel
from backend.nlp.embeddings.index import NeighbourIndex
from backend.nlp.embeddings.parallel import make_parallel_set
from backend.nlp.evaluation.retrieval import retrieval_metrics, separation_metrics
from backend.nlp.normalization import EntityNormalizer
from backend.nlp.ontology import get_ontology
from backend.nlp.query.enums import EntityType, Language, Variable

SETTINGS = load_settings()
ONTOLOGY = get_ontology()


@pytest.fixture(scope="module")
def records():
    return read_jsonl(SETTINGS.paths.data_dir / "train.jsonl")[::20]


def make_model(tmp_path_factory, records, prefix=""):
    characters = sorted({ch for r in records for ch in r.text + prefix if not ch.isspace()})
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
    vocab += characters + [f"##{ch}" for ch in characters]
    path = tmp_path_factory.mktemp("vocab") / "vocab.txt"
    path.write_text("\n".join(vocab), encoding="utf-8")
    tokenizer = BertTokenizerFast(str(path), do_lower_case=False, strip_accents=False)
    torch.manual_seed(0)
    model = BertModel(BertConfig(
        vocab_size=len(tokenizer), hidden_size=32, num_hidden_layers=1,
        num_attention_heads=2, intermediate_size=64, max_position_embeddings=128,
    ))
    return EmbeddingModel(tokenizer, model, "tiny", prefix, 64, 4, torch.device("cpu"))


@pytest.fixture(scope="module")
def model(tmp_path_factory, records):
    return make_model(tmp_path_factory, records)


def test_vectors_are_unit_length(model, records):
    vectors = model.encode([r.text for r in records[:10]])
    assert vectors.shape == (10, 32)
    assert vectors.dtype == np.float32
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


def test_padding_does_not_change_a_vector(model):
    short, long = "rain", "What is the rainfall trend in Gangtok over the last five years?"
    alone = model.encode([short])[0]
    in_batch = model.encode([short, long])[0]  # padded to the long text's length
    assert np.allclose(alone, in_batch, atol=1e-5)


def test_empty_input(model):
    assert model.encode([]).shape == (0, 32)


def test_prefix_changes_the_input(tmp_path_factory, records):
    plain = make_model(tmp_path_factory, records, prefix="")
    prefixed = make_model(tmp_path_factory, records, prefix="query: ")
    assert not np.allclose(plain.encode(["rain"]), prefixed.encode(["rain"]))


# --- index (hand-made vectors, so the expected answers are known) -------------

def unit(*values):
    vector = np.array(values, dtype=np.float32)
    return vector / np.linalg.norm(vector)


@pytest.fixture
def index():
    vectors = np.stack([
        unit(1, 0, 0), unit(0.9, 0.1, 0),      # weather
        unit(0, 1, 0), unit(0.1, 0.9, 0),      # trend
        unit(0, 0, 1),                         # out of domain
    ])
    intents = ["WEATHER_QUERY", "WEATHER_QUERY", "CLIMATE_TREND", "CLIMATE_TREND",
               "OUT_OF_DOMAIN"]
    return NeighbourIndex(vectors, intents, ["a", "b", "c", "d", "e"], "tiny")


def test_domain_similarity_ignores_out_of_domain_rows(index):
    queries = np.stack([unit(1, 0, 0), unit(0, 0, 1)])
    near, far = index.domain_similarity(queries, k=2)
    assert near > 0.95
    # The query equals the stored OOD vector, but that row must not count.
    assert far < 0.1


def test_knn_intent_votes_by_similarity(index):
    queries = np.stack([unit(1, 0.05, 0), unit(0, 1, 0.05), unit(0, 0, 1)])
    assert index.knn_intent(queries, k=2) == ["WEATHER_QUERY", "CLIMATE_TREND", "OUT_OF_DOMAIN"]


def test_index_round_trip_and_model_check(index, tmp_path):
    path = tmp_path / "index.npz"
    index.save(path)
    loaded = NeighbourIndex.load(path, "tiny")
    assert np.array_equal(loaded.vectors, index.vectors)
    assert loaded.intents == index.intents
    with pytest.raises(ValueError, match="Rebuild"):
        NeighbourIndex.load(path, "some-other-model")


def test_index_build_uses_the_encoder(model, records):
    built = NeighbourIndex.build(model, records)
    assert built.vectors.shape == (len(records), 32)
    assert built.model_name == "tiny"


# --- metrics -------------------------------------------------------------------

def test_retrieval_metrics():
    similarities = np.array([
        [0.9, 0.1, 0.2],   # correct (0) ranked 1st
        [0.8, 0.5, 0.6],   # correct (1) ranked 3rd
        [0.1, 0.7, 0.6],   # correct (2) ranked 2nd
    ])
    metrics = retrieval_metrics(similarities, [0, 1, 2])
    assert metrics["recall_at_1"] == pytest.approx(1 / 3)
    assert metrics["recall_at_5"] == 1.0
    assert metrics["mrr"] == pytest.approx((1 + 1 / 3 + 1 / 2) / 3)


def test_separation_metrics():
    perfect = separation_metrics(np.array([0.9, 0.8, 0.95]), np.array([0.1, 0.2]))
    assert perfect["auroc"] == 1.0
    assert perfect["fpr_at_95_tpr"] == 0.0
    useless = separation_metrics(np.array([0.5, 0.5]), np.array([0.5, 0.5]))
    assert useless["auroc"] == 0.5


# --- parallel triples -----------------------------------------------------------

def test_parallel_triples_share_the_same_canonical_entities():
    pools = build_pools(ONTOLOGY, load_lexicon())
    triples = make_parallel_set(pools, 40, seed=1)
    assert len(triples) == 40
    assert len({t[Language.EN] for t in triples}) == 40

    def places(text):
        key_hits = set()
        for loc_id, entry in ONTOLOGY.locations.items():
            if any(alias.casefold() in text.casefold() for alias in entry.aliases.all()):
                key_hits.add(loc_id)
        return key_hits

    # Every place mentioned in the English version is mentioned in the others.
    for triple in triples:
        english = places(triple[Language.EN])
        assert english & places(triple[Language.HI]) or not english
        assert english & places(triple[Language.NE]) or not english


def test_parallel_set_is_deterministic():
    pools = build_pools(ONTOLOGY, load_lexicon())
    assert make_parallel_set(pools, 10, seed=3) == make_parallel_set(pools, 10, seed=3)
    assert random.Random(0).random() == random.Random(0).random()


# --- alias matcher and its hook in the normaliser -------------------------------

class FakeEncoder:
    """Returns hand-picked vectors so matches are predictable."""

    name = "fake"

    def __init__(self, special: dict[str, np.ndarray]):
        self._special = special

    def encode(self, texts):
        rows = []
        for i, text in enumerate(texts):
            if text in self._special:
                rows.append(self._special[text])
            else:
                # Every other text gets its own direction, far from the rest.
                vector = np.zeros(400, dtype=np.float32)
                vector[10 + (abs(hash(text)) % 380)] = 1.0
                rows.append(vector)
        return np.stack(rows)


def axis(i):
    vector = np.zeros(400, dtype=np.float32)
    vector[i] = 1.0
    return vector


def test_alias_matcher_accepts_a_close_synonym_and_rejects_others():
    close = unit(*(axis(0) + 0.2 * axis(1)))
    encoder = FakeEncoder({"temperature": axis(0), "frosty": close, "cricket": axis(2)})
    matcher = AliasMatcher(encoder, ONTOLOGY, threshold=0.9, margin=0.01)
    concept, similarity = matcher.match("frosty")
    assert concept == "TEMPERATURE"
    assert similarity > 0.9
    assert matcher.match("cricket") is None


def test_alias_matcher_refuses_when_two_concepts_tie():
    encoder = FakeEncoder({"temperature": axis(0), "humidity": axis(0), "sticky": axis(0)})
    matcher = AliasMatcher(encoder, ONTOLOGY, threshold=0.9, margin=0.01)
    assert matcher.match("sticky") is None


def test_normaliser_uses_the_matcher_only_as_a_last_resort():
    close = unit(*(axis(0) + 0.2 * axis(1)))
    encoder = FakeEncoder({"temperature": axis(0), "frosty": close})
    matcher = AliasMatcher(encoder, ONTOLOGY, threshold=0.9, margin=0.01)
    with_matcher = EntityNormalizer(ONTOLOGY, SETTINGS.normalization, matcher)
    without = EntityNormalizer(ONTOLOGY, SETTINGS.normalization)

    assert without.normalize("frosty", EntityType.ENV_VARIABLE).resolved is False
    result = with_matcher.normalize("frosty", EntityType.ENV_VARIABLE)
    assert (result.value, result.method) == (Variable.TEMPERATURE, "embedding")
    # Dictionary hits never reach the matcher.
    assert with_matcher.normalize("rainfall", EntityType.ENV_VARIABLE).method == "exact"
    # Locations never use embeddings.
    assert with_matcher.normalize("frosty", EntityType.LOCATION).resolved is False
