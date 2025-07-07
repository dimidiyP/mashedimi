#!/usr/bin/env python3
"""
Надежная система интеграции с OpenAI API
Реализует лучшие практики для продакшн-среды:
- Exponential backoff retry
- Circuit breaker pattern
- Rate limiting
- Timeout management
- Comprehensive error handling
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
import openai
from openai import AsyncOpenAI
import json

logger = logging.getLogger(__name__)

class CircuitBreakerState(Enum):
    CLOSED = "closed"    # Normal operation
    OPEN = "open"        # Failing, all requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered

class OpenAIReliabilityManager:
    """Менеджер надежности для OpenAI API с circuit breaker и retry логикой"""
    
    def __init__(self):
        # Circuit breaker settings
        self.failure_threshold = 5  # Failures before opening circuit
        self.recovery_timeout = 60  # Seconds before trying to recover
        self.success_threshold = 3  # Successes needed to close circuit
        
        # Current state
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        
        # Rate limiting
        self.request_count = 0
        self.request_window_start = time.time()
        self.max_requests_per_minute = 50  # Conservative limit
        
        # Retry settings
        self.max_retries = 3
        self.base_delay = 1  # Base delay in seconds
        self.max_delay = 16  # Maximum delay in seconds
        
        # Timeout settings
        self.default_timeout = 30  # seconds
        
    def _should_allow_request(self) -> bool:
        """Проверить, можно ли выполнить запрос (circuit breaker logic)"""
        current_time = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if current_time - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker moving to HALF_OPEN state")
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def _is_rate_limited(self) -> bool:
        """Проверить rate limiting"""
        current_time = time.time()
        
        # Reset window if needed
        if current_time - self.request_window_start > 60:
            self.request_count = 0
            self.request_window_start = current_time
        
        return self.request_count >= self.max_requests_per_minute
    
    def _record_success(self):
        """Записать успешный запрос"""
        self.failure_count = 0
        self.request_count += 1
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                logger.info("Circuit breaker CLOSED - service recovered")
    
    def _record_failure(self):
        """Записать неудачный запрос"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker OPEN - too many failures ({self.failure_count})")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker back to OPEN - test request failed")
    
    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Выполнить функцию с exponential backoff retry"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Rate limiting check
                if self._is_rate_limited():
                    wait_time = 60 - (time.time() - self.request_window_start)
                    logger.warning(f"Rate limited, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    self.request_count = 0
                    self.request_window_start = time.time()
                
                # Circuit breaker check
                if not self._should_allow_request():
                    raise Exception("Circuit breaker is OPEN - service unavailable")
                
                # Execute the function
                result = await func(*args, **kwargs)
                self._record_success()
                return result
                
            except openai.RateLimitError as e:
                last_exception = e
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(f"Rate limit hit, attempt {attempt + 1}, waiting {delay}s")
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    
            except openai.APITimeoutError as e:
                last_exception = e
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(f"Timeout error, attempt {attempt + 1}, waiting {delay}s")
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    
            except openai.APIConnectionError as e:
                last_exception = e
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(f"Connection error, attempt {attempt + 1}, waiting {delay}s")
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    
            except openai.InternalServerError as e:
                last_exception = e
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(f"Server error, attempt {attempt + 1}, waiting {delay}s")
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_exception = e
                # Don't retry for unknown errors
                break
        
        # All retries failed
        self._record_failure()
        raise last_exception

class ReliableOpenAIClient:
    """Надежный клиент для OpenAI API с улучшенной обработкой ошибок"""
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=30.0,  # 30 second timeout
            max_retries=0   # We handle retries ourselves
        )
        self.reliability_manager = OpenAIReliabilityManager()
        
    async def _create_completion(self, **kwargs):
        """Внутренний метод для создания completion"""
        return await self.client.chat.completions.create(**kwargs)
        
    async def safe_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-3.5-turbo",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Безопасное создание chat completion с надежной обработкой ошибок
        
        Returns:
            dict: {
                "success": bool,
                "response": openai.Response | None,
                "error": str | None,
                "error_type": str | None
            }
        """
        try:
            # Prepare completion parameters
            completion_params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                **kwargs
            }
            
            if max_tokens:
                completion_params["max_tokens"] = max_tokens
                
            if tools:
                completion_params["tools"] = tools
                completion_params["tool_choice"] = tool_choice
            
            # Execute with retry logic
            response = await self.reliability_manager._retry_with_backoff(
                self._create_completion,
                **completion_params
            )
            
            return {
                "success": True,
                "response": response,
                "error": None,
                "error_type": None
            }
            
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {str(e)}")
            return {
                "success": False,
                "response": None,
                "error": "API rate limit exceeded. Please try again later.",
                "error_type": "rate_limit"
            }
            
        except openai.APITimeoutError as e:
            logger.error(f"OpenAI API timeout: {str(e)}")
            return {
                "success": False,
                "response": None,
                "error": "Request timed out. Please try again.",
                "error_type": "timeout"
            }
            
        except openai.APIConnectionError as e:
            logger.error(f"OpenAI connection error: {str(e)}")
            return {
                "success": False,
                "response": None,
                "error": "Unable to connect to AI service. Please try again later.",
                "error_type": "connection"
            }
            
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication error: {str(e)}")
            return {
                "success": False,
                "response": None,
                "error": "AI service authentication failed. Please contact support.",
                "error_type": "auth"
            }
            
        except openai.BadRequestError as e:
            logger.error(f"OpenAI bad request: {str(e)}")
            return {
                "success": False,
                "response": None,
                "error": "Invalid request to AI service. Please try rephrasing your message.",
                "error_type": "bad_request"
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI request: {str(e)}")
            return {
                "success": False,
                "response": None,
                "error": "An unexpected error occurred. Please try again later.",
                "error_type": "unknown"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Получить текущий статус системы надежности"""
        return {
            "circuit_breaker_state": self.reliability_manager.state.value,
            "failure_count": self.reliability_manager.failure_count,
            "success_count": self.reliability_manager.success_count,
            "requests_this_minute": self.reliability_manager.request_count,
            "rate_limit_window_start": self.reliability_manager.request_window_start,
            "last_failure_time": self.reliability_manager.last_failure_time
        }

# Глобальный экземпляр надежного клиента
reliable_openai_client = None

def init_reliable_openai_client(api_key: str):
    """Инициализировать глобальный надежный клиент"""
    global reliable_openai_client
    reliable_openai_client = ReliableOpenAIClient(api_key)
    logger.info("Reliable OpenAI client initialized")

def get_reliable_openai_client() -> ReliableOpenAIClient:
    """Получить глобальный надежный клиент"""
    if reliable_openai_client is None:
        raise RuntimeError("Reliable OpenAI client not initialized")
    return reliable_openai_client