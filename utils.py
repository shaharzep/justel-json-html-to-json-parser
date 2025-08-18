"""
Utility functions for Juportal JSON transformation.
Handles date extraction, text processing, and data manipulation.
"""

import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# Month names in different languages
MONTH_NAMES = {
    'fr': {
        'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
        'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
    },
    'nl': {
        'januari': 1, 'februari': 2, 'maart': 3, 'april': 4, 'mei': 5, 'juni': 6,
        'juli': 7, 'augustus': 8, 'september': 9, 'oktober': 10, 'november': 11, 'december': 12
    },
    'de': {
        'januar': 1, 'februar': 2, 'märz': 3, 'april': 4, 'mai': 5, 'juni': 6,
        'juli': 7, 'august': 8, 'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12
    }
}

def extract_language_from_filename(filename: str) -> str:
    """Extract language code from filename."""
    # Look for _FR, _NL, _DE pattern
    match = re.search(r'_(FR|NL|DE)\.json$', filename, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return 'FR'  # Default to French

def extract_ecli_from_filename(filename: str) -> Optional[str]:
    """Extract ECLI from filename."""
    # Pattern: juportal.be_BE_COURT_YEAR_TYPE.DATE.NUM_LANG.json
    # Example: juportal.be_BE_CASS_2007_ARR.20070622.5_FR.json
    # Should become: ECLI:BE:CASS:2007:ARR.20070622.5
    
    match = re.search(r'juportal\.be_BE_([A-Z]+)_(\d{4})_([A-Z]+)\.([^_]+)_[A-Z]{2}\.json', filename)
    if match:
        court = match.group(1)
        year = match.group(2)
        decision_type = match.group(3)
        rest = match.group(4)  # This includes the date and number part
        
        return f"ECLI:BE:{court}:{year}:{decision_type}.{rest}"
    return None

def extract_date_from_ecli(ecli: str) -> Optional[str]:
    """Extract date from ECLI string."""
    # ECLI format: ECLI:BE:COURT:YEAR:TYPE.YYYYMMDD.NUM
    # or ECLI:BE:COURT:YEAR:TYPE.NUM (for 3-digit dates)
    
    # Try to extract 8-digit date (YYYYMMDD)
    match = re.search(r':(\d{4}):.*?\.(\d{8})\.', ecli)
    if match:
        date_str = match.group(2)
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            pass
    
    # Try to extract year from ECLI for 3-digit dates
    year_match = re.search(r':(\d{4}):', ecli)
    if year_match:
        return year_match.group(1)  # Return just the year for now
    
    return None

def extract_date_from_legend(legend: str, language: str = 'FR') -> Optional[str]:
    """Extract date from decision card legend."""
    patterns = {
        'FR': r"du\s+(\d{1,2})\s+(\w+)\s+(\d{4})",
        'NL': r"van\s+(\d{1,2})\s+(\w+)\s+(\d{4})",
        'DE': r"vom\s+(\d{1,2})\s+(\w+)\s+(\d{4})"
    }
    
    pattern = patterns.get(language.upper(), patterns['FR'])
    match = re.search(pattern, legend, re.IGNORECASE)
    
    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        
        # Get month number from month name
        month_dict = MONTH_NAMES.get(language.lower(), MONTH_NAMES['fr'])
        month = month_dict.get(month_name, 0)
        
        if month > 0:
            try:
                date_obj = datetime(year, month, day)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass
    
    return None

def extract_court_code_from_ecli(ecli: str) -> Optional[str]:
    """Extract court code from ECLI."""
    match = re.search(r'ECLI:BE:([A-Z]+):', ecli)
    if match:
        return match.group(1)
    return None

def extract_decision_type_from_ecli(ecli: str) -> Optional[str]:
    """Extract decision type from ECLI."""
    match = re.search(r'ECLI:BE:[A-Z]+:\d{4}:([A-Z]+)', ecli)
    if match:
        return match.group(1)
    return None

def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    # Remove empty lines
    text = re.sub(r'\n\s*\n', '\n', text)
    
    return text

def remove_pdf_suffix(text: str) -> str:
    """Remove the 'Document PDF ECLI:...' or 'PDF document ECLI:...' suffix from text."""
    if not text:
        return ""
    
    # Pattern to match both variations at the end of text
    # Matches "Document PDF ECLI:..." or "PDF document ECLI:..." at the end
    pattern = r'\s*(Document\s+PDF|PDF\s+document)\s+ECLI:[A-Z]{2}:[A-Z0-9]+:\d{4}:[\w\.\-]+\s*$'
    
    # Remove the pattern from the end of the text
    cleaned = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    return cleaned.strip()

def extract_paragraphs_text(paragraphs: List[Dict]) -> str:
    """Extract and combine text from paragraphs array."""
    texts = []
    for para in paragraphs:
        if isinstance(para, dict) and 'text' in para:
            text = para.get('text', '').strip()
            if text:
                texts.append(text)
    
    return '\n'.join(texts)

def extract_field_value_from_paragraphs(paragraphs: List[Dict], field_label: str) -> Optional[str]:
    """Extract value following a specific field label in paragraphs."""
    found_label = False
    
    for para in paragraphs:
        if not isinstance(para, dict):
            continue
            
        text = para.get('text', '').strip()
        if not text:
            continue
        
        # Check if this paragraph contains the label
        if field_label.lower() in text.lower():
            found_label = True
            # Check if value is in the same paragraph after colon
            if ':' in text:
                parts = text.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        elif found_label:
            # Next paragraph after label contains the value
            return text
    
    return None

def extract_links_from_paragraph(paragraph: Dict) -> List[Dict[str, str]]:
    """Extract links from a paragraph."""
    links = []
    
    # Check for links array in paragraph
    if 'links' in paragraph and isinstance(paragraph['links'], list):
        for link in paragraph['links']:
            if isinstance(link, dict) and 'href' in link:
                links.append({
                    'href': link.get('href', ''),
                    'text': link.get('text', '')
                })
    
    return links

def parse_legal_basis(text: str, links: List[Dict] = None) -> List[str]:
    """Parse legal basis text into array of references."""
    if not text:
        return []
    
    bases = []
    
    # Split by common separators
    parts = re.split(r'[\n;]', text)
    
    for part in parts:
        part = part.strip()
        if part:
            # Clean up the legal basis text
            part = re.sub(r'\s+', ' ', part)
            bases.append(part)
    
    return bases

def extract_pdf_url(section: Dict) -> Optional[str]:
    """Extract PDF URL from a section."""
    # Look for links in paragraphs
    for para in section.get('paragraphs', []):
        for link in para.get('links', []):
            href = link.get('href', '')
            if '/JUPORTAwork/' in href:
                # Construct full URL
                if href.startswith('/'):
                    return f"https://juportal.be{href}"
                return href
    
    return None

def merge_keyword_values(paragraphs: List[Dict], start_idx: int, keyword_type: str = 'free') -> List[str]:
    """
    Merge keyword values that might span multiple paragraphs.
    
    Args:
        paragraphs: List of paragraph dictionaries
        start_idx: Index of the paragraph containing the field label
        keyword_type: Type of keyword ('cassation', 'utu', or 'free')
    
    Returns:
        List of keyword strings
    """
    keywords = []
    
    # Start from the paragraph after the label
    for i in range(start_idx + 1, len(paragraphs)):
        para = paragraphs[i]
        text = para.get('text', '').strip()
        
        # Stop if we hit another field label
        if any(label in text for label in [':', 'Thésaurus', 'Thesaurus', 'Mots libres', 
                                           'Vrije woorden', 'Bases légales', 'Wettelijke bepalingen']):
            break
        
        if text or para.get('html', ''):
            # Different splitting logic based on keyword type
            if keyword_type in ['cassation', 'utu']:
                # Check if HTML contains <br/> tags for splitting
                html = para.get('html', '')
                if '<br/>' in html or '<br>' in html:
                    # Split by <br/> or <br> tags in HTML
                    # Split by br tags
                    parts = re.split(r'<br/?>', html)
                    for part in parts:
                        # Remove all HTML tags and clean up
                        clean_text = re.sub(r'<[^>]+>', '', part).strip()
                        if clean_text and clean_text not in ['-', '–', '']:
                            keywords.append(clean_text)
                elif text:
                    # No HTML breaks, treat as single keyword
                    keywords.append(text)
            else:
                # For free keywords, split by common punctuation
                if text:
                    parts = re.split(r'[;,\n]', text)
                    for part in parts:
                        part = part.strip()
                        if part and part not in ['-', '–']:
                            keywords.append(part)
    
    return keywords

def build_url_from_ecli(ecli: str, language: str) -> str:
    """Build Juportal URL from ECLI and language."""
    return f"https://juportal.be/content/{ecli}/{language.upper()}"

def safe_get(dictionary: Dict, *keys, default=None) -> Any:
    """Safely get nested dictionary values."""
    value = dictionary
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default
    return value

def format_ecli_alias(text: str) -> List[str]:
    """Format ECLI alias values into array."""
    if not text:
        return []
    
    # Split by common separators
    aliases = []
    parts = re.split(r'[;,\n]', text)
    
    for part in parts:
        part = part.strip()
        if part and 'ECLI' in part:
            aliases.append(part)
    
    return aliases if aliases else []

def parse_versions(paragraphs: List[Dict], start_idx: int) -> List[str]:
    """Parse version links from paragraphs."""
    versions = []
    
    # Look for version links in subsequent paragraphs
    for i in range(start_idx + 1, min(start_idx + 5, len(paragraphs))):
        para = paragraphs[i]
        
        # Check for links
        links = para.get('links', [])
        for link in links:
            text = link.get('text', '')
            if any(word in text.lower() for word in ['traduction', 'origineel', 'version']):
                versions.append(text)
        
        # Also check text
        text = para.get('text', '').strip()
        if text and any(word in text.lower() for word in ['traduction', 'origineel', 'version']):
            if text not in versions:
                versions.append(text)
    
    return versions