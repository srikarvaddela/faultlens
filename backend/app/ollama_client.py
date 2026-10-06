"""Native Ollama API, restricted to a loopback server and installed local models."""
import os
from urllib.parse import urlparse

import httpx


class OllamaError(Exception):
    pass


def base_url():
    value = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
    parsed = urlparse(value)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise OllamaError('Ollama URL must be an HTTP loopback address')
    return value


def request(path, data=None, timeout=5):
    try:
        with httpx.Client(base_url=base_url(), timeout=timeout, trust_env=False, follow_redirects=False) as client:
            response = client.get(path) if data is None else client.post(path, json=data)
            if response.status_code >= 400:
                raise OllamaError(f'Ollama returned HTTP {response.status_code}')
            payload = response.json()
            if not isinstance(payload, dict):
                raise OllamaError('Unexpected Ollama response')
            return payload
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError('Ollama connection failed or timed out') from exc


def inventory():
    tags = request('/api/tags')
    version = request('/api/version').get('version')
    models = []
    for model in tags.get('models', []):
        name = model.get('name', '')
        if not isinstance(name, str) or not name or 'cloud' in name.lower() or model.get('remote_model') or model.get('remote_host'):
            continue
        if not isinstance(model.get('digest'), str) or not model['digest']:
            continue
        models.append({key: model.get(key) for key in ('name', 'digest', 'size', 'details')})
    return {'connected': True, 'models': models, 'server_version': version}


def build_request(model, messages, options, final, source_lines, file_lines=None):
    payload = {'model': model, 'messages': messages, 'stream': False, 'options': options, 'keep_alive': '5m'}
    if final:
        payload['format'] = {
            'type': 'object', 'properties': {'candidates': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {'type': 'object', 'properties': {'line': {'type': 'integer', 'minimum': 1, 'maximum': source_lines}, 'reason': {'type': 'string'}}, 'required': ['line', 'reason'], 'additionalProperties': False}}},
            'required': ['candidates'], 'additionalProperties': False,
        }
        if file_lines:
            candidate = payload['format']['properties']['candidates']['items']
            candidate['properties']['file'] = {'type': 'string', 'enum': list(file_lines)}
            candidate['properties']['line']['maximum'] = max(file_lines.values())
            candidate['required'].append('file')
    return payload


def chat(payload):
    return request('/api/chat', payload, timeout=180)
