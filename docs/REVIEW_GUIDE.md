# Hindi and Nepali review guide

**Status: PENDING. No fluent speaker has reviewed any Hindi or Nepali text in
this project.** Everything was drafted by an AI assistant. This guide and the
review pack exist so that a reviewer can check it; they are not evidence that
anyone has.

## What to review

Run this to produce the pack (or use the copy in the repository):

```powershell
python scripts/export_review_pack.py
```

It writes `review/hindi_nepali_review.csv`: 712 rows, one per string, about 356 per
language. Open it in Excel or LibreOffice (it is UTF-8 with a byte-order mark,
so Devanagari displays correctly).

| Kind | Rows (hi / ne) | What it is | Why it matters |
| --- | --- | --- | --- |
| `template` | 120 / 120 | Sentence frames; words in `{braces}` are slots filled automatically | Highest priority. All training data comes from these |
| `lexicon` | 77 / 77 | Time expressions, change amounts, off-topic vocabulary | Fill the slots |
| `alias` | 36 / 37 | Nouns naming a variable or hazard | Fill the slots; also used to recognise the word |
| `descriptor` | 4 / 4 | Words implying a variable ("cold") | Recognition only |
| `place_name` | 36 / 40 | Spellings of Sikkim places | Recognition; a missing common spelling means the place is not found |
| `test_query` | 53 / 53 | Hand-written test questions | If these are unnatural, the reported scores mean less |
| `dialogue_turn` | 7 / 5 | Conversation turns | As above |
| `synonym` | 22 / 21 | Test words for a feature that is switched off | Lowest priority |

Suggested order if time is short: templates, place names, aliases, test
queries, then the rest.

## How to fill in the sheet

For each row, set `reviewer_verdict` to one of:

| Verdict | Meaning |
| --- | --- |
| `ok` | Correct and natural; a native speaker could have written it |
| `stiff` | Correct but formal, bookish or translated-sounding |
| `wrong` | A grammar, spelling or meaning error |
| `not_this_language` | Hindi in a Nepali row, or the reverse |

For anything other than `ok`, put a better version in `suggested_text`, and
add a note in `reviewer_comment` if the reason is not obvious. Leave `status`
alone; the project owner changes it after applying the result.

## Things worth knowing before you start

**Templates are filled by machine.** The column `filled_example` shows one
filling. Judge the frame with any reasonable filling, not just that one.

**Hindi templates dodge gender agreement on purpose.** A slot may receive a
masculine or a feminine noun, so the templates say "{variable} का स्तर"
instead of "कितनी {variable}". That is expected to read as formal. Mark it
`stiff` only where it is actually odd, and suggest alternatives that still
work for both genders.

**Known rough fills.** Some slot values do not inflect: "बादल फटना का खतरा"
should be "बादल फटने का खतरा". Please flag any template where this is common.

**Nepali endings attach to the slot.** "{loc}मा" is intended.

**The real-user-style rows are meant to be messy.** For
`backend/nlp/data/test/realistic.yaml` the question is different: would a
real person type this? Typos and missing punctuation are deliberate. Mark it
`wrong` only if no one would write it that way.

**Places.** Please add any spelling in common use that is missing. District
names follow the December 2021 reorganisation; older names ("उत्तर सिक्किम")
are kept as alternatives.

## Questions I would most like answered

1. Are the Nepali words for "cloudburst" (बादल फाट्ने, मेघ विस्फोट) and "GLOF"
   (हिमताल विस्फोट) what people use?
2. Is "हाल" used for "currently" in everyday Nepali, or mostly in writing?
3. Hindi "कल" and "परसों" are resolved by verb tense. Are there common
   sentences where that would go wrong?
4. Which Hindi templates would a Sikkim resident actually say, and which
   sound like a textbook?
5. Is the Hindi and Nepali in the two languages' rows distinct enough? Several
   Nepali rows may be Hindi with Nepali endings.

## Word lists that live in code

These are not in the sheet because they are regular expressions or sets in
Python files. A reviewer comfortable reading code may want to look at them.

| File | Contents |
| --- | --- |
| `backend/nlp/query/cues.py` | Words that signal "why", "trend", "which areas", "increase", "decrease" |
| `backend/nlp/normalization/time_parser.py` | Words for today, tomorrow, last, next, and time units |
| `backend/nlp/normalization/numbers.py` | Number words |
| `backend/nlp/normalization/normalizer.py` | Nepali case endings and Hindi postpositions removed before lookup |
| `backend/nlp/context/fragments.py` | Filler words ignored when detecting a follow-up |

## After the review

1. Apply accepted suggestions to the source file named in each row.
2. Run `python scripts/generate_dataset.py`, then retrain and re-evaluate
   (see the README).
3. Record who reviewed what, and when, in this file. Only then remove the
   "not reviewed" notices from the YAML headers and documents.

## Review log

| Date | Reviewer | Language | Rows covered | Outcome |
| --- | --- | --- | --- | --- |
| | | | | Nothing reviewed yet |
