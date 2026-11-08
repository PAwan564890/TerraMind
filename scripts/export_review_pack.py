"""Export every Hindi and Nepali string in the project for fluent-speaker review.

Run from the project root:
    python scripts/export_review_pack.py

Writes review/hindi_nepali_review.csv (UTF-8 with BOM, so Excel shows
Devanagari correctly). Each row is one string with where it came from, an
English reference where one exists, and empty columns for the reviewer.

Every row starts with status PENDING. Nothing in this project has been
reviewed by a fluent speaker; this script only prepares the material.
"""

import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from backend.core import load_settings  # noqa: E402
from backend.core.config import PROJECT_ROOT  # noqa: E402
from backend.nlp.dataset.generator import (  # noqa: E402
    LEXICON_PATH,
    TEMPLATES_PATH,
    build_pools,
    fill_template,
    load_families,
    load_lexicon,
)
from backend.nlp.ontology import get_ontology  # noqa: E402
from backend.nlp.query.enums import Language  # noqa: E402

COLUMNS = ["row", "source_file", "item_id", "kind", "language", "text", "filled_example",
           "english_reference", "note", "status", "reviewer_verdict", "suggested_text",
           "reviewer_comment"]
REVIEWED = (Language.HI, Language.NE)


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def main() -> int:
    settings = load_settings()
    ontology = get_ontology()
    lexicon = load_lexicon()
    pools = build_pools(ontology, lexicon)
    rng = random.Random(settings.project.seed)
    test_dir = settings.paths.data_dir / "test"
    ontology_dir = settings.paths.ontology_dir
    rows: list[dict] = []

    def add(source, item_id, kind, language, text, reference="", note="", example=""):
        rows.append({
            "source_file": source, "item_id": item_id, "kind": kind,
            "language": language if isinstance(language, str) else language.value,
            "text": text, "filled_example": example, "english_reference": reference,
            "note": note, "status": "PENDING", "reviewer_verdict": "",
            "suggested_text": "", "reviewer_comment": "",
        })

    # 1. Templates: the sentence frames the training data is generated from.
    source = relative(TEMPLATES_PATH)
    for intent, families in load_families().items():
        for family in families:
            english = " | ".join(family.templates(Language.EN))
            for language in REVIEWED:
                for i, template in enumerate(family.templates(language), start=1):
                    example, _, _ = fill_template(template, language, "train", pools,
                                                  settings.dataset, rng)
                    add(source, f"{family.id}#{i}", "template", language, template, english,
                        f"intent {intent.value}; words in {{braces}} are slots", example)

    # 2. Lexicon: time expressions, change amounts, off-topic vocabulary.
    source = relative(LEXICON_PATH)
    for group in ("time", "change"):
        for slot, by_language in lexicon[group].items():
            english = by_language["en"]
            for language in REVIEWED:
                for i, entry in enumerate(by_language[language.value]):
                    text = entry if isinstance(entry, str) else entry[0]
                    meaning = "" if isinstance(entry, str) else " -> " + ", ".join(map(str, entry[1:]))
                    ref = english[i] if i < len(english) else ""
                    ref = ref if isinstance(ref, str) else ref[0]
                    add(source, f"{group}.{slot}[{i}]", "lexicon", language, text, ref,
                        f"{group} expression{meaning}")
    for slot, by_language in lexicon["ood"].items():
        for language in REVIEWED:
            for i, text in enumerate(by_language[language.value]):
                add(source, f"ood.{slot}[{i}]", "lexicon", language, text,
                    by_language["en"][i], "off-topic vocabulary")

    # 3. Ontology: names of variables and hazards.
    for file_name, entries in (("variables.yaml", ontology.variables),
                               ("disasters.yaml", ontology.disasters)):
        source = relative(ontology_dir / file_name)
        for concept, entry in entries.items():
            for language in REVIEWED:
                for alias in entry.aliases.by_language()[language]:
                    add(source, concept.value, "alias", language, alias,
                        ", ".join(entry.aliases.en), "a noun that names this concept")
                descriptors = getattr(entry, "descriptors", None)
                if descriptors:
                    for word in descriptors.by_language()[language]:
                        add(source, concept.value, "descriptor", language, word,
                            ", ".join(descriptors.en),
                            "a word that implies this concept without naming it")

    # 4. Gazetteer: place names.
    source = relative(ontology_dir / "locations.yaml")
    for loc_id, entry in ontology.locations.items():
        for language in REVIEWED:
            for alias in entry.aliases.by_language()[language]:
                add(source, loc_id, "place_name", language, alias, entry.name,
                    f"{entry.type.value}; check the spelling people actually use")

    # 5. Gold sets: hand-written test questions with an English version.
    for file_name in ("gold.yaml", "gold_v2.yaml"):
        path = test_dir / file_name
        for item in yaml.safe_load(path.read_text(encoding="utf-8")):
            for language in REVIEWED:
                add(relative(path), item["id"], "test_query", language, item[language.value],
                    item["en"], "must mean the same as the English reference")

    # 6. Real-user-style set: written per language, no English parallel.
    path = test_dir / "realistic.yaml"
    for item in yaml.safe_load(path.read_text(encoding="utf-8")):
        if item["language"] in ("hi", "ne"):
            expected = item["expected"]
            add(relative(path), item["id"], "test_query", item["language"], item["text"], "",
                f"meant to look like casual typing ({item['phenomenon']}); expected intent "
                f"{expected['intent']}. Is this how someone would really write it?")

    # 7. Dialogues.
    path = test_dir / "dialogues.yaml"
    for dialogue in yaml.safe_load(path.read_text(encoding="utf-8")):
        for number, turn in enumerate(dialogue["turns"], start=1):
            language = turn["parse"]["language"]
            if language in ("hi", "ne"):
                add(relative(path), f"{dialogue['id']}#turn{number}", "dialogue_turn", language,
                    turn["text"], "", f"expected intent {turn['expect']['intent']}")

    # 8. Synonym test words.
    path = test_dir / "synonyms.yaml"
    synonyms = yaml.safe_load(path.read_text(encoding="utf-8"))
    for text, language, concept in synonyms["positives"]:
        if language in ("hi", "ne"):
            add(relative(path), concept, "synonym", language, text, concept,
                "should make a reader think of this concept")
    for text, language in synonyms["negatives"]:
        if language in ("hi", "ne"):
            add(relative(path), "unrelated", "synonym", language, text, "",
                "should have nothing to do with weather or environment")

    for number, row in enumerate(rows, start=1):
        row["row"] = number

    out_dir = PROJECT_ROOT / "review"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "hindi_nepali_review.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        counts[(row["kind"], row["language"])] = counts.get((row["kind"], row["language"]), 0) + 1
    print(f"wrote {out_path.relative_to(PROJECT_ROOT)}: {len(rows)} rows, all PENDING")
    print(f"  {'kind':<16}{'hi':>6}{'ne':>6}")
    for kind in dict.fromkeys(row["kind"] for row in rows):
        print(f"  {kind:<16}{counts.get((kind, 'hi'), 0):>6}{counts.get((kind, 'ne'), 0):>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
