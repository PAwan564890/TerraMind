# Limitations

What TerraMind cannot do, what it does poorly, and what has not been checked.
Read this before quoting any number from this project.

## It does not answer questions

Only the NLP layer exists. TerraMind can turn "What is the rainfall trend in
Gangtok?" into a structured query. It cannot say what the rainfall was. There
is no environmental data, no prediction model, no document retrieval, no
language model and no interface. It is not yet a digital twin.

## No human review, no real users

- Every training template, every evaluation set and the Hindi and Nepali
  entries of the ontology were drafted by an AI assistant.
- **No fluent Hindi or Nepali speaker has reviewed any of it.** A review pack
  is prepared (`review/hindi_nepali_review.csv`, 712 rows, all marked
  PENDING; see [REVIEW_GUIDE.md](REVIEW_GUIDE.md)). Preparing it is not the
  same as doing it.
- **No real user query has been collected.** The "realistic" evaluation set
  imitates real typing; the same author wrote it and the system.
- Training data is synthetic: 3,867 rows from 100 sentence frames.

It is not production-ready and makes no such claim.

## How well it works

On real-user-style queries the whole pipeline gets 61% exactly right: 71% in
English, 63% in Hindi, 50% in Nepali. On template-style text it gets 90%.
See [EVALUATION.md](EVALUATION.md).

## Known defects

| Defect | Effect |
| --- | --- |
| The ontology lacks everyday words that imply a variable ("rainier", टेम्परेचर, पानी पर्नु, हवा for air quality, रुखबिरुवा) | The variable is not found and the user is asked. Such queries are right 1 time in 10 on the realistic set. Worst in Nepali |
| Intent flips on unseen phrasing | "Wetter or drier?" becomes a comparison; "how likely is a flood?" a general question |
| NER tags "sea level" (समुद्र तल, समुद्र सतह) as an entity | Hindi and Nepali elevation questions get an "unknown place" question |
| The similarity check rejects some real questions | 3 of 144 hand-written real queries, e.g. "What altitude does Lachung sit at?" |
| Off-topic questions close to the domain are questioned, not rejected | "Where is the best momo in Gangtok?" in Nepali gets a clarifying question |
| Fraction words are not numbers | "If rainfall halves" (आधी, आधा) builds no scenario |
| Romanised Hindi and Nepali fail quietly | Detected as English and rejected as off-topic; the user is not told the script is unsupported |
| Two questions in one | Only one is answered, with no warning |

## Confidence threshold

The threshold sits at the bottom of its range, so no query is questioned for
low confidence. With the final model this is a measured outcome: the 5% target
is met on validation data even under a family-level upper bound (3.9%).
Among answered queries, the wrong-intent rate is 1.3% on the test set and 3 to
6% on the hand-written sets, but 18% for English on gold_v2 (2 of 11).
Validation data is 18 template families and easier than real text. A stricter
target (2%) would raise the threshold to 0.90; that choice has not been made.

## The evaluation is small and has been looked at

- Hand-written sets have 51 to 58 queries. One query is about 2 points
  overall and 5 to 6 points for one language.
- Only 12 off-topic queries exist across the hand-written sets.
- gold, gold_v2 and the template test set were used to design fixes. The
  realistic set was not, but its errors have now been read once.
- The pipeline is evaluated with one seed per task. Intent accuracy varies by
  3 to 4 points between seeds on the test set.
- Thresholds come from 18 validation families.

## Scope limits by design

- **Sikkim only.** 24 places are known: the state, 6 districts, 15 towns and
  2 rivers. Any other place produces a clarification, not an answer.
- **Three languages, native script.** Mixed-script text is detected and
  flagged, with no quality claim.
- **One intent and one time span per query.**
- **Time expressions are a rule list.** Month names, seasons and Bikram Sambat
  years are not handled. Years are read as Common Era.
- **Hindi कल and परसों** are resolved by verb tense; with no tense cue the
  future is assumed and flagged.
- **A scenario with a missing piece is dropped whole** and reported in
  `warnings`.
- **Context is simple.** It remembers the last topic, not the conversation.
  After a hypothetical, a follow-up returns to the earlier topic. A stated
  place is forgotten after five turns without being repeated.
- **District boundaries and town-to-district assignments** come from one
  encyclopaedia page and were not checked against an official source.

## Operational limits

- Conversation state is in memory: lost on restart, not shared between
  processes. Run one worker.
- Requests are processed one at a time.
- No authentication, rate limiting or CORS.
- Tested through an in-process client only. Never run as a live server under
  load, never deployed.
- Latency (about 70 ms per query) was measured with the models on a GPU. The
  final models were not timed on a CPU.
- Training the final models used 3.9 of 4.0 GB of GPU memory at the configured
  batch size. Memory needed for inference was not measured.

## Reproducibility: what was and was not verified

Verified on 8 October 2026, on the development laptop:

- The files a fresh clone would contain were copied to a separate folder with
  no environment and no models. Following the README there, the install
  succeeded, all tests passed, the regenerated dataset was identical to the
  stored one, and every script in the documented sequence ran through to a
  working API.

Not verified:

- **Not a true clean clone.** The copy was made from the working folder, not
  cloned from a remote, because the work is not committed.
- **Same machine.** Python, drivers and the Hugging Face cache were already
  present, so the base-model download was not exercised from scratch.
- **Windows only.** Nothing was run on Linux or macOS.
- **The check trained one epoch** to prove the steps run. It did not reproduce
  the reported scores.
- **The GPU install path** in the README was done once, by hand, with a
  manually verified download. It was not repeated in the clean copy.
- **The Colab notebook** was written and never executed. Final training was
  done locally.

## Not verified elsewhere

- Model facts quoted in the original design document (parameter counts,
  training languages) were stated from memory.
- The licences of the base models were not reviewed.

## What would most improve confidence in this project

1. A fluent-speaker review of the Hindi and Nepali data, starting with the
   templates and the ontology's vocabulary.
2. A few hundred real user queries, kept untouched as a test set.
3. A decision on the confidence target, made on data that looks like real use.
