"""Descriptive summaries only. A missing value is never replaced with zero."""
from statistics import fmean
from backend.environment.schema import DailyRow


def summarize(rows: list[DailyRow]) -> dict:
    def values(name):
        return [getattr(row, name) for row in rows if getattr(row, name) is not None]
    means = values('temperature_mean_c')
    lows, highs = values('temperature_min_c'), values('temperature_max_c')
    precipitation, rain = values('precipitation_mm'), values('rainfall_mm')
    n = len(rows)
    return {
        'days': n,
        'temperature_mean_c': fmean(means) if means else None,
        'temperature_min_c': min(lows) if lows else None,
        'temperature_max_c': max(highs) if highs else None,
        'precipitation_total_mm': sum(precipitation) if precipitation else None,
        'rainfall_total_mm': sum(rain) if rain else None,
        'valid_days': {key: len(values(key)) for key in DailyRow.model_fields if key != 'date'},
        'totals_complete': bool(n) and len(precipitation) == n and len(rain) == n,
        'interpretation': 'Calculated over available daily values only; incomplete totals are partial. No climate trend significance or prediction is inferred.',
    }
