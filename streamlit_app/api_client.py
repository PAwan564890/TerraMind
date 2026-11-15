"""Only HTTP transport and workflow sequencing. No backend logic imported."""
import httpx


class APIError(Exception):
    pass


class APIClient:
    def __init__(self, base_url, transport=None):
        self.base_url = base_url.rstrip('/')
        self.transport = transport

    def request(self, method, path, **kwargs):
        try:
            # Up to three sequential provider calls can take 60 seconds.
            with httpx.Client(base_url=self.base_url, timeout=100, transport=self.transport) as client:
                response = client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 503:
                raise APIError('Trained NLP is unavailable. Check /health and restore checkpoints, or explicitly select rule demonstration.') from error
            if error.response.status_code == 404:
                raise APIError('Presentation route unavailable. Start backend.presentation.app and enable demo explicitly if needed.') from error
            raise APIError(f'Backend rejected the request (HTTP {error.response.status_code}). Check the input and API documentation.') from error
        except (httpx.HTTPError, ValueError) as error:
            raise APIError('Cannot reach a valid FastAPI response. Start the backend and check TERRAMIND_API_URL.') from error

    def health(self):
        return self.request('GET', '/health')

    def system(self):
        return self.request('GET', '/system')

    def run(self, query, session_id, mode, source_mode, explanation_language=None):
        if mode not in ('trained', 'demo') or source_mode not in ('live', 'snapshot'):
            raise APIError('Unknown inference or data mode.')
        analysis = self.request('POST', '/demo/analyze' if mode == 'demo' else '/nlp/analyze',
                                json={'query': query, 'session_id': session_id})
        environment = explanation = context_id = None
        if analysis['status'] == 'ok' and analysis.get('structured_query'):
            bundle = self.request('POST', '/environment/session',
                json={'query': analysis['structured_query'], 'source_mode': source_mode,
                      'session_id': session_id,
                      'language': explanation_language or analysis['language']['code']})
            environment, explanation, context_id = bundle['environment'], bundle['explanation'], bundle['context_id']
        return {'analysis': analysis, 'environment': environment, 'explanation': explanation,
                'context_id': context_id, 'mode': mode,
                'source_mode': source_mode, 'question': query}

    def explain(self, session_id, context_id, question, language):
        return self.request('POST', '/genai/explain', json={'session_id':session_id,
            'context_id':context_id, 'question':question, 'language':language})
