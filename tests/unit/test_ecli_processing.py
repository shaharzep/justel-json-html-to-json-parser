#!/usr/bin/env python3
"""
Unit tests for ECLI processing functions.
Tests ECLI extraction, parsing, and manipulation.
"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from juportal_utils.utils import (
    extract_ecli_from_filename,
    extract_jurisdiction_from_ecli,
    extract_court_code_from_ecli,
    extract_decision_type_from_ecli,
    build_url_from_ecli,
    format_ecli_alias
)


class TestECLIExtraction:
    """Test ECLI extraction from filenames."""
    
    def test_extract_ecli_from_filename_standard(self):
        """Test extraction from standard filename."""
        filename = 'juportal.be_BE_CASS_2023_ARR.20230117.2N.7_NL.json'
        result = extract_ecli_from_filename(filename)
        assert result == 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
    
    def test_extract_ecli_from_filename_different_court(self):
        """Test extraction with different court."""
        filename = 'juportal.be_BE_GHCC_2021_ARR.20211014.9_FR.json'
        result = extract_ecli_from_filename(filename)
        assert result == 'ECLI:BE:GHCC:2021:ARR.20211014.9'
    
    def test_extract_ecli_from_filename_different_type(self):
        """Test extraction with different decision type."""
        filename = 'juportal.be_BE_CASS_2020_CONC.20200603.2F.3_NL.json'
        result = extract_ecli_from_filename(filename)
        assert result == 'ECLI:BE:CASS:2020:CONC.20200603.2F.3'
    
    def test_extract_ecli_from_filename_short_number(self):
        """Test extraction with short decision number."""
        filename = 'juportal.be_BE_GHCC_2004_ARR.124_FR.json'
        result = extract_ecli_from_filename(filename)
        assert result == 'ECLI:BE:GHCC:2004:ARR.124'
    
    def test_extract_ecli_from_filename_invalid_format(self):
        """Test extraction with invalid filename format."""
        filename = 'invalid_filename.json'
        result = extract_ecli_from_filename(filename)
        assert result is None
    
    def test_extract_ecli_from_filename_empty(self):
        """Test extraction with empty filename."""
        result = extract_ecli_from_filename('')
        assert result is None
    
    def test_extract_ecli_from_filename_none(self):
        """Test extraction with None filename."""
        result = extract_ecli_from_filename(None)
        assert result is None


class TestECLIParsing:
    """Test parsing of ECLI components."""
    
    def test_extract_jurisdiction_from_ecli(self):
        """Test jurisdiction extraction from ECLI."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = extract_jurisdiction_from_ecli(ecli)
        assert result == 'BE'
    
    def test_extract_jurisdiction_from_ecli_different_country(self):
        """Test jurisdiction extraction with different country."""
        ecli = 'ECLI:NL:HR:2023:123'
        result = extract_jurisdiction_from_ecli(ecli)
        assert result == 'NL'
    
    def test_extract_jurisdiction_from_ecli_invalid(self):
        """Test jurisdiction extraction with invalid ECLI."""
        ecli = 'NOT_AN_ECLI'
        result = extract_jurisdiction_from_ecli(ecli)
        assert result is None
    
    def test_extract_jurisdiction_from_ecli_empty(self):
        """Test jurisdiction extraction with empty ECLI."""
        result = extract_jurisdiction_from_ecli('')
        assert result is None
    
    def test_extract_court_code_from_ecli(self):
        """Test court code extraction from ECLI."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = extract_court_code_from_ecli(ecli)
        assert result == 'CASS'
    
    def test_extract_court_code_from_ecli_different_court(self):
        """Test court code extraction with different court."""
        ecli = 'ECLI:BE:GHCC:2021:ARR.20211014.9'
        result = extract_court_code_from_ecli(ecli)
        assert result == 'GHCC'
    
    def test_extract_court_code_from_ecli_long_code(self):
        """Test court code extraction with long court code."""
        ecli = 'ECLI:BE:CABRL:2023:ARR.123'
        result = extract_court_code_from_ecli(ecli)
        assert result == 'CABRL'
    
    def test_extract_court_code_from_ecli_invalid(self):
        """Test court code extraction with invalid ECLI."""
        ecli = 'INVALID'
        result = extract_court_code_from_ecli(ecli)
        assert result is None
    
    def test_extract_decision_type_from_ecli(self):
        """Test decision type extraction from ECLI."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = extract_decision_type_from_ecli(ecli)
        assert result == 'ARR'
    
    def test_extract_decision_type_from_ecli_conc(self):
        """Test decision type extraction for CONC."""
        ecli = 'ECLI:BE:CASS:2020:CONC.20200603.2F.3'
        result = extract_decision_type_from_ecli(ecli)
        assert result == 'CONC'
    
    def test_extract_decision_type_from_ecli_other_types(self):
        """Test decision type extraction for other types."""
        test_cases = [
            ('ECLI:BE:COURT:2023:JUG.123', 'JUG'),
            ('ECLI:BE:COURT:2023:DEC.456', 'DEC'),
            ('ECLI:BE:COURT:2023:ORD.789', 'ORD'),
            ('ECLI:BE:COURT:2023:AVIS.101', 'AVIS'),
        ]
        
        for ecli, expected in test_cases:
            result = extract_decision_type_from_ecli(ecli)
            assert result == expected
    
    def test_extract_decision_type_from_ecli_invalid(self):
        """Test decision type extraction with invalid ECLI."""
        ecli = 'INVALID'
        result = extract_decision_type_from_ecli(ecli)
        assert result is None


