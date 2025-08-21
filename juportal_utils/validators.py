"""
Schema validation functions for Juportal JSON transformation.
Validates transformed data against the target schema.
"""

import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SchemaValidator:
    """Validates transformed JSON against Juportal schema."""
    
    def __init__(self, schema_path: str = "schemas/schema.json"):
        """Initialize validator with schema."""
        self.schema = self._load_schema(schema_path)
        self.required_fields = self._get_required_fields()
        self.field_types = self._get_field_types()
        
    def _load_schema(self, schema_path: str) -> Dict:
        """Load schema from JSON file."""
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Schema file {schema_path} not found, using default schema")
            return self._get_default_schema()
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing schema JSON: {e}")
            return self._get_default_schema()
    
    def _get_required_fields(self) -> List[str]:
        """Get list of required fields from schema."""
        # These fields should always be present
        return [
            'file_name',
            'decision_id', 
            'url_official_publication',
            'source',
            'language_metadata'
        ]
    
    def _get_field_types(self) -> Dict[str, type]:
        """Define expected types for each field."""
        return {
            'file_name': str,
            'decision_id': str,
            'url_official_publication': str,
            'source': str,
            'language_metadata': str,
            'jurisdiction': str,
            'court_ecli_code': str,
            'decision_type_ecli_code': str,
            'decision_date': str,
            'ecli_alias': list,
            'rol_number': str,
            'case': str,
            'chamber': str,
            'field_of_law': str,
            'versions': list,
            'opinion_public_attorney': str,
            'summaries': list,
            'full_text': str,
            'full_html': str,
            'url_pdf': str,
            'citing': list,
            'precedent': list,
            'cited_in': list,
            'see_more_recently': list,
            'preceded_by': list,
            'followed_by': list,
            'rectification': list,
            'related_case': list,
            'isValid': bool
        }
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate transformed data against schema.
        Returns (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        for field in self.required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Required field '{field}' is missing or null")
        
        # Check field types
        for field, expected_type in self.field_types.items():
            if field in data and data[field] is not None:
                actual_type = type(data[field])
                if expected_type == list and not isinstance(data[field], list):
                    errors.append(f"Field '{field}' should be a list, got {actual_type.__name__}")
                elif expected_type == dict and not isinstance(data[field], dict):
                    errors.append(f"Field '{field}' should be a dict, got {actual_type.__name__}")
                elif expected_type == str and not isinstance(data[field], str):
                    errors.append(f"Field '{field}' should be a string, got {actual_type.__name__}")
                elif expected_type == bool and not isinstance(data[field], bool):
                    errors.append(f"Field '{field}' should be a boolean, got {actual_type.__name__}")
        
        # Validate summaries structure
        if 'summaries' in data and isinstance(data['summaries'], list):
            for i, summary in enumerate(data['summaries']):
                summary_errors = self._validate_summary(summary, i)
                errors.extend(summary_errors)
        
        # Validate related publications fields (now at top level)
        rel_errors = self._validate_related_publications_fields(data)
        errors.extend(rel_errors)
        
        # Validate date format
        if 'decision_date' in data and data['decision_date']:
            if not self._is_valid_date(data['decision_date']):
                errors.append(f"Invalid date format for 'decision_date': {data['decision_date']}")
        
        # Validate URL format
        if 'url_official_publication' in data and data['url_official_publication']:
            if not data['url_official_publication'].startswith('https://juportal.be/'):
                errors.append(f"Invalid URL format: {data['url_official_publication']}")
        
        # Validate ECLI format
        if 'decision_id' in data and data['decision_id']:
            if not data['decision_id'].startswith('ECLI:'):
                errors.append(f"Invalid ECLI format: {data['decision_id']}")
        
        return len(errors) == 0, errors
    
    def _validate_summary(self, summary: Dict, index: int) -> List[str]:
        """Validate summary structure."""
        errors = []
        
        if not isinstance(summary, dict):
            errors.append(f"Summary at index {index} is not a dictionary")
            return errors
        
        # Check summary fields
        summary_fields = {
            'summaryId': str,
            'summary': str,
            'keywordsCassation': list,
            'keywordsUtu': list,
            'keywordsFree': str,  # Note: This should be a string, not an array
            'legalBasis': list
        }
        
        for field, expected_type in summary_fields.items():
            if field in summary and summary[field] is not None:
                if expected_type == list and not isinstance(summary[field], list):
                    errors.append(f"Summary {index}: '{field}' should be a list")
                elif expected_type == str and not isinstance(summary[field], str):
                    errors.append(f"Summary {index}: '{field}' should be a string")
        
        return errors
    
    def _validate_related_publications_fields(self, data: Dict) -> List[str]:
        """Validate related publications fields (now at top level)."""
        errors = []
        
        # Fields that should be lists
        list_fields = ['citing', 'precedent', 'cited_in', 
                      'see_more_recently', 'preceded_by', 'followed_by', 
                      'rectification', 'related_case']
        
        # Fields that should be strings
        string_fields = []
        
        for field in list_fields:
            if field in data and data[field] is not None:
                if not isinstance(data[field], list):
                    errors.append(f"Field '{field}' should be a list")
        
        for field in string_fields:
            if field in data and data[field] is not None:
                if not isinstance(data[field], str):
                    errors.append(f"Field '{field}' should be a string")
        
        return errors
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string is in valid format."""
        # Accept YYYY-MM-DD or just YYYY
        if len(date_str) == 4:  # Just year
            try:
                year = int(date_str)
                return 1900 <= year <= 2100
            except ValueError:
                return False
        
        # Try to parse as full date
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _get_default_schema(self) -> Dict:
        """Return default schema structure."""
        return {
            "file_name": "...",
            "decision_id": "...",
            "url_official_publication": "https://juportal.be/content/...",
            "source": "juportal.be",
            "language_metadata": "...",
            "jurisdiction": "BE",
            "court_ecli_code": "...",
            "decision_type_ecli_code": "...",
            "decision_date": "...",
            "ecli_alias": ["..."],
            "rol_number": "...",
            "case": "...",
            "chamber": "...",
            "field_of_law": "...",
            "versions": ["..."],
            "opinion_public_attorney": "...",
            "summaries": [
                {
                    "summaryId": "...",
                    "summary": "...",
                    "keywordsCassation": ["..."],
                    "keywordsUtu": ["..."],
                    "keywordsFree": "...",
                    "legalBasis": ["..."]
                }
            ],
            "full_text": "...",
            "full_html": "...",
            "url_pdf": "https://juportal.be/JUPORTAwork/...",
            "citing": ["..."],
            "precedent": ["..."],
            "cited_in": ["..."],
            "see_more_recently": ["..."],
            "preceded_by": ["..."],
            "followed_by": ["..."],
            "rectification": ["..."],
            "related_case": ["..."],
            "isValid": True
        }
    
    def create_empty_document(self) -> Dict:
        """Create an empty document with all fields initialized."""
        return {
            "file_name": None,
            "decision_id": None,
            "url_official_publication": None,
            "source": "juportal.be",
            "language_metadata": None,
            "jurisdiction": "BE",
            "court_ecli_code": None,
            "decision_type_ecli_code": None,
            "decision_date": None,
            "ecli_alias": [],
            "rol_number": None,
            "case": None,
            "chamber": None,
            "field_of_law": None,
            "versions": [],
            "opinion_public_attorney": None,
            "summaries": [],
            "full_text": None,
            "full_html": None,
            "url_pdf": None,
            "citing": [],
            "precedent": [],
            "cited_in": [],
            "see_more_recently": [],
            "preceded_by": [],
            "followed_by": [],
            "rectification": [],
            "related_case": [],
            "isValid": False
        }