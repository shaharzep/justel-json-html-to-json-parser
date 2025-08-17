#!/usr/bin/env python3
"""
Two-phase transformation with batch LLM validation.
Phase 1: Transform all files without LLM
Phase 2: Batch validate invalid files with LLM
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import argparse
import asyncio
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import the original transformer (without LLM)
from transform_juportal import JuportalTransformer
from batch_language_validator import BatchLLMValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TwoPhaseTransformer:
    """Manages two-phase transformation with batch LLM validation."""
    
    def __init__(self, input_dir: str = "raw_jsons", output_dir: str = "output"):
        """Initialize the two-phase transformer."""
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        # Statistics
        self.stats = {
            'phase1_time': 0,
            'phase2_time': 0,
            'total_files': 0,
            'invalid_before_llm': 0,
            'invalid_after_llm': 0,
            'llm_fixed': 0,
            'skipped_conc': 0
        }
    
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
        import language_validator
        original_llm = language_validator.llm_validator
        language_validator.llm_validator = None
        
        try:
            # Run the original transformer
            transformer = JuportalTransformer(str(self.input_dir), str(self.output_dir))
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
            fileName = doc['fileName']
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
        """Run both phases of transformation."""
        total_start = time.time()
        
        # Phase 1: Transform without LLM
        self.run_phase1()
        
        # Phase 2: Batch LLM validation
        await self.run_phase2()
        
        total_time = time.time() - total_start
        
        # Print final statistics
        logger.info("=" * 60)
        logger.info("TRANSFORMATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total time: {total_time:.1f}s")
        logger.info(f"  Phase 1 (transformation): {self.stats['phase1_time']:.1f}s")
        logger.info(f"  Phase 2 (LLM validation): {self.stats['phase2_time']:.1f}s")
        logger.info("")
        logger.info(f"Total files processed: {self.stats['total_files']}")
        logger.info(f"Skipped CONC files: {self.stats['skipped_conc']}")
        logger.info(f"Invalid before LLM: {self.stats['invalid_before_llm']}")
        logger.info(f"Fixed by LLM: {self.stats['llm_fixed']}")
        logger.info(f"Still invalid: {self.stats['invalid_after_llm']}")
        
        actual_saved = self.stats['total_files'] - self.stats['skipped_conc']
        valid_count = actual_saved - self.stats['invalid_after_llm']
        valid_pct = (valid_count / actual_saved * 100) if actual_saved > 0 else 0
        
        logger.info("")
        logger.info(f"Final validation rate: {valid_count}/{actual_saved} ({valid_pct:.1f}%) [Excluding CONC files]")
        
        if self.stats['phase1_time'] > 0:
            avg_time_phase1 = self.stats['phase1_time'] / self.stats['total_files']
            logger.info(f"Average time per file (Phase 1): {avg_time_phase1:.3f}s")
        
        if self.stats['invalid_before_llm'] > 0 and self.stats['phase2_time'] > 0:
            avg_time_phase2 = self.stats['phase2_time'] / self.stats['invalid_before_llm']
            logger.info(f"Average time per invalid file (Phase 2): {avg_time_phase2:.3f}s")
        
        logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Two-phase Juportal transformation with batch LLM validation')
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
    
    transformer = TwoPhaseTransformer(args.input, args.output)
    
    # Run async transformation
    asyncio.run(transformer.run())


if __name__ == "__main__":
    main()