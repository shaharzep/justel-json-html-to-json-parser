#!/usr/bin/env python3
"""
Unit tests for date extraction from various sources.
Tests ECLI date extraction, legend date extraction, and LLM fallback.
"""

import pytest
from datetime import datetime
from pathlib import Path
import sys
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from juportal_utils.utils import (
    extract_date_from_ecli,
    extract_date_from_legend,
    extract_date_with_llm_fallback
)


class TestECLIDateExtraction:
    """Test date extraction from ECLI strings."""
    
    def test_extract_date_from_ecli_full_date(self):
        """Test extraction of full date from ECLI."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = extract_date_from_ecli(ecli)
        assert result == '2023-01-17'
    
    def test_extract_date_from_ecli_different_format(self):
        """Test extraction from different ECLI format."""
        ecli = 'ECLI:BE:GHCC:2021:ARR.20211014.9'
        result = extract_date_from_ecli(ecli)
        assert result == '2021-10-14'
    
    def test_extract_date_from_ecli_year_only(self):
        """Test extraction when only year is available."""
        ecli = 'ECLI:BE:CASS:2023:ARR.123'
        result = extract_date_from_ecli(ecli)
        assert result == '2023'
    
    def test_extract_date_from_ecli_no_date(self):
        """Test extraction when no date is present."""
        ecli = 'ECLI:BE:CASS:ARR.ABC'
        result = extract_date_from_ecli(ecli)
        assert result is None
    
    def test_extract_date_from_ecli_invalid_date(self):
        """Test extraction with invalid date format."""
        ecli = 'ECLI:BE:CASS:2023:ARR.99999999.1'
        result = extract_date_from_ecli(ecli)
        # Should return year when full date is invalid
        assert result == '2023'
    
    def test_extract_date_from_ecli_empty(self):
        """Test extraction with empty ECLI."""
        result = extract_date_from_ecli('')
        assert result is None
    
    def test_extract_date_from_ecli_none(self):
        """Test extraction with None ECLI."""
        # The function doesn't handle None gracefully, it expects a string
        # So we should catch the exception or skip this test
        with pytest.raises(TypeError):
            extract_date_from_ecli(None)


class TestLegendDateExtraction:
    """Test date extraction from legend text."""
    
    def test_extract_date_from_legend_french(self):
        """Test extraction from French legend."""
        legend = 'Jugement/arrêt du 15 mars 2023'
        result = extract_date_from_legend(legend, 'FR')
        assert result == '2023-03-15'
    
    def test_extract_date_from_legend_dutch(self):
        """Test extraction from Dutch legend."""
        legend = 'Vonnis/arrest van 17 januari 2023'
        result = extract_date_from_legend(legend, 'NL')
        assert result == '2023-01-17'
    
    def test_extract_date_from_legend_german(self):
        """Test extraction from German legend."""
        legend = 'Urteil vom 20 Februar 2023'
        result = extract_date_from_legend(legend, 'DE')
        assert result == '2023-02-20'
    
    def test_extract_date_from_legend_with_beschikking(self):
        """Test extraction from Dutch legend with Beschikking."""
        legend = 'Beschikking van 10 februari 2023'
        result = extract_date_from_legend(legend, 'NL')
        assert result == '2023-02-10'
    
    def test_extract_date_from_legend_invalid_month(self):
        """Test extraction with invalid month name."""
        legend = 'Jugement/arrêt du 15 invalidmonth 2023'
        result = extract_date_from_legend(legend, 'FR')
        assert result is None
    
    def test_extract_date_from_legend_no_match(self):
        """Test extraction when pattern doesn't match."""
        legend = 'Some random text without date'
        result = extract_date_from_legend(legend, 'FR')
        assert result is None
    
    def test_extract_date_from_legend_invalid_day(self):
        """Test extraction with invalid day value."""
        legend = 'Jugement/arrêt du 32 mars 2023'
        result = extract_date_from_legend(legend, 'FR')
        assert result is None
    
    def test_extract_date_from_legend_all_months_french(self):
        """Test all French month names."""
        months = [
            ('janvier', 1), ('février', 2), ('mars', 3), ('avril', 4),
            ('mai', 5), ('juin', 6), ('juillet', 7), ('août', 8),
            ('septembre', 9), ('octobre', 10), ('novembre', 11), ('décembre', 12)
        ]
        
        for month_name, month_num in months:
            legend = f'Jugement/arrêt du 15 {month_name} 2023'
            result = extract_date_from_legend(legend, 'FR')
            expected = f'2023-{month_num:02d}-15'
            assert result == expected, f"Failed for month {month_name}"
    
    def test_extract_date_from_legend_all_months_dutch(self):
        """Test all Dutch month names."""
        months = [
            ('januari', 1), ('februari', 2), ('maart', 3), ('april', 4),
            ('mei', 5), ('juni', 6), ('juli', 7), ('augustus', 8),
            ('september', 9), ('oktober', 10), ('november', 11), ('december', 12)
        ]
        
        for month_name, month_num in months:
            legend = f'Vonnis/arrest van 15 {month_name} 2023'
            result = extract_date_from_legend(legend, 'NL')
            expected = f'2023-{month_num:02d}-15'
            assert result == expected, f"Failed for month {month_name}"
    
    def test_extract_date_from_legend_case_insensitive(self):
        """Test that month matching is case insensitive."""
        legend = 'Jugement/arrêt du 15 MARS 2023'
        result = extract_date_from_legend(legend, 'FR')
        assert result == '2023-03-15'
        
        legend = 'Jugement/arrêt du 15 Mars 2023'
        result = extract_date_from_legend(legend, 'FR')
        assert result == '2023-03-15'


