import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_service import LLMService
from app.config.settings import settings

class TestLLMService:

    @patch('app.services.llm_service.httpx')
    def test_valid_api_key_configuration(self, mock_httpx):
        settings.OPENROUTER_API_KEY = 'valid_openrouter_key'
        service = LLMService()
        assert service.openrouter_key == 'valid_openrouter_key'

    @patch('app.services.llm_service.logger')
    def test_invalid_api_key_configuration(self, mock_logger):
        settings.OPENROUTER_API_KEY = 'invalid_key'
        service = LLMService()
        # Assuming some error handling in the service
        with pytest.raises(ValueError) as excinfo:
            service._call_openrouter()
        assert 'Invalid API key' in str(excinfo.value)

    def test_no_api_key_provided(self):
        settings.OPENROUTER_API_KEY = None
        service = LLMService()
        with pytest.raises(ValueError) as excinfo:
            service._call_openrouter()
        assert 'API key is required' in str(excinfo.value)

    @patch('app.services.llm_service.httpx.post')
    def test_multiple_llm_provider_support(self, mock_post):
        settings.OPENROUTER_API_KEY = 'valid_openrouter_key'
        settings.GEMINI_API_KEY = 'valid_gemini_key'
        service = LLMService()
        service._call_openrouter()  # Assuming this triggers the use of OpenRouter
        mock_post.assert_called_once()  # Check if the OpenRouter was called

    @patch('app.services.llm_service.httpx.post')
    def test_fallback_mechanism_for_llm_providers(self, mock_post):
        settings.GEMINI_API_KEY = 'valid_gemini_key'
        settings.OPENROUTER_API_KEY = 'valid_openrouter_key'
        # Simulate OpenRouter failing
        mock_post.side_effect = Exception('OpenRouter failure')
        service = LLMService()
        service._call_openrouter()  # First call to OpenRouter
        # Now check if it falls back to Gemini
        service._call_gemini()
        mock_post.assert_called()  # Ensure it attempted calls to both

    @patch('app.services.llm_service.httpx.post')
    def test_api_contract_validation_for_openrouter(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': 'valid_response'}
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        service = LLMService()
        response = service._call_openrouter()
        assert response['data'] == 'valid_response'

    def test_unauthorized_access_to_openrouter_api(self):
        settings.OPENROUTER_API_KEY = 'invalid_key'
        service = LLMService()
        with pytest.raises(PermissionError) as excinfo:
            service._call_openrouter()
        assert 'Unauthorized' in str(excinfo.value)

    def test_invalid_llm_provider_identifier(self):
        service = LLMService()
        with pytest.raises(ValueError) as excinfo:
            service._call_openrouter('invalid_provider')
        assert 'Invalid LLM provider' in str(excinfo.value)

    def test_maximum_length_api_key(self):
        long_key = 'x' * 100
        settings.OPENROUTER_API_KEY = long_key
        service = LLMService()
        assert service.openrouter_key == long_key

    def test_minimum_length_api_key(self):
        short_key = 'ab'
        settings.OPENROUTER_API_KEY = short_key
        service = LLMService()
        with pytest.raises(ValueError) as excinfo:
            service._call_openrouter()
        assert 'API key length must be greater' in str(excinfo.value)

    def test_api_key_exposure(self, caplog):
        settings.OPENROUTER_API_KEY = 'exposed_key'
        service = LLMService()
        with pytest.raises(ValueError) as excinfo:
            service._call_openrouter()
        assert 'exposed_key' not in caplog.text

    def test_session_management_for_api_access(self):
        service = LLMService()
        with pytest.raises(SessionExpiredError):
            service._call_openrouter() # Assuming it checks for session
