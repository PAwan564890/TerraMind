"""Explicit, limited rule demonstration. Never loaded as trained NLP inference.

Reuses the original ontology, normalizer, context manager and query contract.
Language, intent and span recognition here are rules, with NO measured confidence.
"""
import re

from backend.core import load_settings
from backend.nlp.context import ConversationManager, is_fragment
from backend.nlp.normalization import EntityNormalizer
from backend.nlp.normalization.normalizer import Resolution, canonical_time
from backend.nlp.normalization.morphology import ATTACHED_ENDINGS
from backend.nlp.ontology import get_ontology
from backend.nlp.preprocessing import prepare_query
from backend.nlp.query.enums import EntityType, Intent, Language, Status, TimeType
from backend.nlp.query.schema import (
    AnalyzeResponse, Clarification, Entity, IntentResult, LanguageResult, TimePeriod,
)
from backend.nlp.query.structurer import FoundEntity, build_query, build_turn
from backend.nlp.query.validator import validate_query

DEMO_WARNING = 'DEMO: language, intent and entity spans use rules; confidence is unmeasured (0), not a probability.'


class DemoAnalyzer:
    def __init__(self):
        self.settings = load_settings()
        self.ontology = get_ontology()
        self.normalizer = EntityNormalizer(self.ontology, self.settings.normalization)
        self.context = ConversationManager(self.settings.context)

    def analyze(self, query: str, session_id: str | None = None) -> AnalyzeResponse:
        text = prepare_query(query, self.settings.input.max_query_chars)
        # Simple native-script cues, deliberately not a learned detector.
        devanagari = bool(re.search('[ऀ-ॿ]', text))
        nepali = bool(re.search(r'(?<![ऀ-ॿ])छ(?=$|[^ऀ-ॿ])|कति|पछिल्ल|अहिले|गान्तोक|नाम्ची|तापक्रम|हिजो', text))
        language = Language.NE if nepali else Language.HI if devanagari else Language.EN
        found = []
        candidates = []
        endings = '|'.join(re.escape(e) for e in sorted(ATTACHED_ENDINGS, key=len, reverse=True))
        for kind, index in [(EntityType.LOCATION, self.ontology.location_index),
                            (EntityType.ENV_VARIABLE, self.ontology.concept_index)]:
            for alias in index:
                # Unicode vowel signs are not \w: spell out the script range.
                pattern = r'(?<![\wऀ-ॿ])' + re.escape(alias) + rf'(?=$|[^\wऀ-ॿ]|(?:{endings})(?=$|[^\wऀ-ॿ]))'
                for m in re.finditer(pattern, text, re.I):
                    candidates.append((m.start(), m.end(), kind))
        # Longest alias wins, e.g. "Gangtok district" before "Gangtok".
        occupied = []
        for start, end, kind in sorted(candidates, key=lambda x: (-(x[1]-x[0]), x[0])):
            if any(start < b and end > a for a, b in occupied):
                continue
            occupied.append((start, end))
            resolution = self.normalizer.normalize(text[start:end], kind, text, language)
            found.append(FoundEntity(text[start:end], start, end, 0.0, resolution))
        found.sort(key=lambda e: e.start)
        # Only this demo adds explicit ISO date ranges. No production parser change.
        dates = list(re.finditer(r'\b\d{4}-\d{2}-\d{2}\b', text))
        invalid_dates = False
        if dates:
            try:
                if len(dates) != 2:
                    raise ValueError('two dates required')
                period = TimePeriod(type=TimeType.DATE_RANGE,
                                    start=dates[0].group(), end=dates[1].group())
                start, end = dates[0].start(), dates[1].end()
                found.append(FoundEntity(text[start:end], start, end, 0.0,
                    Resolution(type=EntityType.TIME, value=period,
                               canonical=canonical_time(period), method='rule', confidence=1)))
            except ValueError:
                invalid_dates = True
        has_topic = any(e.resolution.type in (EntityType.ENV_VARIABLE, EntityType.DISASTER) for e in found)
        compare = re.search(r'\bcompare|\bcomparison|तुलना', text, re.I)
        trend = re.search(r'\btrend|\bhistory|प्रवृत्ति|रुझान', text, re.I)
        intent = Intent.COMPARISON if compare else Intent.CLIMATE_TREND if trend else Intent.WEATHER_QUERY
        fragment = is_fragment(text, [(e.start, e.end) for e in found])
        warnings = [DEMO_WARNING, 'Demo vocabulary is limited; use the documented questions.']
        def response(status, structured=None, clarification=None):
            return AnalyzeResponse(language=LanguageResult(code=language, confidence=0),
                intent=IntentResult(label=intent, confidence=0),
                entities=[Entity(text=e.text, type=e.resolution.type, start=e.start, end=e.end,
                                 normalized=e.resolution.canonical, confidence=0) for e in found],
                structured_query=structured, status=status, clarification=clarification,
                warnings=warnings)
        if not has_topic and not fragment:
            intent = Intent.OUT_OF_DOMAIN
            return response(Status.OUT_OF_DOMAIN)
        # Do not interpret hazard/scenario/causal questions as weather lookups.
        if invalid_dates or re.search(r'\bwhy\b|\bif\b|\bpredict|क्यों|किन|यदि', text, re.I) or any(
            e.resolution.type is EntityType.DISASTER for e in found
        ):
            return response(Status.NEEDS_CLARIFICATION, clarification=Clarification(
                reason='demo_unsupported', message_key='Use a temperature or rainfall lookup with a town and period; ISO ranges need two valid, ordered dates.'))
        turn, notes = build_turn(text, language, intent, found, self.ontology, fragment)
        warnings.extend(notes)
        resolved = self.context.process(session_id, turn)
        intent = resolved.intent
        structured = build_query(resolved, text)
        # Unlike production's documented trend default, demo never invents a period.
        if structured.time_period is None:
            return response(Status.NEEDS_CLARIFICATION, structured, Clarification(
                reason='missing_time', message_key='Specify today, last 7 days, or two ISO dates.',
                missing_fields=['time_period']))
        checked = validate_query(structured, warnings, self.settings.decision)
        warnings.extend(checked.warnings)
        return response(Status.OK if checked.ok else Status.NEEDS_CLARIFICATION,
                        checked.query, checked.clarification)