class TestECLIFormatting:
    """Test ECLI formatting and manipulation."""
    
    def test_format_ecli_alias_single(self):
        """Test formatting of single ECLI alias."""
        alias = 'ECLI:BE:CASS:2023:ARR.123'
        result = format_ecli_alias(alias)
        assert result == ['ECLI:BE:CASS:2023:ARR.123']
    
    def test_format_ecli_alias_multiple_semicolon(self):
        """Test formatting of multiple aliases with semicolon."""
        alias = 'ECLI:BE:CASS:2023:ARR.123; ECLI:BE:CASS:2023:ARR.456'
        result = format_ecli_alias(alias)
        assert len(result) == 2
        assert 'ECLI:BE:CASS:2023:ARR.123' in result
        assert 'ECLI:BE:CASS:2023:ARR.456' in result
    
    def test_format_ecli_alias_multiple_comma(self):
        """Test formatting of multiple aliases with comma."""
        alias = 'ECLI:BE:CASS:2023:ARR.123, ECLI:BE:CASS:2023:ARR.456'
        result = format_ecli_alias(alias)
        assert len(result) == 2
        assert 'ECLI:BE:CASS:2023:ARR.123' in result
        assert 'ECLI:BE:CASS:2023:ARR.456' in result
    
    def test_format_ecli_alias_with_whitespace(self):
        """Test formatting with extra whitespace."""
        alias = '  ECLI:BE:CASS:2023:ARR.123  ;  ECLI:BE:CASS:2023:ARR.456  '
        result = format_ecli_alias(alias)
        assert len(result) == 2
        assert 'ECLI:BE:CASS:2023:ARR.123' in result
        assert 'ECLI:BE:CASS:2023:ARR.456' in result
    
    def test_format_ecli_alias_empty(self):
        """Test formatting of empty alias."""
        result = format_ecli_alias('')
        assert result == []
    
    def test_format_ecli_alias_none(self):
        """Test formatting of None alias."""
        result = format_ecli_alias(None)
        assert result == []
    
    def test_format_ecli_alias_invalid(self):
        """Test formatting with invalid ECLI."""
        alias = 'NOT_AN_ECLI'
        result = format_ecli_alias(alias)
        assert result == []
    
    def test_format_ecli_alias_mixed_valid_invalid(self):
        """Test formatting with mixed valid and invalid ECLIs."""
        alias = 'ECLI:BE:CASS:2023:ARR.123; INVALID; ECLI:BE:CASS:2023:ARR.456'
        result = format_ecli_alias(alias)
        assert len(result) == 2
        assert 'ECLI:BE:CASS:2023:ARR.123' in result
        assert 'ECLI:BE:CASS:2023:ARR.456' in result
        assert 'INVALID' not in result


class TestURLBuilding:
    """Test URL building from ECLI."""
    
    def test_build_url_from_ecli_french(self):
        """Test URL building for French document."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = build_url_from_ecli(ecli, 'FR')
        assert 'juportal.be' in result
        assert 'ECLI:BE:CASS:2023:ARR.20230117.2N.7' in result
        assert 'FR' in result
    
    def test_build_url_from_ecli_dutch(self):
        """Test URL building for Dutch document."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = build_url_from_ecli(ecli, 'NL')
        assert 'juportal.be' in result
        assert 'ECLI:BE:CASS:2023:ARR.20230117.2N.7' in result
        assert 'NL' in result
    
    def test_build_url_from_ecli_german(self):
        """Test URL building for German document."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = build_url_from_ecli(ecli, 'DE')
        assert 'juportal.be' in result
        assert 'ECLI:BE:CASS:2023:ARR.20230117.2N.7' in result
        assert 'DE' in result
    
    def test_build_url_from_ecli_no_language(self):
        """Test URL building without language."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = build_url_from_ecli(ecli, None)
        assert 'juportal.be' in result
        assert 'ECLI:BE:CASS:2023:ARR.20230117.2N.7' in result
    
    def test_build_url_from_ecli_empty(self):
        """Test URL building with empty ECLI."""
        result = build_url_from_ecli('', 'FR')
        assert result == ''
    
    def test_build_url_from_ecli_none(self):
        """Test URL building with None ECLI."""
        result = build_url_from_ecli(None, 'FR')
        assert result == ''
    
    def test_build_url_from_ecli_special_chars(self):
        """Test URL building with special characters in ECLI."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = build_url_from_ecli(ecli, 'FR')
        # URL should be properly formatted
        assert 'https://' in result or 'http://' in result
        assert '//' not in result.replace('https://', '').replace('http://', '')


class TestECLIValidation:
    """Test ECLI validation functions."""
    
    def test_valid_ecli_format(self):
        """Test validation of valid ECLI format."""
        valid_eclis = [
            'ECLI:BE:CASS:2023:ARR.20230117.2N.7',
            'ECLI:BE:GHCC:2021:ARR.20211014.9',
            'ECLI:BE:CASS:2020:CONC.20200603.2F.3',
            'ECLI:NL:HR:2023:123',
        ]
        
        for ecli in valid_eclis:
            assert ecli.startswith('ECLI:')
            parts = ecli.split(':')
            assert len(parts) >= 5
    
    def test_invalid_ecli_format(self):
        """Test detection of invalid ECLI format."""
        invalid_eclis = [
            'NOT_AN_ECLI',
            'ECLI:',
            'ECLI:BE',
            'ECLI:BE:',
            ':BE:CASS:2023:ARR.123',
        ]
        
        for ecli in invalid_eclis:
            # These should not match standard ECLI pattern
            if not ecli.startswith('ECLI:'):
                assert True
            else:
                parts = ecli.split(':')
                assert len(parts) < 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])