"""
LLM-based language validation for documents flagged as potentially invalid.
Uses OpenAI GPT-4o-mini for cost-effective validation.
"""

import os
import json
import logging
from typing import Dict, Tuple, Optional, List
import openai
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class LLMValidator:
    """Validates document language using LLM as a second opinion."""
    
    def __init__(self):
        """Initialize LLM validator with OpenAI client."""
        # Get API key from environment variable
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
            self.client = None
        else:
            try:
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-4o-mini"  # Cost-effective model
                logger.info(f"LLM validator initialized with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if LLM validation is available."""
        return self.client is not None
    
    def validate_language(self, text_samples: List[str], expected_language: str) -> Tuple[bool, float, str]:
        """
        Validate if text samples match the expected language using LLM.
        
        Args:
            text_samples: List of text samples from the document
            expected_language: Expected language code (FR, NL, DE)
            
        Returns:
            Tuple of (is_valid, confidence, explanation)
        """
        if not self.client:
            logger.warning("LLM client not available for validation")
            return False, 0.0, "LLM validation not available"
        
        # Prepare text samples for validation
        combined_text = "\n".join(text_samples[:5])  # Limit to first 5 samples
        if len(combined_text) > 500:
            combined_text = combined_text[:500]  # Limit total length
        
        # Map language codes to full names
        lang_names = {
            'FR': 'French',
            'NL': 'Dutch',
            'DE': 'German'
        }
        expected_lang_name = lang_names.get(expected_language, expected_language)
        
        # Create prompt for GPT-4o-mini
        prompt = f"""You are a language detection expert. Analyze the following text and determine if it is written in {expected_lang_name}.

Text to analyze:
{combined_text}

Please respond with a JSON object containing:
- "is_language_match": true/false (whether the text is in {expected_lang_name})
- "detected_language": the actual language you detected
- "confidence": a number between 0 and 1 indicating your confidence
- "explanation": a brief explanation of your decision

Consider that:
- Legal texts may contain Latin phrases or technical terms
- Dutch and German can be similar but have distinct characteristics
- Afrikaans is very similar to Dutch and should be considered as Dutch for this purpose
- Short text fragments might be ambiguous

JSON Response:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise language detection expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=200
            )
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            
            # Try to extract JSON from response
            try:
                # Handle case where response might have markdown code blocks
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                result = json.loads(response_text)
                
                is_valid = result.get('is_language_match', False)
                confidence = float(result.get('confidence', 0.0))
                explanation = result.get('explanation', 'No explanation provided')
                
                logger.debug(f"LLM validation result: valid={is_valid}, confidence={confidence:.2f}")
                return is_valid, confidence, explanation
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.debug(f"Raw response: {response_text}")
                return False, 0.0, "Failed to parse LLM response"
                
        except Exception as e:
            logger.error(f"LLM validation failed: {e}")
            return False, 0.0, f"LLM validation error: {str(e)}"
    
    def validate_document(self, output: Dict) -> Tuple[bool, float, str]:
        """
        Validate an entire document using LLM.
        
        Args:
            output: Document dictionary with text content
            
        Returns:
            Tuple of (is_valid, confidence, explanation)
        """
        # Collect text samples from document
        text_samples = []
        
        # Add full_text sample
        if output.get('full_text'):
            text_samples.append(output['full_text'][:300])
        
        # Add notice summaries
        for notice in output.get('summaries', []):
            if notice.get('summary'):
                text_samples.append(notice['summary'][:200])
            if notice.get('keywordsFree'):
                text_samples.append(notice['keywordsFree'][:100])
        
        # Add other text fields
        if output.get('field_of_law'):
            text_samples.append(output['field_of_law'])
        if output.get('chamber'):
            text_samples.append(output['chamber'])
        
        if not text_samples:
            return True, 1.0, "No text content to validate"
        
        expected_lang = output.get('language_metadata')
        if not expected_lang:
            return False, 0.0, "No language_metadata specified"
        
        return self.validate_language(text_samples, expected_lang)