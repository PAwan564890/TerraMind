# Analytics and formulas

Evidence: unchanged original `backend/environment/analytics.py`; additions in `insights.py` and `measurements.py`. All calculations use full floating-point values. React rounds display values only. No significance test, attribution or forecast is inferred.

Let valid daily mean temperatures be T, valid daily rainfall amounts R, and inclusive calendar length D = (end − start).days + 1.

| Result | Definition and limitation |
|---|---|
| Period mean temperature | sum(T)/len(T); null when no valid T |
| Period rainfall | sum(R); null when all days missing; zero is valid |
| Warmest/coolest day | maximum/minimum daily mean temperature, not instantaneous extreme |
| Wettest/driest day | maximum/minimum valid daily rainfall |
| Ties | earliest date primary; all tied dates retained in insights |
| Daily thermal variation | daily maximum − daily minimum if both exist |
| Period temperature range | greatest available daily maximum − smallest available daily minimum |
| Day-to-day change | next daily mean − previous daily mean only for adjacent calendar dates; null if either missing |
| Monthly mean | mean of valid daily means in retrieved portion of that calendar month |
| Monthly rainfall | sum of valid rainfall in retrieved portion; never extrapolated to complete month |
| Rainfall distribution | actual daily date/value series, retaining nulls |
| Coverage | valid count, expected D, missing D − valid; inspect per variable |
| Two-point difference | left − right, only for matching dates/timezone/data kind and complete aligned coverage of that metric |
| Warmer/wetter | sign of unrounded difference; exact zero is tie |
| Supplemental period mean | arithmetic mean of valid daily mean humidity or daily mean scalar wind speeds |
| Supplemental extrema | min/max of valid daily means, not hourly extrema |

The original summary product and the new insights product remain separately typed. Partial records can support carefully labelled available-day summaries but cannot establish a fully covered comparison. Short-term descriptive changes do not establish a long-term climate trend. No interpolation, fabricated missing day or observed-station precision is implied.
