"""Bounded OpenAI-compatible client with sanitized diagnostics and safe retries."""
import json
import math
import os
import random
import re
import time
from dataclasses import dataclass, field
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx
from backend.genai import diagnostics

_MESSAGES = {
    'configuration':'LLM provider is not configured.',
    'rate_limit':'LLM provider rate limit reached.',
    'authentication':'LLM provider authentication/authorization failed.',
    'timeout':'LLM provider timed out.',
    'transport':'LLM provider transport failed.',
    'http_server_error':'LLM provider failed with a server error.',
    'provider_rejection':'LLM provider rejected the request.',
    'malformed_response':'LLM provider returned a malformed response.',
    'structured_output':'LLM provider failed structured-output generation.',
    'incomplete_response':'LLM provider returned an incomplete response.',
}
_TRANSIENT = {429, 500, 502, 503, 504}
_STRUCTURED_CODES = {'json_validate_failed','json_schema_validation_failed','structured_output_validation_failed'}
_RETRY_BUDGET = 35.0  # admission budget across attempts and waits, not a new paid retry loop


class ProviderError(Exception):
    """Static public details only; no underlying exception/body is exposed."""
    def __init__(self, code, *, status=None, retryable=False, retry_after=None,
                 remaining_requests=None, remaining_tokens=None):
        self.code = code
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after
        self.remaining_requests = remaining_requests
        self.remaining_tokens = remaining_tokens
        self.attempts = 1
        self.reference = None
        super().__init__(_MESSAGES[code])

    def __str__(self):
        detail = f'code={self.code}; attempts={self.attempts}'
        if self.status is not None: detail += f'; HTTP={self.status}'
        if self.reference: detail += f'; ref={self.reference}'
        if self.retry_after is not None: detail += f'; retry_after_seconds={self.retry_after:g}'
        return f'{_MESSAGES[self.code]} [{detail}] Environmental results remain available.'


def _float_env(name, default, low, high):
    try: value = float(os.getenv(name, str(default)))
    except ValueError: return default
    return value if math.isfinite(value) and low <= value <= high else default


@dataclass(frozen=True)
class LLMConfig:
    provider: str = 'disabled'
    model: str = ''
    base_url: str = ''
    api_key: str = field(default='', repr=False)
    timeout: float = 15.0
    max_attempts: int = 2
    retry_max_wait: float = 5.0

    @classmethod
    def from_env(cls):
        provider = os.getenv('TERRAMIND_LLM_PROVIDER', 'disabled').strip()
        try: attempts = int(os.getenv('TERRAMIND_LLM_MAX_ATTEMPTS','2'))
        except ValueError: attempts = 2
        if not 1 <= attempts <= 3: attempts = 2
        return cls(provider=provider, model=os.getenv('TERRAMIND_LLM_MODEL', '').strip(),
            base_url=os.getenv('TERRAMIND_LLM_BASE_URL', 'https://api.openai.com/v1' if provider == 'openai' else '').rstrip('/'),
            api_key=os.getenv('TERRAMIND_LLM_API_KEY') or (os.getenv('OPENAI_API_KEY', '') if provider == 'openai' else ''),
            timeout=_float_env('TERRAMIND_LLM_TIMEOUT_SECONDS',15.0,1,30),
            max_attempts=attempts,
            retry_max_wait=_float_env('TERRAMIND_LLM_RETRY_MAX_WAIT_SECONDS',5.0,0,15))

    @property
    def configured(self):
        try: url = urlsplit(self.base_url)
        except ValueError: return False
        safe = url.scheme == 'https' or (url.scheme == 'http' and url.hostname in ('127.0.0.1','localhost','::1'))
        return bool(self.provider in ('openai','openai_compatible') and self.model and self.api_key
                    and safe and url.hostname and not url.username and not url.password
                    and not url.query and not url.fragment)


def _remaining(headers, name):
    raw = headers.get(name,'')
    return int(raw) if re.fullmatch(r'\d{1,10}',raw) else None


def _duration(raw):
    # Groq reset durations, e.g. 2m59.56s, 7.66s. Never log the raw header.
    matches = list(re.finditer(r'(\d+(?:\.\d+)?)(ms|s|m|h)',raw))
    if not matches or ''.join(m.group() for m in matches) != raw: return None
    value = sum(float(m[1])*{'ms':.001,'s':1,'m':60,'h':3600}[m[2]] for m in matches)
    return value if math.isfinite(value) else None


def retry_guidance(headers, now):
    raw = headers.get('retry-after','')[:128]
    if raw:
        try:
            value = float(raw)
            if math.isfinite(value) and value >= 0: return value
        except ValueError: pass
        try:
            stamp = parsedate_to_datetime(raw)
            if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=timezone.utc)
            return max(0.0,stamp.timestamp()-now)
        except (ValueError,TypeError,OverflowError): pass
    waits = []
    for kind in ('requests','tokens'):
        if _remaining(headers,'x-ratelimit-remaining-'+kind) == 0:
            value = _duration(headers.get('x-ratelimit-reset-'+kind,'')[:128])
            if value is not None: waits.append(value)
    return max(waits) if waits else None


