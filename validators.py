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
    
    def __init__(self, schema_path: str = "schema.json"):
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
            'fileName',
            'ecli', 
            'url',
            'source',
            'metaLanguage'
        ]
    
    def _get_field_types(self) -> Dict[str, type]:
        """Define expected types for each field."""
        return {
            'fileName': str,
            'ecli': str,
            'url': str,
            'source': str,
            'metaLanguage': str,
            'jurisdiction': str,
            'courtEcliCode': str,
            'decisionTypeEcliCode': str,
            'decisionDate': str,
            'ecliAlias': list,
            'rolNumber': str,
            'case': str,
            'chamber': str,
            'fieldOfLaw': str,
            'versions': list,
            'opinionPublicAttorney': str,
            'notices': list,
            'fullText': str,
            'fullTextHtml': str,
            'pdfUrl': str,
            'relatedPublications': dict,
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
        
        # Validate notices structure
        if 'notices' in data and isinstance(data['notices'], list):
            for i, notice in enumerate(data['notices']):
                notice_errors = self._validate_notice(notice, i)
                errors.extend(notice_errors)
        
        # Validate related publications structure
        if 'relatedPublications' in data and isinstance(data['relatedPublications'], dict):
            rel_errors = self._validate_related_publications(data['relatedPublications'])
            errors.extend(rel_errors)
        
        # Validate date format
        if 'decisionDate' in data and data['decisionDate']:
            if not self._is_valid_date(data['decisionDate']):
                errors.append(f"Invalid date format for 'decisionDate': {data['decisionDate']}")
        
        # Validate URL format
        if 'url' in data and data['url']:
            if not data['url'].startswith('https://juportal.be/'):
                errors.append(f"Invalid URL format: {data['url']}")
        
        # Validate ECLI format
        if 'ecli' in data and data['ecli']:
            if not data['ecli'].startswith('ECLI:'):
                errors.append(f"Invalid ECLI format: {data['ecli']}")
        
        return len(errors) == 0, errors
    
    def _validate_notice(self, notice: Dict, index: int) -> List[str]:
        """Validate notice structure."""
        errors = []
        
        if not isinstance(notice, dict):
            errors.append(f"Notice at index {index} is not a dictionary")
            return errors
        
        # Check notice fields
        notice_fields = {
            'noticeId': str,
            'summary': str,
            'keywordsCassation': list,
            'keywordsUtu': list,
            'keywordsFree': str,  # Note: This should be a string, not an array
            'legalBasis': list
        }
        
        for field, expected_type in notice_fields.items():
            if field in notice and notice[field] is not None:
                if expected_type == list and not isinstance(notice[field], list):
                    errors.append(f"Notice {index}: '{field}' should be a list")
                elif expected_type == str and not isinstance(notice[field], str):
                    errors.append(f"Notice {index}: '{field}' should be a string")
        
        return errors
    
    def _validate_related_publications(self, rel_pub: Dict) -> List[str]:
        """Validate related publications structure."""
        errors = []
        
        # Fields that should be lists
        list_fields = ['citing', 'precedent', 'cited in', 'justel', 
                      'seeMoreRecently', 'precededBy', 'followedBy', 
                      'rectification', 'relatedCase']
        
        # Fields that should be strings
        string_fields = ['decision', 'opinionPublicAttorney']
        
        for field in list_fields:
            if field in rel_pub and rel_pub[field] is not None:
                if not isinstance(rel_pub[field], list):
                    errors.append(f"Related publications '{field}' should be a list")
        
        for field in string_fields:
            if field in rel_pub and rel_pub[field] is not None:
                if not isinstance(rel_pub[field], str):
                    errors.append(f"Related publications '{field}' should be a string")
        
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
            "fileName": "...",
            "ecli": "...",
            "url": "https://juportal.be/content/...",
            "source": "juportal.be",
            "metaLanguage": "...",
            "jurisdiction": "BE",
            "courtEcliCode": "...",
            "decisionTypeEcliCode": "...",
            "decisionDate": "...",
            "ecliAlias": ["..."],
            "rolNumber": "...",
            "case": "...",
            "chamber": "...",
            "fieldOfLaw": "...",
            "versions": ["..."],
            "opinionPublicAttorney": "...",
            "notices": [
                {
                    "noticeId": "...",
                    "summary": "...",
                    "keywordsCassation": ["..."],
                    "keywordsUtu": ["..."],
                    "keywordsFree": "...",
                    "legalBasis": ["..."]
                }
            ],
            "fullText": "...",
            "fullTextHtml": "...",
            "pdfUrl": "https://juportal.be/JUPORTAwork/...",
            "relatedPublications": {
                "decision": "...",
                "citing": ["..."],
                "precedent": ["..."],
                "opinionPublicAttorney": "...",
                "cited in": ["..."],
                "justel": ["..."],
                "seeMoreRecently": ["..."],
                "precededBy": ["..."],
                "followedBy": ["..."],
                "rectification": ["..."],
                "relatedCase": ["..."]
            },
            "isValid": True
        }
    
    def create_empty_document(self) -> Dict:
        """Create an empty document with all fields initialized."""
        return {
            "fileName": None,
            "ecli": None,
            "url": None,
            "source": "juportal.be",
            "metaLanguage": None,
            "jurisdiction": "BE",
            "courtEcliCode": None,
            "decisionTypeEcliCode": None,
            "decisionDate": None,
            "ecliAlias": [],
            "rolNumber": None,
            "case": None,
            "chamber": None,
            "fieldOfLaw": None,
            "versions": [],
            "opinionPublicAttorney": None,
            "notices": [],
            "fullText": None,
            "fullTextHtml": None,
            "pdfUrl": None,
            "relatedPublications": {
                "decision": None,
                "citing": [],
                "precedent": [],
                "opinionPublicAttorney": None,
                "cited in": [],
                "justel": [],
                "seeMoreRecently": [],
                "precededBy": [],
                "followedBy": [],
                "rectification": [],
                "relatedCase": []
            },
            "isValid": False
        }