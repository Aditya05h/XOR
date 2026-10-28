"""Optional explanations only. Numerical forecasts and simulations never use an LLM."""
import json
from typing import Literal
import httpx
from pydantic import BaseModel, ConfigDict, Field

class EvidenceExplanation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: str = Field(min_length=1, max_length=1200)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    limitation: str = Field(min_length=1, max_length=600)

class ExplanationProvider:
    def __init__(self, settings=None, transport=None):
        self.settings = settings
        self.transport = transport

    def explain(self, evidence: dict[str, str]) -> dict:
        mode = getattr(self.settings, 'llm_provider', 'deterministic')
        fallback = {'source': 'deterministic', 'summary': '; '.join(list(evidence.values())[:3]),
                    'evidence_ids': list(evidence), 'limitation': 'Correlation does not establish physical cause.'}
        if mode == 'deterministic': return fallback
        secret = getattr(self.settings, mode + '_api_key', None)
        key = secret.get_secret_value() if secret else ''
        if not key: return {**fallback, 'fallback_reason': 'Provider credentials unavailable'}
        schema = EvidenceExplanation.model_json_schema()
        prompt = ('Explain only the supplied telemetry evidence. Do not invent causes, numbers, or confirmed outcomes. '
                  'Reference only supplied evidence IDs. Return the requested JSON schema. Evidence: ' + json.dumps(evidence))
        for attempt in range(2):
            try:
                with httpx.Client(timeout=httpx.Timeout(12, connect=5), transport=self.transport) as client:
                    if mode == 'openai':
                        model = getattr(self.settings, 'openai_model', 'gpt-4.1-mini')
                        response = client.post('https://api.openai.com/v1/responses', headers={'Authorization': 'Bearer '+key}, json={
                            'model': model, 'input': prompt, 'max_output_tokens': 1000,
                            'text': {'format': {'type': 'json_schema', 'name': 'evidence_explanation', 'strict': True, 'schema': schema}}})
                        response.raise_for_status()
                        body = response.json()
                        raw = ''.join(c.get('text','') for o in body.get('output',[]) for c in o.get('content',[]) if c.get('type') == 'output_text')
                    elif mode == 'gemini':
                        model = getattr(self.settings, 'gemini_model', 'gemini-2.5-flash')
                        response = client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                            headers={'x-goog-api-key': key}, json={'contents':[{'parts':[{'text':prompt}]}],
                            'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':schema,'maxOutputTokens':1000}})
                        response.raise_for_status()
                        raw = ''.join(p.get('text','') for p in response.json()['candidates'][0]['content']['parts'])
                    else: return {**fallback, 'fallback_reason': 'Unknown provider configuration'}
                result = EvidenceExplanation.model_validate_json(raw)
                if not set(result.evidence_ids).issubset(evidence): raise ValueError('Unknown evidence identifier')
                return {**result.model_dump(), 'source': mode, 'model': model,
                        'limitation': result.limitation + ' Optional model explanation; hypothesis only, not verified causation.'}
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
                if attempt == 1: return {**fallback, 'fallback_reason': 'Provider request or structured-output validation failed after two attempts'}
        return fallback
