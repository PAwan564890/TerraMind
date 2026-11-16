"""Idempotent GET only, two attempts, bounded waits, no bodies/URLs in logs."""
import logging
import math
import time
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import httpx

log=logging.getLogger('terramind.environment')


class RetrievalFailure(Exception):
    def __init__(self,code,status=None,attempts=1,retry_after=None):
        self.code,self.status,self.attempts,self.retry_after=code,status,attempts,retry_after
        super().__init__(f'Open-Meteo unavailable [code={code}; attempts={attempts}'+(f'; http={status}' if status else '')+(f'; retry_after_seconds={retry_after:g}' if retry_after is not None else '')+']. No substitute data were used.')


def get_json(endpoint,params,transport=None,sleep=time.sleep):
    started=time.monotonic()
    for attempt in (1,2):
        code=None;status=None;delay=.25;guidance=None
        try:
            with httpx.Client(timeout=httpx.Timeout(max(.1,20-(time.monotonic()-started)),connect=min(8,max(.1,20-(time.monotonic()-started)))),transport=transport) as client:
                response=client.get(endpoint,params=params)
            status=response.status_code
            if response.is_success:
                try:
                    if len(response.content)>2*1024*1024:raise ValueError('oversize')
                    payload=response.json()
                    if isinstance(payload,dict) and payload.get('error'):
                        raise RetrievalFailure('provider_rejection',status,attempt)
                    return payload,str(response.url)
                except ValueError:code='invalid_response'
            elif status==429:code='rate_limit'
            elif status>=500:code='provider_error'
            else:code='provider_rejection'
            if response.headers.get('retry-after'):
                raw=response.headers['retry-after']
                try:guidance=float(raw)
                except ValueError:
                    try:guidance=(parsedate_to_datetime(raw)-datetime.now(timezone.utc)).total_seconds()
                    except (ValueError,TypeError,OverflowError):pass
                if guidance is not None and math.isfinite(guidance):delay=max(0,guidance)
                else:guidance=None
        except httpx.DecodingError:code='invalid_response'
        except httpx.TimeoutException:code='timeout'
        except httpx.TransportError:code='transport'
        transient=code in ('rate_limit','timeout','transport') or (code=='provider_error' and status in (500,502,503,504))
        retry=transient and attempt<2 and delay<=2 and time.monotonic()-started+delay<20
        log.warning('weather_failure code=%s status=%s attempt=%s retry=%s',code,status,attempt,retry)
        if retry:sleep(delay);continue
        raise RetrievalFailure(code,status,attempt,max(0,guidance) if guidance is not None else None)
