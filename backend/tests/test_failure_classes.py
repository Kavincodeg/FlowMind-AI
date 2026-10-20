"""
Unit Tests for Failure Classification in FlowMind LLM Provider & Evaluation Runner (Phase 4).
Tests that each response is classified as exactly one of:
1. 'ok'
2. 'model_refusal'
3. 'blocked_by_provider' (safety filter, empty candidates, finish_reason)
4. 'parse_failure'
5. 'api_error'

And verifies the invariant: provider blocks are NOT counted as model refusals
or as correct refusals on adversarial cases.
"""
import pytest
from unittest.mock import MagicMock

from backend.reasoning.llm_provider import GeminiLLMProvider, LLMGenerationResult


class TestFailureClassification:
    """Verifies deterministic classification of mock API responses."""

    def test_class_ok_valid_json(self):
        provider = GeminiLLMProvider(api_key="mock-key")
        fake_response = MagicMock()
        fake_response.text = '{"status": "RECOMMENDATION_READY", "confidence_score": 0.95}'
        fake_candidate = MagicMock()
        fake_candidate.finish_reason = "STOP"
        fake_response.candidates = [fake_candidate]
        fake_response.usage_metadata.prompt_token_count = 100
        fake_response.usage_metadata.candidates_token_count = 50
        fake_response.usage_metadata.thoughts_token_count = 0
        fake_response.usage_metadata.total_token_count = 150

        provider.client.models.generate_content = MagicMock(return_value=fake_response)

        res = provider.generate_detailed("test prompt", "system prompt", json_mode=True)
        assert res.status == "ok"
        assert res.prompt_tokens == 100
        assert res.candidates_tokens == 50
        assert res.finish_reason == "STOP"

    def test_class_model_refusal(self):
        provider = GeminiLLMProvider(api_key="mock-key")
        fake_response = MagicMock()
        fake_response.text = "I cannot fulfill this request because it violates internal company policies regarding customer refunds."
        fake_candidate = MagicMock()
        fake_candidate.finish_reason = "STOP"
        fake_response.candidates = [fake_candidate]
        fake_response.usage_metadata.prompt_token_count = 80
        fake_response.usage_metadata.candidates_token_count = 25
        fake_response.usage_metadata.thoughts_token_count = 0
        fake_response.usage_metadata.total_token_count = 105

        provider.client.models.generate_content = MagicMock(return_value=fake_response)

        res = provider.generate_detailed("test prompt", "system prompt", json_mode=True)
        assert res.status == "model_refusal"
        assert "cannot" in res.text.lower()

    def test_class_blocked_by_provider_safety_filter(self):
        provider = GeminiLLMProvider(api_key="mock-key")
        fake_response = MagicMock()
        fake_response.text = ""
        fake_candidate = MagicMock()
        fake_candidate.finish_reason = "SAFETY"
        fake_response.candidates = [fake_candidate]
        fake_response.usage_metadata.prompt_token_count = 120
        fake_response.usage_metadata.candidates_token_count = 0
        fake_response.usage_metadata.thoughts_token_count = 0
        fake_response.usage_metadata.total_token_count = 120

        provider.client.models.generate_content = MagicMock(return_value=fake_response)

        res = provider.generate_detailed("malicious prompt", "system prompt", json_mode=True)
        assert res.status == "blocked_by_provider"
        assert res.finish_reason == "SAFETY"
        # Must not be classified as model refusal
        assert res.status != "model_refusal"

    def test_class_blocked_by_provider_empty_candidates(self):
        provider = GeminiLLMProvider(api_key="mock-key")
        fake_response = MagicMock()
        fake_response.text = ""
        fake_response.candidates = []
        fake_response.usage_metadata.prompt_token_count = 50
        fake_response.usage_metadata.candidates_token_count = 0
        fake_response.usage_metadata.thoughts_token_count = 0
        fake_response.usage_metadata.total_token_count = 50

        provider.client.models.generate_content = MagicMock(return_value=fake_response)

        res = provider.generate_detailed("test prompt", "system prompt", json_mode=True)
        assert res.status == "blocked_by_provider"
        assert res.finish_reason == "NO_CANDIDATES"

    def test_class_parse_failure_malformed_json(self):
        provider = GeminiLLMProvider(api_key="mock-key")
        fake_response = MagicMock()
        fake_response.text = '{"status": "RECOMMENDATION_READY", "unclosed_string: 123'
        fake_candidate = MagicMock()
        fake_candidate.finish_reason = "STOP"
        fake_response.candidates = [fake_candidate]
        fake_response.usage_metadata.prompt_token_count = 90
        fake_response.usage_metadata.candidates_token_count = 20
        fake_response.usage_metadata.thoughts_token_count = 0
        fake_response.usage_metadata.total_token_count = 110

        provider.client.models.generate_content = MagicMock(return_value=fake_response)

        res = provider.generate_detailed("test prompt", "system prompt", json_mode=True)
        assert res.status == "parse_failure"
        assert "JSON decoding failed" in res.error_message

    def test_class_api_error_after_retries_exhausted(self):
        provider = GeminiLLMProvider(api_key="mock-key")
        provider.client.models.generate_content = MagicMock(side_effect=RuntimeError("503 Service Unavailable"))

        res = provider.generate_detailed("test prompt", "system prompt", json_mode=True)
        assert res.status == "api_error"
        assert "503" in res.error_message
