import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_service import LLMService

class MockSchema:
    @classmethod
    def __init__(cls, **kwargs):
        for key, value in kwargs.items():
            setattr(cls, key, value)

    @classmethod
    def model_json_schema(cls):
        return {"type": "object"}

@pytest.fixture
def llm_service():
    return LLMService()

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_success(mock_client, llm_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": '{"key": "value"}'}}]}
    mock_client.return_value.__enter__.return_value.post.return_value = mock_response
    
    result = llm_service.generate_structured_json("Test prompt", MockSchema)
    assert result.key == "value"

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_cache_hit(mock_client, llm_service):
    cache_data = '{"key": "cached_value"}'
    cache_file = '.deliveryos/cache/llm/some_hash.json'
    with patch('builtins.open', new_callable=MagicMock) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = cache_data
        result = llm_service.generate_structured_json("Test prompt", MockSchema, skip_cache=False)
    assert result.key == "cached_value"

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_api_failure(mock_client, llm_service):
    mock_client.return_value.__enter__.return_value.post.side_effect = Exception("API Error")
    with pytest.raises(ValueError):
        llm_service.generate_structured_json("Test prompt", MockSchema)


import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_service import LLMService

class MockSchema:
    @classmethod
    def __init__(cls, **kwargs):
        for key, value in kwargs.items():
            setattr(cls, key, value)

    @classmethod
    def model_json_schema(cls):
        return {"type": "object"}

@pytest.fixture
def llm_service():
    return LLMService()

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_success(mock_client, llm_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": '{"key": "value"}'}}]}
    mock_client.return_value.__enter__.return_value.post.return_value = mock_response
    
    result = llm_service.generate_structured_json("Test prompt", MockSchema)
    assert result.key == "value"

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_cache_hit(mock_client, llm_service):
    cache_data = '{"key": "cached_value"}'
    cache_file = '.deliveryos/cache/llm/some_hash.json'
    with patch('builtins.open', new_callable=MagicMock) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = cache_data
        result = llm_service.generate_structured_json("Test prompt", MockSchema, skip_cache=False)
    assert result.key == "cached_value"

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_api_failure(mock_client, llm_service):
    mock_client.return_value.__enter__.return_value.post.side_effect = Exception("API Error")
    with pytest.raises(ValueError):
        llm_service.generate_structured_json("Test prompt", MockSchema)

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_skip_cache(mock_client, llm_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": '{"key": "skip_cache_value"}'}}]}
    mock_client.return_value.__enter__.return_value.post.return_value = mock_response

    result = llm_service.generate_structured_json("Test prompt", MockSchema, skip_cache=True)
    assert result.key == "skip_cache_value"


@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_with_empty_prompt(mock_client, llm_service):
    mock_client.return_value.__enter__.return_value.post.return_value.status_code = 200
    mock_client.return_value.__enter__.return_value.post.return_value.json.return_value = {"choices": [{"message": {"content": '{"key": "default_value"}'}}]}

    result = llm_service.generate_structured_json("", MockSchema)
    assert result.key == "default_value"

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_with_invalid_schema(mock_client, llm_service):
    with pytest.raises(TypeError):
        llm_service.generate_structured_json("Test prompt", object)

@patch('app.services.llm_service.httpx.Client')
def test_generate_structured_json_no_cache(mock_client, llm_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": '{"key": "no_cache_value"}'}}]}
    mock_client.return_value.__enter__.return_value.post.return_value = mock_response

    result = llm_service.generate_structured_json("Test prompt", MockSchema, skip_cache=True)
    assert result.key == "no_cache_value"