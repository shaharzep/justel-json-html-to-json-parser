#!/usr/bin/env python3
"""
Two-phase transformation with batch LLM validation and deduplication.
Phase 1: Transform all files without LLM
Phase 1.5: Deduplicate based on ECLI aliases
Phase 2: Batch validate invalid files with LLM
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
import argparse
import asyncio
import time
from dotenv import load_dotenv

# Add parent directory to Python path for utils imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Load environment variables from .env file
load_dotenv()

# Import the original transformer (without LLM)
from juportal_utils.transform_juportal import JuportalTransformer
from juportal_utils.batch_language_validator import BatchLLMValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedJuportalTransformer(JuportalTransformer):
    """Enhanced transformer with full_textHtml extraction."""
    
    def _process_full_text(self, section: Dict, output: Dict):
        """Process full text section with HTML extraction."""
        from juportal_utils.utils import extract_pdf_url, clean_text
        
        paragraphs = section.get('paragraphs', [])
        text_parts = []
        html_parts = []
        
        for para in paragraphs:
            text = para.get('text', '').strip()
            html = para.get('html', '')
            
            # Skip empty paragraphs
            if not text:
                continue
            
            # Skip paragraphs that start with "Document PDF" - these are PDF download links
            if text.startswith('Document PDF') or text.startswith('PDF document'):
                continue
            
            # Skip paragraphs that are ONLY metadata labels (no content after the label)
            # These are typically very short paragraphs with just the label
            is_just_label = False
            for label in ['texte intégral:', 'volledige tekst:', 'volltext:', 
                         'full text:', 'pdf:', 'download:']:
                if text.lower().strip() == label.strip(':'):
                    is_just_label = True
                    break
            
            if not is_just_label:
                # Add to text parts for plain text
                text_parts.append(text)
                # Add to HTML parts if HTML exists
                if html:
                    html_parts.append(html)
        
        # Process plain text
        if text_parts:
            full_text = ' '.join(text_parts)
            cleaned_text = clean_text(full_text)
            # If the text is just the placeholder "<>", clear both text and HTML fields
            if cleaned_text == "<>":
                output['full_text'] = ""
                output['full_html'] = ""
            else:
                output['full_text'] = cleaned_text
                # Process HTML only if we have actual content
                if html_parts:
                    # Join with a newline to preserve structure
                    output['full_html'] = '\n'.join(html_parts)
        
        # Look for PDF URL
        pdf_url = extract_pdf_url(section)
        if pdf_url:
            output['url_pdf'] = pdf_url


class TwoPhaseTransformerWithDedup:
    """Manages two-phase transformation with deduplication and batch LLM validation."""
    
    def __init__(self, input_dir: str = "raw_jsons", output_dir: str = "output"):
        """Initialize the two-phase transformer."""
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        # Statistics
        self.stats = {
            'phase1_time': 0,
            'dedup_time': 0,
            'phase2_time': 0,
            'total_files': 0,
            'invalid_before_llm': 0,
            'invalid_after_llm': 0,
            'llm_fixed': 0,
            'skipped_conc': 0,
            'duplicates_removed': 0,
            'german_files_removed': 0,
            'missing_dates_count': 0,
            'valid_with_dates_count': 0
        }
    
    def ecli_to_filename(self, ecli: str, language: str = None) -> List[str]:
        """
        Convert ECLI to possible filename formats.
        
        Args:
            ecli: ECLI identifier (e.g., 'ECLI:BE:GHCC:2013:ARR.20130718.1')
            language: Language code (FR, NL, DE) or None for all languages
            
        Returns:
            List of possible filenames
        """
        if not ecli or not ecli.startswith('ECLI:'):
            return []
        
        # Replace colons with underscores
        base = ecli.replace(':', '_')
        
        # Generate filename with language suffix
        filenames = []
        if language:
            filenames.append(f"juportal.be_{base}_{language}.json")
        else:
            # Try all language variants
            for lang in ['FR', 'NL', 'DE']:
                filenames.append(f"juportal.be_{base}_{lang}.json")
        
        return filenames
    
    def count_missing_dates(self):
        """Count files with missing or incomplete decision dates."""
        logger.info("=" * 60)
        logger.info("Analyzing decision dates in output files")
        logger.info("=" * 60)
        
        missing_dates_files = []
        valid_with_dates = 0
        valid_files_checked = 0
        
        all_files = list(self.output_dir.glob("*.json"))
        
        # Skip the summary file
        all_files = [f for f in all_files if f.name != 'invalid_files.json']
        
        for filepath in all_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                
                # Skip invalid files
                if not doc.get('isValid', True):
                    continue
                
                valid_files_checked += 1
                
                # Check decision_date field
                decision_date = doc.get('decision_date')
                
                # Check if date is missing or incomplete (only year)
                if not decision_date or decision_date == '' or (isinstance(decision_date, str) and len(decision_date) == 4):
                    missing_dates_files.append({
                        'file': filepath.name,
                        'ecli': doc.get('decision_id', 'Unknown'),
                        'current_date': decision_date
                    })
                else:
                    valid_with_dates += 1
                    
            except Exception as e:
                logger.warning(f"Error checking {filepath}: {e}")
        
        self.stats['missing_dates_count'] = len(missing_dates_files)
        self.stats['valid_with_dates_count'] = valid_with_dates
        
        # Save list of files with missing dates if any exist
        if missing_dates_files:
            missing_dates_path = self.output_dir / 'missing_dates.json'
            with open(missing_dates_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'count': len(missing_dates_files),
                    'files': missing_dates_files
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"Found {len(missing_dates_files)} valid files with missing/incomplete dates")
            logger.info(f"List saved to {missing_dates_path}")
        else:
            logger.info("All valid files have complete decision dates!")
        
        if valid_files_checked > 0:
            complete_rate = (valid_with_dates / valid_files_checked) * 100
            logger.info(f"Date completeness: {valid_with_dates}/{valid_files_checked} ({complete_rate:.1f}%)")
    
    def remove_german_files(self):
        """Remove files with German language (DE) from output directory."""
        logger.info("=" * 60)
        logger.info("Removing German language files")
        logger.info("=" * 60)
        
        removed_count = 0
        all_files = list(self.output_dir.glob("*.json"))
        
        # Skip invalid_files.json
        all_files = [f for f in all_files if f.name != 'invalid_files.json']
        
        for filepath in all_files:
            try:
                # Check if filename contains _DE pattern
                if '_DE.json' in filepath.name:
                    # Double-check by reading the file content
                    with open(filepath, 'r', encoding='utf-8') as f:
                        doc = json.load(f)
                    
                    # Check language_metadata field
                    if doc.get('language_metadata') == 'DE':
                        logger.debug(f"Removing German file: {filepath.name}")
                        filepath.unlink()
                        removed_count += 1
                        
            except Exception as e:
                logger.warning(f"Error checking/removing file {filepath}: {e}")
        
        self.stats['german_files_removed'] = removed_count
        logger.info(f"Removed {removed_count} German language files")
        
    def deduplicate_files(self):
        """Remove duplicate files based on ECLI aliases."""
        logger.info("=" * 60)
        logger.info("PHASE 1.5: Deduplication based on ECLI aliases")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Load all files and build ECLI index
        logger.info("Building ECLI index...")
        files_by_ecli = {}  # Map ECLI to filepath
        all_files = list(self.output_dir.glob("*.json"))
        
        # Skip invalid_files.json
        all_files = [f for f in all_files if f.name != 'invalid_files.json']
        
        # First pass: build index of ECLI to file mapping
        for filepath in all_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                
                # Map main ECLI to file
                main_ecli = doc.get('decision_id')
                if main_ecli:
                    files_by_ecli[main_ecli] = filepath
            except Exception as e:
                logger.warning(f"Error reading {filepath}: {e}")
        
        # Second pass: check for duplicates based on aliases
        processed_files = set()
        removed_files = set()
        
        for filepath in all_files:
            if filepath in removed_files:
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                
                processed_files.add(filepath)
                
                # Check each ECLI alias
                ecli_aliases = doc.get('ecli_alias', [])
                
                for alias in ecli_aliases:
                    if not alias or not alias.startswith('ECLI:'):
                        continue
                    
                    # Check if this alias exists as a main ECLI in our index
                    if alias in files_by_ecli:
                        duplicate_path = files_by_ecli[alias]
                        
                        # Don't remove if it's the same file or already processed
                        if duplicate_path != filepath and duplicate_path not in processed_files and duplicate_path not in removed_files:
                            # This is a duplicate - remove it
                            logger.info(f"Removing duplicate: {duplicate_path.name} (ECLI {alias} is an alias in {filepath.name})")
                            duplicate_path.unlink()
                            removed_files.add(duplicate_path)
                            self.stats['duplicates_removed'] += 1
                
            except Exception as e:
                logger.warning(f"Error processing {filepath} for deduplication: {e}")
        
        self.stats['dedup_time'] = time.time() - start_time
        logger.info(f"Deduplication completed in {self.stats['dedup_time']:.1f}s")
        logger.info(f"Removed {self.stats['duplicates_removed']} duplicate files")
    
    def run_phase1(self):
        """Phase 1: Run full transformation without LLM."""
        logger.info("=" * 60)
        logger.info("PHASE 1: Full transformation without LLM validation")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Clean output directory
        if self.output_dir.exists():
            logger.info(f"Cleaning output directory: {self.output_dir}")
            import shutil
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Temporarily disable LLM in language_validator
        from juportal_utils import language_validator
        original_llm = language_validator.llm_validator
        language_validator.llm_validator = None
        
        try:
            # Use enhanced transformer for full_textHtml extraction
            transformer = EnhancedJuportalTransformer(str(self.input_dir), str(self.output_dir))
            transformer.process_all()
            
            # Get statistics
            self.stats['total_files'] = transformer.stats['total_files']
            self.stats['invalid_before_llm'] = transformer.stats['language_invalid']
            self.stats['skipped_conc'] = transformer.stats.get('skipped_conc', 0)
            
        finally:
            # Restore LLM validator
            language_validator.llm_validator = original_llm
        
        self.stats['phase1_time'] = time.time() - start_time
        
        logger.info(f"Phase 1 completed in {self.stats['phase1_time']:.1f}s")
        logger.info(f"Files with invalid language: {self.stats['invalid_before_llm']}")
    
    async def run_phase2(self):
        """Phase 2: Batch validate invalid files with LLM."""
        logger.info("=" * 60)
        logger.info("PHASE 2: Batch LLM validation for invalid files")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Find all files with isValid = false
        invalid_files = []
        
        logger.info("Scanning output files for invalid language...")
        
        for filepath in self.output_dir.glob("*.json"):
            with open(filepath, 'r', encoding='utf-8') as f:
                doc = json.load(f)
            
            if not doc.get('isValid', True):
                invalid_files.append(doc)
        
        logger.info(f"Found {len(invalid_files)} files with invalid language")
        
        if not invalid_files:
            logger.info("No invalid files to process")
            self.stats['phase2_time'] = time.time() - start_time
            return
        
        # Initialize batch LLM validator
        batch_llm = BatchLLMValidator(batch_size=10, max_concurrent=5)
        
        if not batch_llm.is_available():
            logger.error("LLM validator not available, skipping Phase 2")
            self.stats['invalid_after_llm'] = len(invalid_files)
            self.stats['phase2_time'] = time.time() - start_time
            return
        
        # Batch validate with LLM
        logger.info(f"Sending {len(invalid_files)} files to LLM in batches...")
        
        results = await batch_llm.validate_documents(invalid_files)
        
        # Update files based on LLM results
        logger.info("Updating files based on LLM validation...")
        
        fixed_files = []
        still_invalid = []
        
        for doc in invalid_files:
            fileName = doc['file_name']
            if fileName in results:
                is_valid, confidence, explanation = results[fileName]
                
                if is_valid and confidence >= 0.8:
                    # LLM says it's valid - update the file
                    doc['isValid'] = True
                    doc['llmValidation'] = {
                        'validated': True,
                        'confidence': confidence,
                        'explanation': explanation
                    }
                    
                    # Save updated file
                    output_path = self.output_dir / fileName
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(doc, f, ensure_ascii=False, indent=2)
                    
                    fixed_files.append(fileName)
                    self.stats['llm_fixed'] += 1
                    
                    logger.info(f"✓ LLM validated: {fileName} (confidence: {confidence:.2f})")
                else:
                    # LLM confirms it's invalid
                    doc['llmValidation'] = {
                        'validated': False,
                        'confidence': confidence,
                        'explanation': explanation
                    }
                    
                    # Save updated file with LLM confirmation
                    output_path = self.output_dir / fileName
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(doc, f, ensure_ascii=False, indent=2)
                    
                    still_invalid.append(fileName)
                    
                    logger.debug(f"✗ LLM confirmed invalid: {fileName} (confidence: {confidence:.2f})")
        
        self.stats['invalid_after_llm'] = len(still_invalid)
        self.stats['phase2_time'] = time.time() - start_time
        
        # Save list of still invalid files
        if still_invalid:
            invalid_list_path = self.output_dir / 'invalid_files.json'
            with open(invalid_list_path, 'w', encoding='utf-8') as f:
                json.dump(sorted(still_invalid), f, ensure_ascii=False, indent=2)
            logger.info(f"List of {len(still_invalid)} invalid files saved to {invalid_list_path}")
        
        logger.info(f"Phase 2 completed in {self.stats['phase2_time']:.1f}s")
    
    async def run(self):
        """Run all phases of transformation."""
        total_start = time.time()
        
        # Phase 1: Transform without LLM
        self.run_phase1()
        
        # Phase 1.2: Remove German language files
        self.remove_german_files()
        
        # Phase 1.5: Deduplicate based on ECLI aliases
        self.deduplicate_files()
        
        # Phase 2: Batch LLM validation
        await self.run_phase2()
        
        # Phase 3: Analyze missing dates
        self.count_missing_dates()
        
        total_time = time.time() - total_start
        
        # Count final output files
        final_file_count = len(list(self.output_dir.glob("*.json")))
        
        # Print final statistics
        logger.info("=" * 60)
        logger.info("TRANSFORMATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total time: {total_time:.1f}s")
        logger.info(f"  Phase 1 (transformation): {self.stats['phase1_time']:.1f}s")
        logger.info(f"  Phase 1.5 (deduplication): {self.stats['dedup_time']:.1f}s")
        logger.info(f"  Phase 2 (LLM validation): {self.stats['phase2_time']:.1f}s")
        logger.info("")
        logger.info(f"Total files processed: {self.stats['total_files']}")
        logger.info(f"Skipped CONC files: {self.stats['skipped_conc']}")
        logger.info(f"German files removed: {self.stats['german_files_removed']}")
        logger.info(f"Duplicates removed: {self.stats['duplicates_removed']}")
        logger.info(f"Final output files: {final_file_count}")
        logger.info("")
        logger.info(f"Invalid before LLM: {self.stats['invalid_before_llm']}")
        logger.info(f"Fixed by LLM: {self.stats['llm_fixed']}")
        logger.info(f"Still invalid: {self.stats['invalid_after_llm']}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Two-phase Juportal transformation with deduplication and batch LLM validation')
    parser.add_argument('--input', '-i', default='raw_jsons',
                      help='Input directory containing JSON files')
    parser.add_argument('--output', '-o', default='output',
                      help='Output directory for transformed files')
    parser.add_argument('--verbose', '-v', action='store_true',
                      help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        # Suppress debug messages from libraries
        logging.getLogger('language_validator').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
    
    transformer = TwoPhaseTransformerWithDedup(args.input, args.output)
    
    # Run async transformation
    asyncio.run(transformer.run())


if __name__ == "__main__":
    main()