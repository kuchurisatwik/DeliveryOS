import json
from typing import Type, TypeVar, Any
from google import genai
from pydantic import BaseModel
from app.config.settings import settings
from app.utils.logger import logger

T = TypeVar('T', bound=BaseModel)

class LLMService:
    """Centralized service for interacting with LLM providers (Google Gemini)."""
    
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set. LLM features will fail.")
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)
            
    def generate_structured_json(self, prompt: str, schema: Type[T], primary_model: str = "gemini-2.5-flash") -> T:
        """
        Generates a structured JSON response matching the provided Pydantic schema.
        Falls back to other models if rate limits (429) or availability issues (503) occur.
        
        Args:
            prompt: The instruction and context for the LLM.
            schema: A Pydantic BaseModel class representing the desired output structure.
            primary_model: The preferred Gemini model to use.
            
        Returns:
            An instance of the provided schema class.
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured.")
            
        models_to_try = [primary_model, "gemini-1.5-flash", "gemini-1.5-pro"]
        last_exception = None
        
        for model in models_to_try:
            logger.info(f"Calling LLM ({model}) with structured output requirement...")
            
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                    },
                )
                
                # The response text should be a valid JSON string matching the schema
                json_data = json.loads(response.text)
                return schema(**json_data)
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "503" in error_str or "UNAVAILABLE" in error_str:
                    logger.warning(f"Model {model} hit rate limit or 503. Sleeping for 5 seconds before fallback... Error: {e}")
                    import time
                    time.sleep(5)
                    last_exception = e
                    continue
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    logger.warning(f"Model {model} not found (404). Falling back... Error: {e}")
                    last_exception = e
                    continue
                else:
                    logger.error(f"LLM API call failed with non-rate-limit error: {e}")
                    raise
                    
        raise ValueError(f"All fallback models failed due to rate limits. Last error: {last_exception}")
