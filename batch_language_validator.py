"""
Batch language validation using LLM for improved performance.
Processes multiple documents in parallel batches.
"""

import os
import json
import logging
from typing import Dict, List, Tuple, Optional
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import time

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class BatchLLMValidator:
    """Validates document languages using LLM in batches for efficiency."""
    
    def __init__(self, batch_size: int = 10, max_concurrent: int = 5):
        """
        Initialize batch LLM validator with OpenAI client.
        
        Args:
            batch_size: Number of documents to validate in a single API call
            max_concurrent: Maximum number of concurrent API calls
        """
        # Get API key from environment variable
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
            self.client = None
        else:
            try:
                self.client = AsyncOpenAI(api_key=api_key)
                self.model = "gpt-4o-mini"  # Cost-effective model
                self.batch_size = batch_size
                self.max_concurrent = max_concurrent
                logger.info(f"Batch LLM validator initialized with model: {self.model}, batch_size: {batch_size}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if LLM validation is available."""
        return self.client is not None
    
    async def validate_batch(self, documents: List[Dict]) -> List[Tuple[str, bool, float, str]]:
        """
        Validate a batch of documents using a single LLM call.
        
        Args:
            documents: List of document dictionaries with 'fileName', 'metaLanguage', and text content
            
        Returns:
            List of tuples (fileName, is_valid, confidence, explanation)
        """
        if not self.client:
            return [(doc['fileName'], False, 0.0, "LLM not available") for doc in documents]
        
        # Prepare batch validation request
        batch_items = []
        for doc in documents:
            # Extract text samples
            text_samples = self._extract_text_samples(doc)
            if not text_samples:
                batch_items.append({
                    'fileName': doc['fileName'],
                    'language': doc['metaLanguage'],
                    'text': 'NO_TEXT_CONTENT'
                })
            else:
                combined_text = '\n'.join(text_samples[:3])[:300]  # Limit text
                batch_items.append({
                    'fileName': doc['fileName'],
                    'language': doc['metaLanguage'],
                    'text': combined_text
                })
        
        # Map language codes to full names
        lang_names = {'FR': 'French', 'NL': 'Dutch', 'DE': 'German'}
        
        # Create batch prompt
        prompt = """You are a language detection expert. Analyze the following documents and determine if each text matches its expected language.

For each document, provide a JSON object with:
- "fileName": the file name
- "is_valid": true/false (whether the text matches the expected language)
- "confidence": a number between 0 and 1
- "explanation": a brief explanation

Documents to analyze:
"""
        
        for item in batch_items:
            expected_lang = lang_names.get(item['language'], item['language'])
            prompt += f"\n\nFile: {item['fileName']}\nExpected Language: {expected_lang}\nText: {item['text'][:200]}"
        
        prompt += "\n\nProvide a JSON array with results for all documents:"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise language detection expert. Respond only with valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            results = json.loads(response_text)
            
            # Process results
            output = []
            for result in results:
                fileName = result.get('fileName', '')
                is_valid = result.get('is_valid', False)
                confidence = float(result.get('confidence', 0.0))
                explanation = result.get('explanation', 'No explanation')
                output.append((fileName, is_valid, confidence, explanation))
            
            return output
            
        except Exception as e:
            logger.error(f"Batch validation failed: {e}")
            return [(doc['fileName'], False, 0.0, f"Error: {str(e)}") for doc in documents]
    
    def _extract_text_samples(self, doc: Dict) -> List[str]:
        """Extract text samples from a document for validation."""
        samples = []
        
        # Add fullText sample
        if doc.get('fullText'):
            samples.append(doc['fullText'][:300])
        
        # Add notice summaries
        for notice in doc.get('notices', []):
            if notice.get('summary'):
                samples.append(notice['summary'][:200])
            if notice.get('keywordsFree'):
                samples.append(notice['keywordsFree'][:100])
        
        # Add other fields
        if doc.get('fieldOfLaw'):
            samples.append(doc['fieldOfLaw'])
        if doc.get('chamber'):
            samples.append(doc['chamber'])
        
        return [s for s in samples if s and s.strip()]
    
    async def validate_documents(self, documents: List[Dict]) -> Dict[str, Tuple[bool, float, str]]:
        """
        Validate multiple documents using batched LLM calls.
        
        Args:
            documents: List of document dictionaries to validate
            
        Returns:
            Dictionary mapping fileName to (is_valid, confidence, explanation)
        """
        if not documents:
            return {}
        
        logger.info(f"Starting batch validation for {len(documents)} documents")
        start_time = time.time()
        
        # Split into batches
        batches = []
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            batches.append(batch)
        
        logger.info(f"Split into {len(batches)} batches of up to {self.batch_size} documents")
        
        # Process batches with concurrency limit
        results = {}
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_batch_with_limit(batch):
            async with semaphore:
                return await self.validate_batch(batch)
        
        # Process all batches
        tasks = [process_batch_with_limit(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)
        
        # Combine results
        for batch_result in batch_results:
            for fileName, is_valid, confidence, explanation in batch_result:
                results[fileName] = (is_valid, confidence, explanation)
        
        elapsed = time.time() - start_time
        logger.info(f"Batch validation completed in {elapsed:.1f}s for {len(documents)} documents")
        logger.info(f"Average time per document: {elapsed/len(documents):.2f}s")
        
        return results


async def validate_invalid_files(input_dir: str = "output", threshold: float = 0.8):
    """
    Load all transformed files, identify invalid ones, and validate them in batches.
    
    Args:
        input_dir: Directory containing transformed JSON files
        threshold: Confidence threshold for LLM to override initial validation
        
    Returns:
        Statistics about validation results
    """
    from language_validator import LanguageValidator
    
    # Initialize validators
    lang_validator = LanguageValidator()
    batch_llm = BatchLLMValidator(batch_size=10, max_concurrent=5)
    
    if not batch_llm.is_available():
        logger.error("LLM validator not available")
        return None
    
    # First pass: identify invalid files
    logger.info("First pass: Processing files to identify invalid ones...")
    invalid_docs = []
    total_files = 0
    
    input_path = Path(input_dir)
    for filepath in input_path.glob("*.json"):
        total_files += 1
        
        # Load document
        with open(filepath, 'r', encoding='utf-8') as f:
            doc = json.load(f)
        
        # Quick validation without LLM
        is_valid = lang_validator.validate_document(doc)
        
        if not is_valid:
            invalid_docs.append(doc)
            logger.debug(f"Found invalid: {doc['fileName']}")
    
    logger.info(f"First pass complete: {len(invalid_docs)} invalid out of {total_files} files")
    
    if not invalid_docs:
        logger.info("No invalid documents to process")
        return {
            'total_files': total_files,
            'invalid_before_llm': 0,
            'invalid_after_llm': 0,
            'fixed_by_llm': 0
        }
    
    # Second pass: Batch validate invalid documents with LLM
    logger.info(f"Second pass: Batch validating {len(invalid_docs)} invalid documents with LLM...")
    
    results = await batch_llm.validate_documents(invalid_docs)
    
    # Count results
    fixed_count = 0
    still_invalid = []
    
    for doc in invalid_docs:
        fileName = doc['fileName']
        if fileName in results:
            is_valid, confidence, explanation = results[fileName]
            if is_valid and confidence >= threshold:
                fixed_count += 1
                logger.info(f"LLM validated as correct: {fileName} (confidence: {confidence:.2f})")
            else:
                still_invalid.append(fileName)
                logger.info(f"LLM confirmed invalid: {fileName} (confidence: {confidence:.2f})")
    
    # Print summary
    stats = {
        'total_files': total_files,
        'invalid_before_llm': len(invalid_docs),
        'invalid_after_llm': len(still_invalid),
        'fixed_by_llm': fixed_count,
        'final_valid_percentage': (total_files - len(still_invalid)) / total_files * 100
    }
    
    logger.info("=" * 50)
    logger.info("BATCH VALIDATION COMPLETE")
    logger.info(f"Total files: {stats['total_files']}")
    logger.info(f"Invalid before LLM: {stats['invalid_before_llm']}")
    logger.info(f"Fixed by LLM: {stats['fixed_by_llm']}")
    logger.info(f"Still invalid: {stats['invalid_after_llm']}")
    logger.info(f"Final valid percentage: {stats['final_valid_percentage']:.1f}%")
    logger.info("=" * 50)
    
    # Save list of still invalid files
    if still_invalid:
        with open('invalid_files.json', 'w', encoding='utf-8') as f:
            json.dump(still_invalid, f, ensure_ascii=False, indent=2)
        logger.info(f"List of {len(still_invalid)} invalid files saved to invalid_files.json")
    
    return stats


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    
    parser = argparse.ArgumentParser(description='Batch validate language in transformed files')
    parser.add_argument('--input', '-i', default='output',
                       help='Input directory containing transformed JSON files')
    parser.add_argument('--threshold', '-t', type=float, default=0.8,
                       help='Confidence threshold for LLM override (0-1)')
    
    args = parser.parse_args()
    
    # Run async validation
    asyncio.run(validate_invalid_files(args.input, args.threshold))