"""
Language validation module for Juportal JSON files.
Validates that document content matches the declared language.
"""

import logging
from typing import Dict, List, Optional, Tuple
from langdetect import detect, detect_langs, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# Set seed for deterministic results
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

# Import LLM validator if available
try:
    from .llm_validator import LLMValidator
    llm_validator = LLMValidator()
except Exception as e:
    logger.debug(f"LLM validator not available: {e}")
    llm_validator = None

class LanguageValidator:
    """Validates that document content matches declared language."""
    
    def __init__(self):
        """Initialize language validator."""
        # Map Juportal language codes to langdetect ISO codes
        self.lang_map = {
            'FR': 'fr',  # French
            'NL': 'nl',  # Dutch
            'DE': 'de'   # German
        }
        
        # Minimum text length for reliable detection
        self.min_text_length = 30  # Increased for better accuracy
        
    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect language of given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Detected language code (ISO 639-1) or None if detection fails
        """
        if not text or len(text.strip()) < self.min_text_length:
            logger.debug(f"Text too short for detection: {len(text)} chars")
            return None
            
        try:
            # Convert to lowercase for better accuracy (especially for Dutch/German distinction)
            clean_text = text.strip().lower()
            detected = detect(clean_text)
            logger.debug(f"Detected language: {detected} for text: {text[:50]}...")
            return detected
        except LangDetectException as e:
            logger.warning(f"Language detection failed: {e}")
            return None
            
    def detect_language_with_confidence(self, text: str) -> List[Tuple[str, float]]:
        """
        Detect language with confidence scores.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of (language, probability) tuples
        """
        if not text or len(text.strip()) < self.min_text_length:
            return []
            
        try:
            # Convert to lowercase for better accuracy
            clean_text = text.strip().lower()
            langs = detect_langs(clean_text)
            return [(lang.lang, lang.prob) for lang in langs]
        except LangDetectException:
            return []
    
    def validate_language_match(self, expected_lang: str, text: str, threshold: float = 0.7) -> bool:
        """
        Validate if text matches expected language.
        
        Args:
            expected_lang: Expected language code (FR, NL, DE)
            text: Text to validate
            threshold: Minimum confidence threshold (0-1)
            
        Returns:
            True if language matches with sufficient confidence
        """
        # Convert to ISO code
        expected_iso = self.lang_map.get(expected_lang)
        if not expected_iso:
            logger.warning(f"Unknown language code: {expected_lang}")
            return False
            
        # Get detection with confidence
        detections = self.detect_language_with_confidence(text)
        if not detections:
            logger.debug(f"No language detected for validation")
            return False
            
        # Special handling for Dutch - Afrikaans is often confused with Dutch
        # If expecting Dutch and detected Afrikaans, check if Dutch is in top detections
        if expected_iso == 'nl' and detections:
            top_lang, top_prob = detections[0]
            if top_lang == 'af':  # Afrikaans detected instead of Dutch
                # Check if Dutch is in the detections at all
                for lang, prob in detections:
                    if lang == 'nl' and prob >= 0.3:  # Lower threshold for Dutch when AF is detected
                        logger.debug(f"Accepting Dutch (nl) despite Afrikaans detection: nl={prob:.2f}, af={top_prob:.2f}")
                        return True
                # If text is very short and detected as Afrikaans, likely Dutch legal text
                if len(text) < 100:
                    logger.debug(f"Short text detected as Afrikaans, likely Dutch legal text")
                    return True
            
        # Check if expected language is detected with sufficient confidence
        for lang, prob in detections:
            if lang == expected_iso and prob >= threshold:
                logger.debug(f"Language match confirmed: {lang} with confidence {prob:.2f}")
                return True
                
        # Log the mismatch
        if detections:
            top_lang, top_prob = detections[0]
            logger.info(f"Language mismatch: expected {expected_iso}, detected {top_lang} ({top_prob:.2f})")
            
        return False
    
    def validate_document(self, output: Dict) -> bool:
        """
        Validate language consistency in entire document.
        
        Args:
            output: Transformed document dictionary
            
        Returns:
            True if document language is valid/consistent
        """
        # Get expected language
        meta_lang = output.get('language_metadata')
        if not meta_lang:
            logger.warning("No language_metadata specified in document")
            return False
            
        # Collect text samples for validation
        text_samples = []
        
        # Extract full_text sample (first 500 chars for better accuracy)
        full_text = output.get('full_text')
        if full_text and full_text.strip():
            # Take more text for better detection accuracy
            sample = full_text[:500].strip()
            if sample:
                text_samples.append(sample)
        
        # Extract from summaries
        summaries = output.get('summaries', [])
        for summary in summaries:
            # Check summary
            summary_text = summary.get('summary')
            if summary_text and summary_text.strip():
                sample = summary_text[:200].strip()
                if sample:
                    text_samples.append(sample)
                    
            # Check keywordsFree (often contains language-specific text)
            keywords_free = summary.get('keywordsFree')
            if keywords_free and isinstance(keywords_free, str) and keywords_free.strip():
                sample = keywords_free[:200].strip()
                if sample:
                    text_samples.append(sample)
            
            # Check keywordsCassation (array of strings)
            keywords_cass = summary.get('keywordsCassation', [])
            if keywords_cass and isinstance(keywords_cass, list):
                # Join first few keywords for language detection
                kw_text = ' '.join(keywords_cass[:5])
                if kw_text.strip():
                    text_samples.append(kw_text.strip())
            
            # Check keywordsUtu (array of strings)  
            keywords_utu = summary.get('keywordsUtu', [])
            if keywords_utu and isinstance(keywords_utu, list):
                kw_text = ' '.join(keywords_utu[:5])
                if kw_text.strip():
                    text_samples.append(kw_text.strip())
                    
            # Check legalBasis (array of strings)
            legal_basis = summary.get('legalBasis', [])
            if legal_basis and isinstance(legal_basis, list):
                lb_text = ' '.join(legal_basis[:3])
                if lb_text.strip():
                    text_samples.append(lb_text.strip())
        
        # Also check other text fields in the document
        # Chamber field
        chamber = output.get('chamber')
        if chamber and isinstance(chamber, str) and chamber.strip():
            text_samples.append(chamber.strip())
            
        # Field of law
        field_of_law = output.get('field_of_law')
        if field_of_law and isinstance(field_of_law, str) and field_of_law.strip():
            text_samples.append(field_of_law.strip())
        
        # Opinion public attorney
        opinion = output.get('opinion_public_attorney')
        if opinion and isinstance(opinion, str) and opinion.strip():
            text_samples.append(opinion[:200].strip())
            
        # If no text samples found, mark as valid (no content to validate)
        if not text_samples:
            logger.info(f"No text content found for language validation in {output.get('file_name')} - marking as valid (empty document)")
            return True
        
        # Validate each sample and count matches
        matches = 0
        total = len(text_samples)
        
        for sample in text_samples:
            # Use lower threshold (0.5) for better handling of short/mixed text
            if self.validate_language_match(meta_lang, sample, threshold=0.5):
                matches += 1
        
        # Document is valid if majority of samples match (lowered to 40% for edge cases)
        match_ratio = matches / total if total > 0 else 0
        is_valid = match_ratio >= 0.4
        
        # If initial validation fails and LLM is available, use it as a second opinion
        if not is_valid and llm_validator and llm_validator.is_available():
            logger.info(f"Initial validation failed for {output.get('file_name')}, using LLM validator...")
            try:
                llm_valid, llm_confidence, llm_explanation = llm_validator.validate_document(output)
                
                # If LLM is confident (>0.8) that the language is correct, override the initial validation
                if llm_valid and llm_confidence >= 0.8:
                    logger.info(f"LLM validation overrode initial result for {output.get('file_name')}: "
                              f"valid={llm_valid}, confidence={llm_confidence:.2f}, reason: {llm_explanation[:100]}")
                    is_valid = True
                else:
                    logger.info(f"LLM validation confirmed invalid for {output.get('file_name')}: "
                              f"confidence={llm_confidence:.2f}, reason: {llm_explanation[:100]}")
            except Exception as e:
                logger.error(f"LLM validation failed for {output.get('file_name')}: {e}")
                # Keep original validation result if LLM fails
        
        if not is_valid:
            logger.warning(f"Language validation failed for {output.get('file_name')}: "
                         f"{matches}/{total} samples matched (ratio: {match_ratio:.2f})")
        else:
            logger.debug(f"Language validation passed for {output.get('file_name')}: "
                        f"{matches}/{total} samples matched")
        
        return is_valid
    
    def get_document_language_stats(self, output: Dict) -> Dict:
        """
        Get detailed language statistics for document.
        
        Args:
            output: Transformed document dictionary
            
        Returns:
            Dictionary with language detection statistics
        """
        stats = {
            'language_metadata': output.get('language_metadata'),
            'detections': [],
            'isValid': False,
            'confidence': 0.0
        }
        
        # Collect all text
        all_text = []
        
        if output.get('full_text'):
            all_text.append(output['full_text'][:1000])
            
        for summary in output.get('summaries', []):
            if summary.get('summary'):
                all_text.append(summary['summary'][:500])
        
        if not all_text:
            return stats
            
        # Detect on combined text
        combined = ' '.join(all_text)
        detections = self.detect_language_with_confidence(combined)
        
        if detections:
            stats['detections'] = [{'lang': lang, 'prob': prob} for lang, prob in detections]
            
            # Check if expected language is detected
            expected_iso = self.lang_map.get(output.get('language_metadata'))
            if expected_iso:
                for lang, prob in detections:
                    if lang == expected_iso:
                        stats['isValid'] = True
                        stats['confidence'] = prob
                        break
        
        return stats