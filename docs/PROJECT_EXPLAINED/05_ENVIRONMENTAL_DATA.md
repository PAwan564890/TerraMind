# Environmental data, points and provenance

Authoritative registry: `backend/environment/locations.json`, validated by `registry.py`. Set `TERRAMIND_EXTENDED_LOCATIONS=1` to enable ten points; default remains Gangtok, Namchi and Mangan.

| Point | Latitude | Longitude | GeoNames ID |
|---|---:|---:|---:|
| Gangtok | 27.32574 | 88.61216 | 1271631 |
| Namchi | 27.16494 | 88.36380 | 1262029 |
| Mangan | 27.50965 | 88.52206 | 1263776 |
| Gyalshing | 27.28952 | 88.25764 | 1270577 |
| Rangpo | 27.17733 | 88.53358 | 1258484 |
| Jorethang | 27.10696 | 88.32332 | 7279751 |
| Ravangla | 27.30589 | 88.36355 | 10630194 |
| Pelling | 27.30158 | 88.23266 | 7114402 |
| Soreng | 27.16902 | 88.20263 | 1255707 |
| Lachung | 27.69340 | 88.74429 | 1265346 |

These are town points, not district polygons/averages. Registry records carry source URL, GeoNames attribution, admin/country checks, aliases and verification metadata. Ambiguous Pakyong and Singtam and unavailable Chungthang results were excluded rather than guessed. Nearby towns may map to the same model grid cell and share values.

Original weather: daily mean/min/max temperature (°C), rainfall and precipitation (mm). Rainfall and total precipitation are distinct fields; recent rainfall combines rain and showers. Historical requests explicitly use ERA5 reanalysis via Open-Meteo. Recent data are weather-model past estimates, not guaranteed station observations. Timezone is Asia/Kolkata; requested coordinates and returned grid coordinates remain separate.

With `TERRAMIND_ADDITIONAL_MEASUREMENTS=1`, a separate typed product retrieves daily mean relative humidity at 2 m (%) and daily mean scalar wind speed at 10 m (m/s), requesting `wind_speed_unit=ms`. Humidity must be finite and 0–100; wind speed finite and nonnegative. These are neither gusts nor wind direction.

Supported bounded historical intervals start in 1940, are nonfuture, chronological and at most 366 inclusive days. ERA5 requires a lag of six days; recent retrieval has its own 92-day availability window. Unsupported spans are rejected, not silently expanded. Historical snapshots only cover the original three points for 1–7 January 2025; new points and supplemental variables have no snapshot fallback.

Validation preserves nulls and rejects wrong units, mismatched dates and malformed values. HTTP GET retries are bounded (maximum two attempts); large responses, provider rejection and data failures remain visible. Missing data are never zero-filled. Source evidence includes provider URLs, model/data kind, coordinates, units, period, coverage and timestamps where returned. Attribution includes Open-Meteo/GeoNames and historical ECMWF/Copernicus. Review linked source licences before reuse.
