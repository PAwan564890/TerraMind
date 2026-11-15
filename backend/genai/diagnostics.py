"""Sanitized diagnostics: a fixed schema, never exception text or provider data."""
import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

log = logging.getLogger('terramind.genai')
CATEGORIES = frozenset({'configuration','rate_limit','authentication','timeout','transport',
    'http_server_error','provider_rejection','malformed_response','structured_output',
    'incomplete_response','grounding_validation','internal_error'})


def reference():
    return uuid.uuid4().hex[:12]


def failure(category, ref, *, status=None, attempt=1, retry=False, delay=None,
            retry_after=None, remaining_requests=None, remaining_tokens=None):
    assert category in CATEGORIES
    # All arguments are locally generated values or parsed numeric metadata.
    # No arbitrary strings from headers, exceptions, response bodies or env.
    log.warning('llm_failure ref=%s category=%s http_status=%s attempt=%d retry=%s '
                'delay_seconds=%s retry_after_seconds=%s remaining_requests=%s remaining_tokens=%s',
                ref, category, status, attempt, retry, delay, retry_after,
                remaining_requests, remaining_tokens)


_private_call = ContextVar('terramind_private_provider_call', default=False)


class _TransportFilter(logging.Filter):
    def filter(self, record):
        return not (_private_call.get() and record.name.startswith(('httpx','httpcore')))


_transport_filter = _TransportFilter()


@contextmanager
def private_transport():
    """Suppress third-party URL/header diagnostics for this provider call only."""
    # Filters stay attached but are inert outside this thread/context. Inspect
    # handlers at entry because API logging setup can replace root handlers.
    loggers = [logging.getLogger()] + [value for name,value in
        list(logging.Logger.manager.loggerDict.items())
        if name.startswith(('httpx','httpcore')) and isinstance(value,logging.Logger)]
    for logger in loggers:
        for handler in logger.handlers:
            if _transport_filter not in handler.filters:
                handler.addFilter(_transport_filter)
    token = _private_call.set(True)
    try:
        yield
    finally:
        _private_call.reset(token)
