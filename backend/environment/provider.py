"""Open-Meteo adapter. Requests use fixed endpoints and vetted point coordinates."""
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from backend.environment.analytics import summarize
from backend.environment.schema import DailyRow, WeatherResult

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
FORECAST = 'https://api.open-meteo.com/v1/forecast'
# GeoNames coordinates verified through Open-Meteo geocoding (2026-11-15).
# Town points only; these do not represent district/state spatial averages.
LOCATIONS = {
    'loc:gangtok': ('Gangtok', 27.32574, 88.61216),
    'loc:namchi': ('Namchi', 27.16494, 88.36380),
    'loc:mangan': ('Mangan', 27.50965, 88.52206),
}
FIELDS = {
    'temperature_mean_c': 'temperature_2m_mean',
    'temperature_min_c': 'temperature_2m_min',
    'temperature_max_c': 'temperature_2m_max',
    'precipitation_mm': 'precipitation_sum',
    'rainfall_mm': 'rain_sum',
}
SNAPSHOT_DIR = Path(__file__).with_name('snapshots')


class DataUnavailable(Exception):
    pass


class OpenMeteo:
    def __init__(self, transport=None):
        self.transport = transport

    def retrieve(self, location_id: str, start: date, end: date, today: date,
                 source_mode: str = 'live') -> WeatherResult:
        name, lat, lon = LOCATIONS[location_id]
        historical = end <= date.fromordinal(today.toordinal() - 6)
        endpoint = ARCHIVE if historical else FORECAST
        params = {'latitude': lat, 'longitude': lon, 'start_date': start.isoformat(),
                  'end_date': end.isoformat(), 'daily': ','.join(FIELDS.values()),
                  'timezone': 'Asia/Kolkata', 'temperature_unit': 'celsius',
                  'precipitation_unit': 'mm'}
        if historical:
            # Explicit ERA5 avoids mixing historical models across the time series.
            params['models'] = 'era5'
        if start == end == today:
            params['current'] = 'temperature_2m,precipitation,rain,showers'
        if not historical:
            params['daily'] += ',showers_sum'
        warnings = ['Point grid estimate, not a station observation or district average.',
                    'PRECIPITATION includes rain and snow; historical rainfall is rain_sum; weather-model rainfall is rain_sum + showers_sum.']
        if source_mode == 'snapshot':
            path = SNAPSHOT_DIR / (location_id.split(':')[1] + '.json')
            if not path.exists() or start != date(2025, 1, 1) or end != date(2025, 1, 7):
                raise DataUnavailable('Recorded snapshots cover only 2025-01-01 through 2025-01-07.')
            saved = json.loads(path.read_text(encoding='utf-8'))
            payload, retrieved = saved['response'], datetime.fromisoformat(saved['retrieved_at'])
            source_url = saved['source_url']
            warnings.append('RECORDED SNAPSHOT: real previously retrieved reanalysis; no live call was made.')
        else:
            try:
                with httpx.Client(timeout=httpx.Timeout(20, connect=8), transport=self.transport) as client:
                    response = client.get(endpoint, params=params)
                    response.raise_for_status()
                    payload = response.json()
                    source_url = str(response.url)
                retrieved = datetime.now(timezone.utc)
            except (httpx.HTTPError, ValueError) as error:
                # No silently substituted data, and no remote body echoed into the UI.
                raise DataUnavailable('Open-Meteo request failed; retry or explicitly select a recorded snapshot.') from error
        try:
            if not isinstance(payload, dict):
                raise ValueError('expected object')
            if payload.get('error'):
                raise ValueError('provider error')
            if payload.get('timezone') != 'Asia/Kolkata':
                raise ValueError('unexpected timezone')
            daily, units = payload['daily'], payload['daily_units']
            if not isinstance(daily, dict) or not isinstance(units, dict):
                raise ValueError('expected daily objects')
            times = daily['time']
            if not times or len(set(times)) != len(times):
                raise ValueError('empty/duplicate dates')
            for key in FIELDS.values():
                if key not in daily or len(daily[key]) != len(times):
                    raise ValueError('misaligned data')
                if units.get(key) != ('mm' if key.endswith('_sum') else '°C'):
                    raise ValueError('unexpected units')
            def numeric(value):
                if value is None:
                    return None
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError('invalid number')
                return float(value)
            if not historical:
                if units.get('showers_sum') != 'mm' or len(daily['showers_sum']) != len(times):
                    raise ValueError('missing shower data')
            rows = [DailyRow(date=day, **{field: numeric(daily[key][i]) for field, key in FIELDS.items()})
                    for i, day in enumerate(times)]
            if not historical:
                for i, row in enumerate(rows):
                    showers = numeric(daily['showers_sum'][i])
                    if showers is not None and showers < 0:
                        raise ValueError('negative showers')
                    row.rainfall_mm = row.rainfall_mm + showers if row.rainfall_mm is not None and showers is not None else None
            expected_days = (end - start).days + 1
            if len(rows) != expected_days or [r.date for r in rows] != [date.fromordinal(start.toordinal()+i) for i in range(expected_days)]:
                raise ValueError('unexpected date coverage')
            if any(r.precipitation_mm is not None and r.precipitation_mm < 0 or
                   r.rainfall_mm is not None and r.rainfall_mm < 0 for r in rows):
                raise ValueError('negative precipitation')
            current = payload.get('current')
            if current is not None:
                current_units = payload.get('current_units', {})
                if any(current_units.get(k) != u for k, u in [('temperature_2m', '°C'), ('precipitation', 'mm'), ('rain', 'mm'), ('showers', 'mm')]):
                    raise ValueError('unexpected current units')
                current = {'time': current['time'], 'interval_seconds': current['interval'],
                           'temperature_c': numeric(current['temperature_2m']),
                           'precipitation_mm': numeric(current['precipitation']),
                           'rainfall_mm': (numeric(current['rain']) + numeric(current['showers'])
                                          if current['rain'] is not None and current['showers'] is not None else None)}
            summary = summarize(rows)
            if any(count < len(rows) for count in summary['valid_days'].values()):
                warnings.append('Missing daily data: statistics use available values; totals may be partial.')
            if not historical:
                warnings.append('Weather-model output. Today’s daily statistics include forecast hours and are not completed-day observations.')
            return WeatherResult(location_id=location_id, location_name=name,
                requested_latitude=lat, requested_longitude=lon,
                grid_latitude=payload['latitude'], grid_longitude=payload['longitude'],
                start=start, end=end, data_kind='reanalysis' if historical else 'weather_model',
                source='Open-Meteo / ERA5 reanalysis' if historical else 'Open-Meteo weather models',
                source_url=source_url, attribution='Weather data by Open-Meteo.com (CC BY 4.0); historical ERA5: Copernicus Climate Change Service / ECMWF.',
                retrieved_at=retrieved, current=current, daily=rows, summary=summary, warnings=warnings)
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise DataUnavailable('Open-Meteo returned invalid or incomplete data; no result was substituted.') from error
