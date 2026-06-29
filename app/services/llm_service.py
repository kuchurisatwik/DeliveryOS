import json
import httpx
import hashlib
import os
from typing import Type, TypeVar, Any
from pydantic import BaseModel
from app.config.settings import settings
from app.utils.logger import logger

T = TypeVar('T', bound=BaseModel)

class LLMService:
    """Centralized service for interacting with LLM providers via OpenRouter.
    Fixed to openai/gpt-4o-mini for all calls.
    """
    
    FIXED_MODEL = "google/gemini-2.0-flash-exp:free"
    
    def __init__(self):
        self.openrouter_key = settings.OPENROUTER_API_KEY
        
        if not self.openrouter_key:
            logger.warning("No OPENROUTER_API_KEY is set. LLM features will fail.")
            
    def generate_structured_json(self, prompt: str, schema: Type[T], skip_cache: bool = False) -> T:
        """
        Generates a structured JSON response matching the provided Pydantic schema.
        Uses openai/gpt-4o-mini via OpenRouter with json_object response format.
        """
        cache_dir = os.path.join(os.getcwd(), ".deliveryos", "cache", "llm")
        os.makedirs(cache_dir, exist_ok=True)
        
        prompt_hash = hashlib.sha256((prompt + schema.__name__).encode()).hexdigest()
        cache_file = os.path.join(cache_dir, f"{prompt_hash}.json")
        
        # Skip cache for repair sessions to avoid poisoning iterations
        if not skip_cache and os.path.exists(cache_file):
            logger.info(f"LLM Cache hit for {schema.__name__}.")
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return schema(**data)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                
        result = self._call_openrouter(prompt, schema)
        
        # Only cache non-repair results
        if not skip_cache:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(result.model_dump_json(indent=2))
            except Exception as e:
                logger.warning(f"Failed to write LLM cache: {e}")
            
        return result
            
    def _call_openrouter(self, prompt: str, schema: Type[T]) -> T:
        system_prompt = (
            f"You are a strict JSON data generator. You must respond ONLY with a raw JSON data object "
            f"that satisfies this schema:\n{json.dumps(schema.model_json_schema())}\n\n"
            f"IMPORTANT: DO NOT output the schema definition itself (do not output $defs). "
            f"Output the actual data instance. Do not include any markdown formatting "
            f"(like ```json), commentary, or extra text.\n\n"
            f"CRITICAL CONSTRAINT: If the schema requires a list of files or code blocks (e.g., `generated_files`), "
            f"you MUST fully generate the code and include at least one complete file object in the array. "
            f"DO NOT return an empty list (`[]`) for code artifacts under any circumstances."
        )
        
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Software Delivery Engineer"
        }
        
        model = self.FIXED_MODEL
        logger.info(f"Calling OpenRouter LLM ({model}) with structured output requirement...")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        
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
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            json_data = json.loads(content.strip())
            return schema(**json_data)
            
        except Exception as e:
            logger.error(f"Model {model} failed via OpenRouter. Error: {e}")
            raise ValueError(f"LLM call failed with {model}: {e}")
