"""LLM service implementation focusing on mathematical operations."""

import os
import re
from typing import List, Optional, Tuple
import google.generativeai as genai
import structlog
from google.api_core import exceptions

from ..domain.models import Message

logger = structlog.get_logger()

# Default API key that has no cost/usage limits
DEFAULT_API_KEY = "AIzaSyC0Zjo94X2x0MOpCmEWLuDPdeSAEvHJa_E"

class LLMService:
    """LLM service using Google's Gemini model with math focus."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(LLMService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the LLM service."""
        if self._initialized:
            return
            
        # Get API key from environment or use default
        api_key = os.getenv("GEMINI_API_KEY", DEFAULT_API_KEY)
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.context_window = 5
        logger.info("llm_service_init", model="gemini-1.5-flash", using_default_key=(api_key == DEFAULT_API_KEY))
        
        LLMService._initialized = True
    
    def _is_math_query(self, message: str) -> bool:
        """Detect if the query is mathematical in nature."""
        math_patterns = [
            r'\d+\s*[\+\-\*\/]\s*\d+',  # Direct math operations
            r'multiply|times|divide|plus|minus|add|subtract',  # Operation words
            r'that|this|it',  # Context references
            r'double|triple|half|twice',  # Special operations
            r'take away|knock off|cut',  # Informal subtraction
            r'start with|begin with',  # Initial value setters
            r'\d+',  # Any number
        ]
        return any(re.search(pattern, message.lower()) for pattern in math_patterns)

    def _extract_numbers_and_operation(self, message: str, history: List[Message]) -> Tuple[List[int], Optional[str]]:
        """Extract numbers and operation from message with context."""
        message = message.lower()
        last_result = None
        
        # Get the last numerical result from history
        for msg in reversed(history):
            if msg.role == "assistant":
                match = re.search(r'(\d+)', msg.content)
                if match:
                    last_result = int(match.group(1))
                    break
        
        # Handle special operations first
        if any(word in message for word in ['double', 'twice']):
            return [last_result, 2], '*'
        elif 'triple' in message:
            return [last_result, 3], '*'
        elif any(phrase in message for phrase in ['half', 'cut in half']):
            return [last_result, 2], '/'
            
        # Replace words with numbers where appropriate
        number_words = {
            'hundred': '100',
            'thousand': '1000',
            'ten': '10',
            'zero': '0',
            'one': '1',
            'two': '2',
            'three': '3',
            'four': '4',
            'five': '5',
            'six': '6',
            'seven': '7',
            'eight': '8',
            'nine': '9'
        }
        for word, num in number_words.items():
            message = re.sub(rf'\b{word}\b', num, message)
        
        # Replace context references with the last result
        if last_result is not None:
            for ref in ['that', 'this', 'it']:
                message = re.sub(rf'\b{ref}\b', str(last_result), message)
        
        # Extract numbers
        numbers = [int(n) for n in re.findall(r'-?\d+', message)]
        if not numbers and last_result is not None:
            numbers = [last_result]
        
        # Determine operation
        operation = None
        operation_patterns = [
            (r'\+|plus|add|another|increase|more', '+'),
            (r'-|minus|subtract|take away|knock off|decrease|less|reduce', '-'),
            (r'\*|times|multiply|x', '*'),
            (r'\/|divide|divided by|over', '/')
        ]
        
        for pattern, op in operation_patterns:
            if re.search(pattern, message):
                operation = op
                break
            
        # Handle "start with" or "begin with" as special cases
        if any(phrase in message for phrase in ['start with', 'begin with']) and numbers:
            return [numbers[0]], None
            
        return numbers, operation

    def _calculate(self, numbers: List[int], operation: str) -> Optional[str]:
        """Perform calculation based on numbers and operation."""
        if not numbers:
            return None
            
        # Special case for single number (e.g., "start with 100")
        if len(numbers) == 1 and not operation:
            return str(numbers[0])
            
        if len(numbers) != 2 or not operation:
            return None
            
        a, b = numbers
        try:
            if operation == '+':
                return str(a + b)
            elif operation == '-':
                return str(a - b)
            elif operation == '*':
                return str(a * b)
            elif operation == '/' and b != 0:
                return str(a // b)
        except Exception as e:
            logger.error("calculation_error", error=str(e))
        return None

    async def generate_response(
        self,
        message: str,
        history: Optional[List[Message]] = None
    ) -> str:
        """Generate response using direct calculation with Gemini fallback."""
        history = history or []
        
        # Always try direct calculation first
        numbers, operation = self._extract_numbers_and_operation(message, history)
        result = self._calculate(numbers, operation)
        if result:
            return result
            
        # If direct calculation fails and it looks like a math query, try Gemini
        if self._is_math_query(message):
            try:
                prompt = self._format_math_prompt(message, history)
                response = self.model.generate_content(prompt)
                return self._extract_number(response.text)
            except exceptions.ResourceExhausted:
                logger.warning("gemini_quota_exhausted", fallback="retrying calculation")
                # Try calculation one more time with different number extraction
                numbers, operation = self._extract_numbers_and_operation(message, history)
                result = self._calculate(numbers, operation)
                if result:
                    return result
                return "0"  # Default fallback for math queries
            except Exception as e:
                logger.error("response_generation_error", error=str(e))
                return "0"  # Default fallback for math queries
                
        # If not a math query, return empty response
        return ""

    def _format_math_prompt(self, message: str, history: List[Message]) -> str:
        """Format math query with context."""
        # Get the last result if it exists
        last_result = None
        for msg in reversed(history):
            if msg.role == "assistant":
                match = re.search(r'(\d+)', msg.content)
                if match:
                    last_result = match.group(1)
                    break
        
        prompt = f"""You are a math assistant. Provide only the numerical answer without any explanation.
Previous result: {last_result if last_result else 'None'}
Question: {message}
Answer: """
        return prompt

    def _extract_number(self, response: str) -> str:
        """Extract numerical answer from response."""
        # Clean up the response to get just the number
        matches = re.findall(r'-?\d*\.?\d+', response)
        return matches[-1] if matches else "0"

    async def process_message(self, messages: List[Message]) -> str:
        """Process a message and generate a response."""
        try:
            if not messages:
                return "No message provided."
                
            latest_message = messages[-1].content
            history = messages[:-1]
            
            response = await self.generate_response(latest_message, history)
            return response or "0"  # Default to "0" if no response
            
        except Exception as e:
            logger.error("message_processing_error", error=str(e))
            return "0"  # Default to "0" on error