class OpenAICompatibleClient:
    def __init__(self, config=None, transport=None, *, sleep=None, clock=None,
                 wall_clock=None, jitter=None):
        self.config = config or LLMConfig.from_env()
        self.transport = transport
        self.sleep = sleep or time.sleep
        self.clock = clock or time.monotonic
        self.wall_clock = wall_clock or time.time
        self.jitter = jitter or (lambda: random.uniform(0,.25))

    def _attempt(self, body, remaining):
        try:
            timeout = min(self.config.timeout,remaining)
            with diagnostics.private_transport(), httpx.Client(timeout=httpx.Timeout(timeout,connect=min(5,timeout)),
                              transport=self.transport,follow_redirects=False,trust_env=False) as client:
                with client.stream('POST',self.config.base_url+'/chat/completions',
                        headers={'Authorization':'Bearer '+self.config.api_key},json=body) as response:
                    status = response.status_code
                    info = dict(status=status,retry_after=retry_guidance(response.headers,self.wall_clock()),
                        remaining_requests=_remaining(response.headers,'x-ratelimit-remaining-requests'),
                        remaining_tokens=_remaining(response.headers,'x-ratelimit-remaining-tokens'))
                    if status in (401,403): raise ProviderError('authentication',**info)
                    if status == 408: raise ProviderError('timeout',**info)
                    if status == 429: raise ProviderError('rate_limit',retryable=True,**info)
                    if status >= 500: raise ProviderError('http_server_error',retryable=status in _TRANSIENT,**info)
                    chunks,size = [],0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 65536: raise ProviderError('malformed_response',status=status)
                        chunks.append(chunk)
                    try: payload = json.loads(b''.join(chunks))
                    except (ValueError,UnicodeError):
                        raise ProviderError('malformed_response' if status < 300 else 'provider_rejection',**info) from None
                    if not isinstance(payload,dict): raise ProviderError('malformed_response',status=status)
                    provider_error = payload.get('error')
                    if status >= 300 or provider_error:
                        code = provider_error.get('code') if isinstance(provider_error,dict) else None
                        category = 'structured_output' if isinstance(code,str) and code in _STRUCTURED_CODES else 'provider_rejection'
                        raise ProviderError(category,**info)
            choices = payload.get('choices')
            if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):
                raise ProviderError('malformed_response',status=status)
            choice = choices[0];message = choice.get('message')
            if not isinstance(message,dict): raise ProviderError('malformed_response',status=status)
            if message.get('refusal') or choice.get('finish_reason') in ('content_filter','tool_calls'):
                raise ProviderError('provider_rejection',status=status)
            if choice.get('finish_reason') == 'length': raise ProviderError('incomplete_response',status=status)
            content = message.get('content')
            if choice.get('finish_reason') != 'stop' or not isinstance(content,str) or len(content)>16000:
                raise ProviderError('malformed_response',status=status)
            return content
        except httpx.DecodingError:
            raise ProviderError('malformed_response') from None
        except httpx.InvalidURL:
            raise ProviderError('configuration') from None
        except httpx.TimeoutException as error:
            # A read/write timeout may have consumed provider tokens already.
            raise ProviderError('timeout',retryable=isinstance(error,httpx.ConnectTimeout)) from None
        except httpx.TransportError as error:
            raise ProviderError('transport',retryable=isinstance(error,httpx.ConnectError)) from None

    def generate(self, system: str, request: dict) -> str:
        ref = diagnostics.reference()
        if not self.config.configured: raise ProviderError('configuration')
        body = {'model':self.config.model,'temperature':0,'max_tokens':1800,
            'response_format':{'type':'json_object'},'messages':[
                {'role':'system','content':system},
                {'role':'user','content':json.dumps(request,ensure_ascii=False)}]}
        started = self.clock()
        attempts = max(1,min(3,self.config.max_attempts))
        for attempt in range(1,attempts+1):
            try:
                remaining = _RETRY_BUDGET-(self.clock()-started)
                if remaining <= 0: raise ProviderError('timeout')
                content = self._attempt(body,remaining)
                if attempt > 1:
                    diagnostics.log.info('llm_recovered ref=%s attempt=%d',ref,attempt)
                return content
            except ProviderError as error:
                error.reference,error.attempts = ref,attempt
                delay = error.retry_after if error.retry_after is not None else .5*2**(attempt-1)+self.jitter()
                allowed_wait = max(0,min(15,self.config.retry_max_wait))
                will_retry = (error.retryable and attempt < attempts and delay <= allowed_wait
                              and self.clock()-started+delay+1 <= _RETRY_BUDGET)
                diagnostics.failure(error.code,ref,status=error.status,attempt=attempt,retry=will_retry,
                    delay=delay if will_retry else None,retry_after=error.retry_after,
                    remaining_requests=error.remaining_requests,remaining_tokens=error.remaining_tokens)
                if not will_retry: raise error from None
                self.sleep(delay)
