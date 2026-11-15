"""Deterministic evidence compiler. Model can select facts, never calculate."""
import math
from itertools import combinations
from backend.environment.analytics import summarize
from backend.genai.schema import Fact, Source

METRICS = {
    'temperature_mean_c': ('°C','temperature_mean_c'),
    'temperature_min_c': ('°C','temperature_min_c'),
    'temperature_max_c': ('°C','temperature_max_c'),
    'rainfall_total_mm': ('mm','rainfall_mm'),
    'precipitation_total_mm': ('mm','precipitation_mm'),
}


def compile_facts(context):
    facts, sources = [], []
    summaries = []
    for i, weather in enumerate(context.environment.results):
        source_id = f's{i}'
        sources.append(Source(id=source_id, name=weather.source, url=weather.source_url,
            attribution=weather.attribution, data_kind=weather.data_kind,
            retrieved_at=weather.retrieved_at.isoformat(), source_mode=context.source_mode))
        # Recompute using the deterministic analytics function, never trust model claims.
        summary = summarize(weather.daily)
        summaries.append(summary)
        for metric, (unit, field) in METRICS.items():
            value = summary[metric]
            if value is None or not math.isfinite(value):
                continue
            valid = summary['valid_days'][field]
            facts.append(Fact(fact_id=f'{i}:{metric}', value=f'{value:.2f}', unit=unit,
                location_ids=[weather.location_id], location_names=[weather.location_name],
                start=weather.start.isoformat(), end=weather.end.isoformat(),
                source_ids=[source_id], metric=metric,
                coverage=f'{valid}/{summary["days"]}'))
    # Comparison arithmetic belongs HERE, not in the model. Only compare full,
    # identical coverage and periods; no false inference from partial totals.
    for a, b in combinations(range(len(summaries)), 2):
        left, right = context.environment.results[a], context.environment.results[b]
        if (left.start,left.end,left.data_kind) != (right.start,right.end,right.data_kind):
            continue
        for metric in ('temperature_mean_c', 'rainfall_total_mm'):
            unit, field = METRICS[metric]
            if any(s['valid_days'][field] != s['days'] or not s['days'] for s in (summaries[a],summaries[b])):
                continue
            delta = summaries[a][metric] - summaries[b][metric]
            if not math.isfinite(delta):
                continue
            facts.append(Fact(fact_id=f'{a}-{b}:{metric}', value=f'{delta:.2f}', unit=unit,
                location_ids=[left.location_id,right.location_id], location_names=[left.location_name,right.location_name],
                start=left.start.isoformat(), end=left.end.isoformat(), source_ids=[f's{a}',f's{b}'],
                metric='difference_'+metric, coverage=f'{summaries[a]["days"]}/{summaries[a]["days"]}'))
    return facts, sources


LABELS = {
    'en': ['Mean daily temperature','Minimum temperature','Maximum temperature','Rainfall sum','Total precipitation',
           'Difference in mean temperature','Difference in rainfall'],
    'hi': ['औसत दैनिक तापमान','न्यूनतम तापमान','अधिकतम तापमान','वर्षा का योग','कुल वर्षण',
           'औसत तापमान का अंतर','वर्षा का अंतर'],
    'ne': ['औसत दैनिक तापक्रम','न्यूनतम तापक्रम','अधिकतम तापक्रम','वर्षाको योग','कुल वर्षण',
           'औसत तापक्रमको अन्तर','वर्षाको अन्तर'],
}
KEYS = [*METRICS, 'difference_temperature_mean_c','difference_rainfall_total_mm']
NOTICES = {
    'en': 'AI selected these validated facts from the stored environmental results. Values are deterministic summaries of available daily data; coverage is shown per fact. Differences use left minus right. These are grid reanalysis/weather-model estimates, not station observations. No forecast, hazard or causal claim is made. Recorded snapshots are not live retrievals.',
    'hi': 'AI ने संग्रहीत पर्यावरणीय परिणामों से ये सत्यापित तथ्य चुने हैं। मान उपलब्ध दैनिक डेटा के गणितीय सारांश हैं; प्रत्येक तथ्य के साथ डेटा की उपलब्धता दी गई है। अंतर बाएँ स्थान से दाएँ स्थान को घटाकर है। ये ग्रिड पुनर्विश्लेषण या मौसम मॉडल के अनुमान हैं, स्टेशन मापन नहीं। भविष्यवाणी, आपदा या कारण का दावा नहीं किया गया है। संग्रहीत स्नैपशॉट लाइव डेटा नहीं हैं।',
    'ne': 'AI ले भण्डारित वातावरणीय नतिजाबाट यी प्रमाणित तथ्य छानेको छ। मानहरू उपलब्ध दैनिक तथ्याङ्कका गणितीय सारांश हुन्; हरेक तथ्यसँग उपलब्धता देखाइएको छ। अन्तर बायाँ स्थानबाट दायाँ स्थान घटाएर हो। यी ग्रिड पुनर्विश्लेषण वा मौसम मोडेलका अनुमान हुन्, स्टेशनका मापन होइनन्। भविष्यवाणी, विपद् वा कारणको दाबी गरिएको छैन। भण्डारित स्न्यापसट प्रत्यक्ष डेटा होइनन्।',
}


def render(language, facts, sources):
    lines = [NOTICES[language]]
    for fact in facts:
        label = LABELS[language][KEYS.index(fact.metric)]
        places = ' − '.join(fact.location_names)
        lines.append(f'{places} · {fact.start} — {fact.end}: {label}: {fact.value} {fact.unit} '
                     f'[{fact.coverage}; {", ".join(fact.source_ids)}].')
    # Source attribution is ALWAYS supplied by server, never generated or omitted by model.
    for source in sources:
        lines.append(f'[{source.id}] {source.name} · {source.data_kind} · {source.source_mode} · '
                     f'{source.retrieved_at}\n{source.url}\n{source.attribution}')
    return '\n\n'.join(lines)
