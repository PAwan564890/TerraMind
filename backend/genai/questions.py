"""Bounded follow-up routing over stored facts, never new data or calculations.

Only complete supported formulations are accepted. A keyword inside an
unsupported question (e.g. temperature tomorrow) cannot authorize an answer.
"""
import re
import unicodedata

_ALL = {
    'summarize these environmental results', 'summarize these results',
    'explain these results', 'explain stored results', 'summarize stored results',
    'explain the stored results', 'explain these stored results',
    'इन परिणामों का सारांश समझाएँ', 'यी नतिजाको सारांश बुझाउनुहोस्',
}
_ALIASES = {
    'temperature': 'temperature_mean_c',
    'temperature results': 'temperature_mean_c',
    'these temperature results': 'temperature_mean_c',
    'temperature summary': 'temperature_mean_c',
    'mean temperature': 'temperature_mean_c',
    'average temperature': 'temperature_mean_c',
    'mean daily temperature': 'temperature_mean_c',
    'average daily temperature': 'temperature_mean_c',
    'minimum temperature': 'temperature_min_c',
    'maximum temperature': 'temperature_max_c',
    'rainfall': 'rainfall_total_mm', 'rain': 'rainfall_total_mm',
    'rainfall summary': 'rainfall_total_mm', 'rainfall total': 'rainfall_total_mm',
    'total rainfall': 'rainfall_total_mm',
    'precipitation': 'precipitation_total_mm',
    'total precipitation': 'precipitation_total_mm',
}
_NATIVE = {
    'वर्षा का सारांश समझाएँ': 'rainfall_total_mm',
    'बारिश का सारांश समझाएँ': 'rainfall_total_mm',
    'वर्षाको सारांश बुझाउनुहोस्': 'rainfall_total_mm',
    'वर्षाको कुल योग कति छ': 'rainfall_total_mm',
    'औसत दैनिक तापमान समझाएँ': 'temperature_mean_c',
    'औसत दैनिक तापक्रम बुझाउनुहोस्': 'temperature_mean_c',
}
_COMPARISONS = {
    'compare the mean temperatures': 'difference_temperature_mean_c',
    'compare mean temperatures': 'difference_temperature_mean_c',
    'compare the rainfall totals': 'difference_rainfall_total_mm',
    'compare rainfall totals': 'difference_rainfall_total_mm',
}
_REQUEST = re.compile(
    r'(?:please )?(?:explain|describe|summarize|show|what is|what was|what are|what were) '
    r'(?:the )?(?P<metric>.+?)(?: (?:in these stored results|in the stored results|'
    r'in these results|from these results|for this period))?'
)


def select_facts(question, facts):
    """Return matching facts, or [] if unsupported/missing. No provider decision.

    The summary default may choose any available fact. Specific requests are
    restricted to the named metric; absent metrics and incomplete comparisons
    have no eligible facts and are refused before an LLM call.
    """
    key = ' '.join(unicodedata.normalize('NFC', question).casefold().split()).rstrip(' .?!।')
    if key in _ALL:
        return list(facts)
    metric = _NATIVE.get(key) or _COMPARISONS.get(key)
    if metric is None:
        match = _REQUEST.fullmatch(key)
        metric = _ALIASES.get(match['metric']) if match else None
    return [fact for fact in facts if fact.metric == metric] if metric else []
