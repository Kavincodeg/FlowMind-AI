"""
Tests for OllamaLLMProvider:
  - num_ctx >= 8192 assertion
  - Prompt truncation guard
  - Pydantic schema validation & schema_deviation tracking
  - Memory unload (keep_alive: 0)
  - Zero monetary cost invariant ($0.00)
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel, Field

from backend.reasoning.llm_provider import (
    OllamaLLMProvider,
    PromptTruncationError,
    LLMGenerationResult,
)


class SampleSchema(BaseModel):
    status: str
    confidence: float = Field(ge=0.0, le=1.0)


def test_num_ctx_enforcement():
    """Evaluating protocol requires num_ctx >= 8192."""
    with pytest.raises(ValueError, match="num_ctx must be at least 8192"):
        OllamaLLMProvider(num_ctx=4096)

    # Valid num_ctx
    provider = OllamaLLMProvider(num_ctx=8192)
    assert provider.num_ctx == 8192


def test_zero_cost_invariant():
    """Local provider must strictly accrue $0.00 USD."""
    provider = OllamaLLMProvider()
    assert provider.total_cost_usd == 0.0


@patch("urllib.request.urlopen")
def test_truncation_guard_trips_when_prompt_approaches_ctx(mock_urlopen):
    """Truncation guard must raise PromptTruncationError when prompt_eval_count + num_predict >= num_ctx."""
    # Context is 8192, num_predict is 2048. If prompt is 6500, 6500 + 2048 = 8548 >= 8192 -> triggers guard
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "response": '{"status": "ok"}',
        "prompt_eval_count": 6500,
        "eval_count": 100,
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    provider = OllamaLLMProvider(num_ctx=8192, num_predict=2048)
    with pytest.raises(PromptTruncationError, match="PROMPT TRUNCATION GUARD TRIGGERED"):
        provider.generate_detailed("Long prompt that approaches context ceiling")

    assert provider.truncation_guard_trips == 1


@patch("urllib.request.urlopen")
def test_truncation_guard_passes_when_within_context(mock_urlopen):
    """Truncation guard passes safely when well within context."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "response": '{"status": "APPROVED", "confidence": 0.95}',
        "prompt_eval_count": 500,
        "eval_count": 50,
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    provider = OllamaLLMProvider(num_ctx=8192, num_predict=2048)
    res = provider.generate_detailed("Short prompt", response_schema=SampleSchema)
    assert res.status == "ok"
    assert provider.truncation_guard_trips == 0
    assert provider.schema_deviation_count == 0


@patch("urllib.request.urlopen")
def test_schema_deviation_detection(mock_urlopen):
    """Pydantic schema validation failures increment schema_deviation_count and return parse_failure."""
    # Returns confidence out of bounds (1.5 > 1.0)
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "response": '{"status": "APPROVED", "confidence": 1.5}',
        "prompt_eval_count": 100,
        "eval_count": 20,
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    provider = OllamaLLMProvider(num_ctx=8192, num_predict=2048)
    res = provider.generate_detailed("Validate schema", response_schema=SampleSchema)
    assert res.status == "parse_failure"
    assert provider.schema_deviation_count == 1
    assert "Schema validation error" in res.error_message


@patch("urllib.request.urlopen")
def test_unload_evicts_model_with_keep_alive_zero(mock_urlopen):
    """unload() sends keep_alive: 0 to Ollama."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    provider = OllamaLLMProvider(model="llama3.1:8b")
    success = provider.unload()
    assert success is True
    # Verify request payload
    called_req = mock_urlopen.call_args[0][0]
    payload = json.loads(called_req.data.decode("utf-8"))
    assert payload.get("keep_alive") == 0
    assert payload.get("model") == "llama3.1:8b"
