"""Integrity checks for the generated dataset.

`errors` must be empty before the data is used. `warnings` flag rows a human
should look at but that do not make the data unusable.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from backend.nlp.dataset.records import DatasetRecord
from backend.nlp.ontology import Ontology, normalize_alias
from backend.nlp.preprocessing import normalize_query
from backend.nlp.query.enums import EntityType, Intent, Language

_PUNCTUATION = "?.,।!:;\"'()"
_MAX_ALIAS_WORDS = 4


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _all_aliases(ontology: Ontology) -> set[str]:
    entries = [*ontology.variables.values(), *ontology.disasters.values(),
               *ontology.locations.values()]
    return {normalize_alias(alias) for entry in entries for alias in entry.aliases.all()}


def _tokens(text: str) -> list[tuple[int, int]]:
    """(start, end) of every whitespace-separated word, punctuation trimmed."""
    tokens, position = [], 0
    for word in text.split():
        start = text.index(word, position)
        position = start + len(word)
        stripped = word.strip(_PUNCTUATION)
        if stripped:
            inner = word.index(stripped)
            tokens.append((start + inner, start + inner + len(stripped)))
    return tokens


def _unlabelled_aliases(record: DatasetRecord, aliases: set[str]) -> list[str]:
    """Ontology terms present in the text but not covered by any entity label.
    An unlabelled term teaches NER that the word is sometimes not an entity."""
    tokens = _tokens(record.text)
    found = []
    for i in range(len(tokens)):
        for j in range(i, min(i + _MAX_ALIAS_WORDS, len(tokens))):
            start, end = tokens[i][0], tokens[j][1]
            if normalize_alias(record.text[start:end]) not in aliases:
                continue
            if not any(start < e.end and e.start < end for e in record.entities):
                found.append(record.text[start:end])
    return found


def validate_records(records: list[DatasetRecord], ontology: Ontology) -> Report:
    report = Report()
    aliases = _all_aliases(ontology)

    group_splits: dict[str, set[str]] = defaultdict(set)
    text_count = Counter(r.text for r in records)
    id_count = Counter(r.id for r in records)

    for text, n in text_count.items():
        if n > 1:
            report.errors.append(f"duplicate text ({n}x): {text}")
    for record_id, n in id_count.items():
        if n > 1:
            report.errors.append(f"duplicate id: {record_id}")

    for r in records:
        group_splits[r.group_id].add(r.split)

        # Training text must already be in the form the pipeline will feed the
        # models at run time; otherwise entity offsets would not line up.
        if normalize_query(r.text) != r.text:
            report.errors.append(f"{r.id}: text is not in normalised form")

        previous_end = 0
        for e in sorted(r.entities, key=lambda e: e.start):
            if r.text[e.start:e.end] != e.text:
                report.errors.append(f"{r.id}: span {e.start}:{e.end} is not '{e.text}'")
            if e.start < previous_end:
                report.errors.append(f"{r.id}: overlapping entities")
            previous_end = e.end

        if r.heldout_location and r.split != "test":
            report.errors.append(f"{r.id}: held-out location outside the test split")
        if r.intent is Intent.OUT_OF_DOMAIN:
            # An off-topic request can still name a real place ("a taxi to
            # Gangtok"); it can never carry an operation or another entity type.
            if r.operation or any(e.type is not EntityType.LOCATION for e in r.entities):
                report.errors.append(f"{r.id}: out-of-domain row may only label places")
        if r.intent is not Intent.OUT_OF_DOMAIN:
            if r.operation is None:
                report.errors.append(f"{r.id}: in-domain row needs an operation")
            for term in _unlabelled_aliases(r, aliases):
                report.warnings.append(f"{r.id}: unlabelled ontology term '{term}' in: {r.text}")

    for group_id, splits in group_splits.items():
        if len(splits) > 1:
            report.errors.append(f"group {group_id} appears in several splits: {sorted(splits)}")

    for split in ("train", "val", "test"):
        present = {(r.intent, r.language) for r in records if r.split == split}
        for intent in Intent:
            for language in Language:
                if (intent, language) not in present:
                    report.errors.append(f"{split} has no {intent.value} rows in {language.value}")

    return report


def summarize(records: list[DatasetRecord]) -> str:
    """Counts per split, intent and language as a printable table."""
    counts = Counter((r.split, r.intent, r.language) for r in records)
    lines = []
    for split in ("train", "val", "test"):
        rows = [r for r in records if r.split == split]
        groups = len({r.group_id for r in rows})
        lines.append(f"\n{split}: {len(rows)} rows from {groups} template families")
        lines.append(f"  {'intent':<22}{'en':>6}{'hi':>6}{'ne':>6}{'total':>8}")
        for intent in Intent:
            per_language = [counts[(split, intent, language)] for language in Language]
            lines.append(
                f"  {intent.value:<22}" + "".join(f"{n:>6}" for n in per_language)
                + f"{sum(per_language):>8}"
            )
        totals = [sum(counts[(split, i, language)] for i in Intent) for language in Language]
        lines.append(f"  {'TOTAL':<22}" + "".join(f"{n:>6}" for n in totals) + f"{sum(totals):>8}")

    test = [r for r in records if r.split == "test"]
    heldout = sum(r.heldout_location for r in test)
    lines.append(f"\ntest rows with a held-out location: {heldout} of {len(test)}")
    entity_counts = Counter(e.type.value for r in records for e in r.entities)
    lines.append("entity labels: " + ", ".join(f"{k}={v}" for k, v in sorted(entity_counts.items())))
    return "\n".join(lines)
