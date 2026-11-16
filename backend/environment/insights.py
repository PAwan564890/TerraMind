"""Descriptive insights from validated rows. No interpolation or climate claims."""
from itertools import combinations
from statistics import fmean

FIELDS = {'temperature_mean_c':'°C','temperature_min_c':'°C','temperature_max_c':'°C','rainfall_mm':'mm','precipitation_mm':'mm'}


def temporal(weather):
    rows=sorted(weather.daily,key=lambda r:r.date)
    expected=(weather.end-weather.start).days+1
    coverage={field:{'valid':sum(getattr(r,field) is not None for r in rows),'missing':expected-sum(getattr(r,field) is not None for r in rows),'expected':expected} for field in FIELDS}
    def extremes(field):
        available=[r for r in rows if getattr(r,field) is not None]
        if not available:return {'highest':None,'lowest':None,'unit':FIELDS[field]}
        def event(value):
            dates=[r.date.isoformat() for r in available if getattr(r,field)==value]
            return {'value':value,'date':dates[0],'tied_dates':dates}
        return {'highest':event(max(getattr(r,field) for r in available)),'lowest':event(min(getattr(r,field) for r in available)),'unit':FIELDS[field]}
    changes=[]
    for left,right in zip(rows,rows[1:]):
        if (right.date-left.date).days==1:
            changes.append({'date':right.date.isoformat(),'previous_date':left.date.isoformat(),'temperature_mean_change_c':right.temperature_mean_c-left.temperature_mean_c if left.temperature_mean_c is not None and right.temperature_mean_c is not None else None})
    variation=[{'date':r.date.isoformat(),'temperature_range_c':r.temperature_max_c-r.temperature_min_c if r.temperature_max_c is not None and r.temperature_min_c is not None else None} for r in rows]
    months={}
    for r in rows:months.setdefault(r.date.strftime('%Y-%m'),[]).append(r)
    monthly=[]
    for month,part in months.items():
        means=[r.temperature_mean_c for r in part if r.temperature_mean_c is not None];rain=[r.rainfall_mm for r in part if r.rainfall_mm is not None]
        monthly.append({'month':month,'retrieved_days':len(part),'temperature_valid_days':len(means),'rainfall_valid_days':len(rain),'temperature_mean_c':fmean(means) if means else None,'rainfall_total_mm':sum(rain) if rain else None,'period_start':part[0].date.isoformat(),'period_end':part[-1].date.isoformat(),'label':'Retrieved portion of calendar month; not necessarily a complete month'})
    low=[r.temperature_min_c for r in rows if r.temperature_min_c is not None];high=[r.temperature_max_c for r in rows if r.temperature_max_c is not None]
    return {'location_id':weather.location_id,'location_name':weather.location_name,'start':str(weather.start),'end':str(weather.end),'timezone':weather.timezone,'temperature_days':extremes('temperature_mean_c'),'rainfall_days':extremes('rainfall_mm'),'period_temperature_range_c':max(high)-min(low) if low and high else None,'daily_variation':variation,'day_to_day':changes,'rainfall_distribution':[{'date':str(r.date),'rainfall_mm':r.rainfall_mm} for r in rows],'coverage':coverage,'monthly':monthly,'tie_rule':'Earliest date is primary; all tied dates listed. Warmest/coolest use daily mean, wettest/driest use daily rainfall. Zero rainfall is a valid dry day.','limitation':'Available grid estimates only. Missing values are not zero; extrema may miss unobserved days. No significance, causal attribution or long-term climate trend is inferred.'}


def comparisons(results):
    output=[]
    for left,right in combinations(results,2):
        same=(left.start,left.end,left.timezone,left.data_kind)==(right.start,right.end,right.timezone,right.data_kind)
        expected_days=(left.end-left.start).days+1
        same=same and len(left.daily)==len(right.daily)==expected_days and [r.date for r in left.daily]==[r.date for r in right.daily]
        row={'left':left.location_id,'right':right.location_id,'left_name':left.location_name,'right_name':right.location_name,'start':str(left.start),'end':str(left.end),'temperature_difference_c':None,'rainfall_difference_mm':None,'warmer':None,'wetter':None,'warnings':[]}
        for field,metric,key,winner in [('temperature_mean_c','temperature_mean_c','temperature_difference_c','warmer'),('rainfall_mm','rainfall_total_mm','rainfall_difference_mm','wetter')]:
            a=[getattr(r,field) for r in left.daily];b=[getattr(r,field) for r in right.daily]
            row[field+'_coverage']={left.location_id:sum(v is not None for v in a),right.location_id:sum(v is not None for v in b)}
            if not same or not a or not b or len(a)!=len(b) or None in a or None in b:
                row['warnings'].append('Comparison unavailable for '+field+': periods, definitions or complete coverage differ.');continue
            delta=(fmean(a)-fmean(b)) if field=='temperature_mean_c' else sum(a)-sum(b)
            row[key]=delta;row[winner]=left.location_id if delta>0 else right.location_id if delta<0 else 'tie'
        labels={left.location_id:left.location_name,right.location_id:right.location_name,'tie':'Tie'}
        row['warmer_name']=labels.get(row['warmer'])
        row['wetter_name']=labels.get(row['wetter'])
        output.append(row)
    return output
