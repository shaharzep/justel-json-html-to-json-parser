#!/usr/bin/env python3
"""
Main transformation script for Juportal JSON files.
Transforms intermediate JSON files to target schema format.
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .mapping_config import FieldMapper
from .utils import (
    extract_language_from_filename,
    extract_ecli_from_filename,
    extract_date_from_ecli,
    extract_date_from_legend,
    extract_date_with_llm_fallback,
    extract_jurisdiction_from_ecli,
    extract_court_code_from_ecli,
    extract_decision_type_from_ecli,
    clean_text,
    extract_paragraphs_text,
    extract_paragraphs_html,
    extract_field_value_from_paragraphs,
    extract_links_from_paragraph,
    parse_legal_basis,
    extract_pdf_url,
    merge_keyword_values,
    build_url_from_ecli,
    safe_get,
    format_ecli_alias,
    parse_versions
)
from .validators import SchemaValidator
from .language_validator import LanguageValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JuportalTransformer:
    """Transform Juportal intermediate JSON to target schema."""
    
    def __init__(self, input_dir: str = "raw_jsons", output_dir: str = "output"):
        """Initialize transformer."""
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.mapper = FieldMapper()
        self.validator = SchemaValidator()
        self.language_validator = LanguageValidator()
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'validation_errors': 0,
            'language_invalid': 0,
            'skipped_conc': 0
        }
    
    def transform_file(self, filepath: Path) -> Optional[Dict]:
        """Transform a single JSON file."""
        try:
            logger.info(f"Processing file: {filepath.name}")
            
            # Load input JSON
            with open(filepath, 'r', encoding='utf-8') as f:
                input_data = json.load(f)
            
            # Extract metadata from filename
            filename = filepath.name
            language = extract_language_from_filename(filename)
            ecli = extract_ecli_from_filename(filename)
            
            # Create output document
            output = self.validator.create_empty_document()
            
            # Set basic fields
            output['file_name'] = filename
            output['decision_id'] = ecli or input_data.get('title', '')
            output['language_metadata'] = language
            output['source'] = 'juportal.be'
            
            # Extract jurisdiction from ECLI (decision_id)
            if output['decision_id']:
                output['jurisdiction'] = extract_jurisdiction_from_ecli(output['decision_id']) or 'BE'
            else:
                output['jurisdiction'] = 'BE'  # Default fallback
            
            output['url_official_publication'] = build_url_from_ecli(output['decision_id'], language)
            
            # Extract court and decision type from ECLI
            if output['decision_id']:
                output['court_ecli_code'] = extract_court_code_from_ecli(output['decision_id'])
                output['decision_type_ecli_code'] = extract_decision_type_from_ecli(output['decision_id'])
            
            # Process sections
            sections = input_data.get('sections', [])
            
            for section in sections:
                legend = section.get('legend', '')
                
                if self.mapper.is_decision_card(legend):
                    # Process first card (decision overview)
                    self._process_decision_card(section, output, language)
                    
                    # Try to extract date from legend if not already set
                    if not output['decision_date'] or len(output['decision_date']) == 4:
                        date = extract_date_from_legend(legend, language)
                        if date:
                            output['decision_date'] = date
                
                elif self.mapper.is_fiche_card(legend):
                    # Process Fiche card (summary)
                    self._process_fiche_card(section, output, legend)
                
                elif self.mapper.is_full_text_section(legend):
                    # Process full text section
                    self._process_full_text(section, output)
                
                elif self.mapper.is_related_publications(legend):
                    # Process related publications
                    self._process_related_publications(section, output)
            
            # Extract decision date from ECLI if not set
            if not output['decision_date'] or len(output['decision_date']) == 4:
                date = extract_date_from_ecli(output['decision_id'])
                if date and len(date) > 4:
                    output['decision_date'] = date
            
            # If still no date, try LLM fallback on all legend texts
            if not output['decision_date'] or len(str(output['decision_date'])) == 4:
                for section in sections:
                    legend = section.get('legend', '')
                    if legend and 'van' in legend.lower() or 'du' in legend.lower() or 'vom' in legend.lower():
                        date = extract_date_with_llm_fallback(legend, language)
                        if date:
                            output['decision_date'] = date
                            logger.info(f"Used LLM fallback to extract date for {filename}: {date}")
                            break
            
            # Validate language consistency
            output['isValid'] = self.language_validator.validate_document(output)
            if not output['isValid']:
                self.stats['language_invalid'] += 1
                logger.info(f"Language validation failed for {filename}")
            
            # Validate output schema
            is_valid, errors = self.validator.validate(output)
            if not is_valid:
                logger.warning(f"Validation errors for {filename}: {errors}")
                self.stats['validation_errors'] += 1
            
            return output
            
        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")
            self.stats['failed'] += 1
            return None
    
    def _process_decision_card(self, section: Dict, output: Dict, language: str):
        """Process the first card containing decision metadata."""
        paragraphs = section.get('paragraphs', [])
        
        for i, para in enumerate(paragraphs):
            text = para.get('text', '').strip()
            if not text:
                continue
            
            # Identify field by text
            field = self.mapper.identify_field(text)
            
            if field == 'ecli' and i + 1 < len(paragraphs):
                value = paragraphs[i + 1].get('text', '').strip()
                if value and 'ECLI' in value:
                    output['decision_id'] = value
            
            elif field == 'rolNumber' and i + 1 < len(paragraphs):
                value = paragraphs[i + 1].get('text', '').strip()
                if value:
                    output['rol_number'] = value
            
            elif field == 'chamber' and i + 1 < len(paragraphs):
                value = paragraphs[i + 1].get('text', '').strip()
                if value:
                    output['chamber'] = value
            
            elif field == 'fieldOfLaw' and i + 1 < len(paragraphs):
                value = paragraphs[i + 1].get('text', '').strip()
                if value:
                    output['field_of_law'] = value
            
            elif field == 'case' and i + 1 < len(paragraphs):
                value = paragraphs[i + 1].get('text', '').strip()
                if value:
                    output['case'] = value
            
            elif field == 'versions':
                # Parse version links
                versions = parse_versions(paragraphs, i)
                if versions:
                    output['versions'] = versions
            
            elif field == 'ecliAlias' and i + 1 < len(paragraphs):
                value = paragraphs[i + 1].get('text', '').strip()
                if value:
                    output['ecli_alias'] = format_ecli_alias(value)
    
    def _process_fiche_card(self, section: Dict, output: Dict, legend: str):
        """Process a Fiche card containing summary information."""
        # Extract Fiche numbers
        fiche_numbers = self.mapper.extract_fiche_numbers(legend)
        
        paragraphs = section.get('paragraphs', [])
        
        # Summary is ALWAYS the first paragraph if it exists
        # If the first paragraph is a metadata field label, there is no summary
        summary = ""
        
        if paragraphs:
            first_para_text = paragraphs[0].get('text', '').strip()
            
            # Check if the first paragraph is a metadata field label
            if first_para_text and first_para_text not in ['', '-', ':', '–']:
                field = self.mapper.identify_field(first_para_text)
                if field is None:
                    # First paragraph is not a metadata field, so it's the summary
                    summary = first_para_text
                # If it's a metadata field label, summary remains empty string
        
        # For multi-fiche cards, we need to collect ALL metadata (there may be multiple sets)
        all_keywords_cassation = []
        all_keywords_utu = []
        all_keywords_free = []
        all_legal_basis = []
        
        for i, para in enumerate(paragraphs):
            text = para.get('text', '').strip()
            if not text:
                continue
            
            field = self.mapper.identify_field(text)
            
            if field == 'keywordsCassation':
                kw = merge_keyword_values(paragraphs, i, keyword_type='cassation')
                all_keywords_cassation.extend(kw)
            
            elif field == 'keywordsUtu':
                kw = merge_keyword_values(paragraphs, i, keyword_type='utu')
                all_keywords_utu.extend(kw)
            
            elif field == 'keywordsFree':
                # Free keywords should be concatenated as a string
                free_kw = merge_keyword_values(paragraphs, i, keyword_type='free')
                all_keywords_free.extend(free_kw)
            
            elif field == 'legalBasis':
                # Extract legal basis - use HTML to split by <br/> tags
                if i + 1 < len(paragraphs):
                    basis_para = paragraphs[i + 1]
                    basis_html = basis_para.get('html', '')
                    basis_text = basis_para.get('text', '').strip()
                    
                    # Check if HTML contains <br/> tags for splitting
                    if '<br/>' in basis_html or '<br>' in basis_html:
                        import re
                        # Split by br tags
                        parts = re.split(r'<br/?>', basis_html)
                        for part in parts:
                            # Remove HTML tags and clean up
                            clean_text = re.sub(r'<[^>]+>', '', part)
                            # Remove newlines and normalize whitespace
                            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                            if clean_text and clean_text not in ['-', '–', '']:
                                all_legal_basis.append(clean_text)
                    elif basis_text:
                        # No HTML breaks, treat as single entry
                        all_legal_basis.append(basis_text)
        
        # Deduplicate all collected metadata while preserving order
        def dedupe_list(items):
            """Deduplicate list while preserving order."""
            seen = set()
            result = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
            return result
        
        # Apply deduplication
        all_keywords_cassation = dedupe_list(all_keywords_cassation)
        all_keywords_utu = dedupe_list(all_keywords_utu)
        all_legal_basis = dedupe_list(all_legal_basis)
        
        # For free keywords, join and deduplicate
        keywords_free_str = ' '.join(all_keywords_free) if all_keywords_free else ""
        
        # Use the first fiche number as the summary ID
        summary_id = fiche_numbers[0] if fiche_numbers else "1"
        
        # Create a single consolidated summary
        notice = {
            'summaryId': summary_id,
            'summary': summary,  # Can be empty string if no summary text found
            'keywordsCassation': all_keywords_cassation,
            'keywordsUtu': all_keywords_utu,
            'keywordsFree': keywords_free_str,
            'legalBasis': all_legal_basis
        }
        
        # Only add summary if it has any content (summary text or metadata)
        if summary or all_keywords_cassation or all_keywords_utu or keywords_free_str or all_legal_basis:
            output['summaries'].append(notice)
    
    def _process_full_text(self, section: Dict, output: Dict):
        """Process full text section."""
        paragraphs = section.get('paragraphs', [])
        
        # Extract all paragraph texts
        full_text = extract_paragraphs_text(paragraphs)
        if full_text:
            # Clean the text and remove PDF suffix
            from .utils import remove_pdf_suffix
            cleaned_text = clean_text(full_text)
            cleaned_text = remove_pdf_suffix(cleaned_text)
            # If the text is just the placeholder "<>", clear both text and HTML fields
            if cleaned_text == "<>":
                output['full_text'] = ""
                output['full_html'] = ""
            else:
                output['full_text'] = cleaned_text
                # Extract and process HTML only if we have actual content
                full_text_html = extract_paragraphs_html(paragraphs)
                if full_text_html:
                    # Clean the HTML and remove PDF suffix
                    cleaned_html = remove_pdf_suffix(full_text_html)
                    output['full_html'] = cleaned_html
        
        # Look for PDF URL
        pdf_url = extract_pdf_url(section)
        if pdf_url:
            output['url_pdf'] = pdf_url
    
    def _process_related_publications(self, section: Dict, output: Dict):
        """Process related publications section."""
        paragraphs = section.get('paragraphs', [])
        
        for i, para in enumerate(paragraphs):
            text = para.get('text', '').strip()
            if not text:
                continue
            
            # Check for various relationship types
            text_lower = text.lower()
            
            if 'citant:' in text_lower or 'citeert:' in text_lower:
                values = self._extract_related_eclis(paragraphs, i)
                if values:
                    output['citing'] = values
            
            elif 'précédents:' in text_lower or 'precedenten:' in text_lower:
                values = self._extract_related_eclis(paragraphs, i)
                if values:
                    output['precedent'] = values
            
            elif 'conclusion m.p.:' in text_lower or 'conclusie o.m.:' in text_lower:
                if i + 1 < len(paragraphs):
                    output['opinion_public_attorney'] = paragraphs[i + 1].get('text', '').strip()
            
            elif 'cité par:' in text_lower or 'geciteerd door:' in text_lower:
                values = self._extract_related_eclis(paragraphs, i)
                if values:
                    output['cited_in'] = values
            
            elif 'voir plus récemment:' in text_lower or 'zie ook recenter:' in text_lower:
                values = self._extract_related_eclis(paragraphs, i)
                if values:
                    output['see_more_recently'] = values
            
            elif 'précédé par:' in text_lower or 'voorafgegaan door:' in text_lower:
                values = self._extract_related_eclis(paragraphs, i)
                if values:
                    output['preceded_by'] = values
            
            elif 'suivi par:' in text_lower or 'gevolgd door:' in text_lower:
                values = self._extract_related_eclis(paragraphs, i)
                if values:
                    output['followed_by'] = values
            
            elif 'rectification:' in text_lower:
                values = self._extract_related_eclis(paragraphs, i)
                if values:
                    output['rectification'] = values
            
            elif 'verbonden dossier:' in text_lower:
                values = self._extract_related_eclis(paragraphs, i)
                if values:
                    output['related_case'] = values
    
    def _extract_related_eclis(self, paragraphs: List[Dict], start_idx: int) -> List[str]:
        """Extract related ECLI references."""
        eclis = []
        
        # Look through all remaining paragraphs, not just the next 10
        for i in range(start_idx + 1, len(paragraphs)):
            para = paragraphs[i]
            text = para.get('text', '').strip()
            
            # Stop if we hit another field label
            if ':' in text and any(label in text.lower() for label in 
                                 ['citant', 'citeert', 
                                  'précédent', 'precedent', 'cité', 'geciteerd',
                                  'conclusion', 'conclusie',
                                  'voir plus', 'zie ook', 'précédé', 'voorafgegaan',
                                  'suivi par', 'gevolgd door', 'rectification',
                                  'verbonden dossier']):
                break
            
            # Look for ECLI patterns
            if 'ECLI' in text:
                eclis.append(text)
            
            # Check links
            for link in para.get('links', []):
                link_text = link.get('text', '')
                if 'ECLI' in link_text:
                    eclis.append(link_text)
        
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for ecli in eclis:
            if ecli not in seen:
                seen.add(ecli)
                deduped.append(ecli)
        
        return deduped
    
    def _extract_related_links(self, paragraphs: List[Dict], start_idx: int) -> List[str]:
        """Extract related links."""
        links = []
        
        # Look through all remaining paragraphs until we hit another field label
        for i in range(start_idx + 1, len(paragraphs)):
            para = paragraphs[i]
            text = para.get('text', '').strip()
            
            # Stop if we hit another field label
            if ':' in text and any(label in text.lower() for label in 
                                 ['citant', 'citeert', 
                                  'précédent', 'precedent', 'cité', 'geciteerd',
                                  'conclusion', 'conclusie', 'voir plus', 'zie ook',
                                  'précédé', 'voorafgegaan', 'suivi par', 'gevolgd door',
                                  'rectification', 'verbonden dossier']):
                break
            
            # Check for links
            for link in para.get('links', []):
                href = link.get('href', '')
                if href:
                    links.append(href)
        
        return links
    
    def process_all(self):
        """Process all JSON files in input directory."""
        json_files = list(self.input_dir.glob("*.json"))
        self.stats['total_files'] = len(json_files)
        
        logger.info(f"Found {len(json_files)} JSON files to process")
        
        for filepath in json_files:
            output = self.transform_file(filepath)
            
            if output:
                # Check if it's a CONC (conclusion) file - skip saving those
                if output.get('decision_type_ecli_code') == 'CONC':
                    self.stats['skipped_conc'] += 1
                    logger.info(f"Skipped CONC file: {filepath.name}")
                else:
                    # Save transformed JSON
                    output_path = self.output_dir / filepath.name
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(output, f, ensure_ascii=False, indent=2)
                    
                    self.stats['successful'] += 1
                    logger.info(f"Successfully transformed: {filepath.name}")
        
        # Print statistics
        logger.info("=" * 50)
        logger.info("TRANSFORMATION COMPLETE")
        logger.info(f"Total files: {self.stats['total_files']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Skipped CONC files: {self.stats['skipped_conc']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Schema validation errors: {self.stats['validation_errors']}")
        logger.info(f"Language validation failures: {self.stats['language_invalid']}")
        valid_count = self.stats['successful'] - self.stats['language_invalid']
        logger.info(f"Files with valid language: {valid_count}/{self.stats['successful']} ({valid_count*100/self.stats['successful'] if self.stats['successful'] > 0 else 0:.1f}%)")
        logger.info("=" * 50)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Transform Juportal JSON files')
    parser.add_argument('--input', '-i', default='raw_jsons',
                      help='Input directory containing JSON files')
    parser.add_argument('--output', '-o', default='output',
                      help='Output directory for transformed files')
    parser.add_argument('--file', '-f', help='Process single file')
    parser.add_argument('--verbose', '-v', action='store_true',
                      help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    transformer = JuportalTransformer(args.input, args.output)
    
    if args.file:
        # Process single file
        filepath = Path(args.file)
        if filepath.exists():
            output = transformer.transform_file(filepath)
            if output:
                print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            logger.error(f"File not found: {args.file}")
    else:
        # Process all files
        transformer.process_all()

if __name__ == "__main__":
    main()