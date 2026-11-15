"""Small Chat Completions client. No SDK, retries, logging or secret exposure."""
import json
import math
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx


class ProviderError(Exception):
    """Safe public error; never contains provider bodies, prompts or credentials."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str = 'disabled'
    model: str = ''
    base_url: str = ''
    api_key: str = field(default='', repr=False)
    timeout: float = 15.0

    @classmethod
    def from_env(cls):
        provider = os.getenv('TERRAMIND_LLM_PROVIDER', 'disabled').strip()
        try:
            timeout = float(os.getenv('TERRAMIND_LLM_TIMEOUT_SECONDS', '15'))
        except ValueError:
            timeout = 15.0
        if not math.isfinite(timeout) or not 1 <= timeout <= 30:
            timeout = 15.0
        return cls(provider=provider, model=os.getenv('TERRAMIND_LLM_MODEL', '').strip(),
            base_url=os.getenv('TERRAMIND_LLM_BASE_URL', 'https://api.openai.com/v1' if provider == 'openai' else '').rstrip('/'),
            api_key=os.getenv('TERRAMIND_LLM_API_KEY') or (os.getenv('OPENAI_API_KEY', '') if provider == 'openai' else ''),
            timeout=timeout)

    @property
    def configured(self):
        try:
            url = urlsplit(self.base_url)
        except ValueError:
            return False
        # HTTPS for remote providers; HTTP only for explicit local development.
        safe = url.scheme == 'https' or (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost', '::1'))
        return bool(self.provider in ('openai', 'openai_compatible') and self.model and self.api_key
                    and safe and url.hostname and not url.username and not url.password
                    and not url.query and not url.fragment)


class OpenAICompatibleClient:
    def __init__(self, config=None, transport=None):
        self.config = config or LLMConfig.from_env()
        self.transport = transport

    def generate(self, system: str, request: dict) -> str:
        if not self.config.configured:
            raise ProviderError('LLM provider is not configured.')
        body = {'model': self.config.model, 'temperature': 0,
                'max_tokens': 1800, 'response_format': {'type': 'json_object'},
                'messages': [{'role':'system', 'content':system},
                             {'role':'user', 'content':json.dumps(request, ensure_ascii=False)}]}
        try:
            with httpx.Client(timeout=httpx.Timeout(self.config.timeout, connect=min(5, self.config.timeout)),
                              transport=self.transport, follow_redirects=False, trust_env=False) as client:
                # Stream only to bound response memory; the completion itself is non-streaming JSON.
                with client.stream('POST', self.config.base_url + '/chat/completions',
                        headers={'Authorization':'Bearer ' + self.config.api_key}, json=body) as response:
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 65536:
                            raise ProviderError('LLM response exceeded the size limit.')
                        chunks.append(chunk)
                    payload = json.loads(b''.join(chunks))
            choice = payload['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ProviderError('LLM returned an incomplete response.')
            content = choice['message']['content']
            if not isinstance(content, str) or len(content) > 16000:
                raise ProviderError('LLM response format was invalid.')
            return content
        except httpx.TimeoutException as error:
            raise ProviderError('LLM provider timed out; environmental results remain available.') from error
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
            raise ProviderError('LLM provider failed; environmental results remain available.') from error
