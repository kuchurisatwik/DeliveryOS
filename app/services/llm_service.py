import json
import httpx
import hashlib
import os
from typing import Type, TypeVar
from pydantic import BaseModel
from app.config.settings import settings
from app.utils.logger import logger

T = TypeVar('T', bound=BaseModel)

class LLMService:
    """Centralized service for interacting with LLM providers (OpenRouter or Google Gemini)."""
    
    def __init__(self):
        self.openrouter_key = settings.OPENROUTER_API_KEY
        self.gemini_key = settings.GEMINI_API_KEY
        
        if not self.openrouter_key and not self.gemini_key:
            logger.warning("No LLM API keys are set. LLM features will fail.")
            
    def generate_structured_json(self, prompt: str, schema: Type[T], primary_model: str = "google/gemini-2.5-flash") -> T:
        """
        Generates a structured JSON response matching the provided Pydantic schema.
        Falls back to other models if rate limits or availability issues occur.
        """
        cache_dir = os.path.join(os.getcwd(), ".deliveryos", "cache", "llm")
        os.makedirs(cache_dir, exist_ok=True)
        
        prompt_hash = hashlib.sha256((prompt + schema.__name__).encode()).hexdigest()
        cache_file = os.path.join(cache_dir, f"{prompt_hash}.json")
        
        if os.path.exists(cache_file):
            logger.info(f"LLM Cache hit for {schema.__name__}.")
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return schema(**data)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                
        result = None
        if self.openrouter_key:
            # If the caller passed a raw gemini model name, map it to openrouter syntax
            if not primary_model.startswith("google/"):
                primary_model = f"google/{primary_model}"
            result = self._call_openrouter(prompt, schema, primary_model)
        elif self.gemini_key:
            # If the caller passed an openrouter model name, strip the prefix
            if primary_model.startswith("google/"):
                primary_model = primary_model.split("/")[-1]
            result = self._call_gemini(prompt, schema, primary_model)
        else:
            raise ValueError("No LLM API keys are configured.")
            
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=2))
        except Exception as e:
            logger.warning(f"Failed to write LLM cache: {e}")
            
        return result
            
    def _call_openrouter(self, prompt: str, schema: Type[T], primary_model: str) -> T:
        # Enforce structured output via system prompt and json schema mapping
        system_prompt = f"You are a strict JSON generator. You must respond ONLY with raw JSON matching this exact schema:\n{json.dumps(schema.model_json_schema())}\nDo not include any markdown formatting (like ```json), commentary, or extra text."
        
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Software Delivery Engineer"
        }
        
        # OpenRouter fallback sequence across multiple providers
        models_to_try = [
            primary_model, 
            "openai/gpt-4o-mini",
            "anthropic/claude-3-haiku",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemini-2.0-flash-lite-preview-02-05:free"
        ]
        
        last_exception = None
        
        for model in models_to_try:
            logger.info(f"Calling OpenRouter LLM ({model}) with structured output requirement...")
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            }
            
            # Only add response_format if it's an OpenAI model, as many OpenRouter models reject it with 400
            if "openai/" in model or "gpt" in model:
                payload["response_format"] = {"type": "json_object"}
            
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                    response.raise_for_status()
                    
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Clean up any potential markdown block wrappers if the model disobeyed
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                    
                json_data = json.loads(content.strip())
                return schema(**json_data)
                
            except Exception as e:
                logger.warning(f"Model {model} failed via OpenRouter. Error: {e}")
                last_exception = e
                import time
                time.sleep(2)
                continue
                
        raise ValueError(f"All fallback models failed on OpenRouter. Last error: {last_exception}")

    def _call_gemini(self, prompt: str, schema: Type[T], primary_model: str) -> T:
        from google import genai
        client = genai.Client(api_key=self.gemini_key)
        
        models_to_try = [primary_model, "gemini-1.5-flash", "gemini-1.5-pro"]
        last_exception = None
        
        for model in models_to_try:
            logger.info(f"Calling Gemini LLM ({model}) with structured output requirement...")
            
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                    },
                )
                
                json_data = json.loads(response.text)
                return schema(**json_data)
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "503" in error_str:
                    logger.warning(f"Model {model} hit rate limit or 503. Sleeping... Error: {e}")
                    import time
                    time.sleep(5)
                    last_exception = e
                    continue
                else:
                    logger.warning(f"Model {model} failed. Falling back... Error: {e}")
                    last_exception = e
                    continue
                    
        raise ValueError(f"All fallback models failed due to rate limits. Last error: {last_exception}")