class TestLLMFallbackDateExtraction:
    """Test LLM fallback for date extraction."""
    
    @patch('juportal_utils.llm_validator.LLMValidator')
    def test_llm_fallback_successful(self, mock_llm_class):
        """Test successful date extraction via LLM."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.is_available.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='2023-03-15'))]
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        legend = 'Some complex text with date 15 March 2023'
        result = extract_date_with_llm_fallback(legend, 'FR')
        
        assert result == '2023-03-15'
        mock_llm.client.chat.completions.create.assert_called_once()
    
    @patch('juportal_utils.llm_validator.LLMValidator')
    def test_llm_fallback_no_date_found(self, mock_llm_class):
        """Test LLM returns NO_DATE when no date found."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.is_available.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='NO_DATE'))]
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        legend = 'Text without any date'
        result = extract_date_with_llm_fallback(legend, 'FR')
        
        assert result is None
    
    @patch('juportal_utils.llm_validator.LLMValidator')
    def test_llm_fallback_invalid_format(self, mock_llm_class):
        """Test LLM returns invalid date format."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.is_available.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='15/03/2023'))]  # Wrong format
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        legend = 'Text with date'
        result = extract_date_with_llm_fallback(legend, 'FR')
        
        assert result is None
    
    @patch('juportal_utils.llm_validator.LLMValidator')
    def test_llm_fallback_not_available(self, mock_llm_class):
        """Test when LLM is not available."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.is_available.return_value = False
        mock_llm_class.return_value = mock_llm
        
        legend = 'Text with date'
        result = extract_date_with_llm_fallback(legend, 'FR')
        
        assert result is None
        mock_llm.client.chat.completions.create.assert_not_called()
    
    @patch('juportal_utils.llm_validator.LLMValidator')
    def test_llm_fallback_exception(self, mock_llm_class):
        """Test when LLM raises an exception."""
        # Setup mock to raise exception
        mock_llm = Mock()
        mock_llm.is_available.return_value = True
        mock_llm.client.chat.completions.create.side_effect = Exception('API Error')
        mock_llm_class.return_value = mock_llm
        
        legend = 'Text with date'
        result = extract_date_with_llm_fallback(legend, 'FR')
        
        assert result is None
    
    @patch('juportal_utils.llm_validator.LLMValidator')
    def test_llm_fallback_invalid_date_value(self, mock_llm_class):
        """Test when LLM returns an invalid date (e.g., Feb 30)."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.is_available.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='2023-02-30'))]  # Invalid date
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        legend = 'Text with invalid date'
        result = extract_date_with_llm_fallback(legend, 'FR')
        
        assert result is None


class TestDateExtractionIntegration:
    """Integration tests for date extraction pipeline."""
    
    def test_date_extraction_priority(self):
        """Test that date extraction follows the correct priority."""
        # ECLI date should take priority
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        result = extract_date_from_ecli(ecli)
        assert result == '2023-01-17'
        
        # Legend date should be used when ECLI has no full date
        ecli_year_only = 'ECLI:BE:CASS:2023:ARR.123'
        year_result = extract_date_from_ecli(ecli_year_only)
        assert year_result == '2023'
        
        legend = 'Vonnis/arrest van 17 januari 2023'
        legend_result = extract_date_from_legend(legend, 'NL')
        assert legend_result == '2023-01-17'
    
    def test_partial_date_handling(self):
        """Test handling of partial dates (year only)."""
        ecli = 'ECLI:BE:CASS:2023:ARR.123'
        result = extract_date_from_ecli(ecli)
        assert result == '2023'
        assert len(result) == 4  # Year only
    
    def test_date_validation(self):
        """Test that invalid dates are rejected."""
        # February 30th doesn't exist
        legend = 'Jugement/arrêt du 30 février 2023'
        result = extract_date_from_legend(legend, 'FR')
        assert result is None
        
        # Month 13 doesn't exist
        ecli = 'ECLI:BE:CASS:2023:ARR.20231301.1'
        result = extract_date_from_ecli(ecli)
        # Invalid date falls back to year only
        assert result == '2023'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])