"""Unit tests for field extraction functions"""

import unittest
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from juportal_utils.utils import (
    extract_language_from_filename,
    extract_ecli_from_filename,
    extract_date_from_ecli,
    extract_date_from_legend,
    extract_court_code_from_ecli,
    extract_decision_type_from_ecli,
    build_url_from_ecli,
    format_ecli_alias,
    parse_versions,
    extract_pdf_url
)


class TestFieldExtraction(unittest.TestCase):
    """Test field extraction functions"""
    
    def test_extract_language_from_filename(self):
        """Test language extraction from filename"""
        # French
        self.assertEqual(
            extract_language_from_filename("juportal.be_BE_CASS_2007_ARR.20070622.5_FR.json"),
            "FR"
        )
        # Dutch
        self.assertEqual(
            extract_language_from_filename("juportal.be_BE_CASS_2007_ARR.20070622.5_NL.json"),
            "NL"
        )
        # German
        self.assertEqual(
            extract_language_from_filename("juportal.be_BE_GHCC_2022_ARR.103_DE.json"),
            "DE"
        )
        # Default to French if not found
        self.assertEqual(
            extract_language_from_filename("invalid_filename.json"),
            "FR"
        )
    
    def test_extract_ecli_from_filename(self):
        """Test ECLI extraction from filename"""
        # Standard format
        self.assertEqual(
            extract_ecli_from_filename("juportal.be_BE_CASS_2007_ARR.20070622.5_FR.json"),
            "ECLI:BE:CASS:2007:ARR.20070622.5"
        )
        # With underscore in number
        self.assertEqual(
            extract_ecli_from_filename("juportal.be_BE_CASS_2024_ARR.20241105.2N.13_NL.json"),
            "ECLI:BE:CASS:2024:ARR.20241105.2N.13"
        )
        # Invalid filename
        self.assertIsNone(extract_ecli_from_filename("invalid.json"))
    
    def test_extract_date_from_ecli(self):
        """Test date extraction from ECLI"""
        # Standard 8-digit date
        self.assertEqual(
            extract_date_from_ecli("ECLI:BE:CASS:2007:ARR.20070622.5"),
            "2007-06-22"
        )
        # Another date format
        self.assertEqual(
            extract_date_from_ecli("ECLI:BE:CASS:2024:ARR.20241105.2N.13"),
            "2024-11-05"
        )
        # Only year available (3-digit format)
        self.assertEqual(
            extract_date_from_ecli("ECLI:BE:GHCC:2005:ARR.177"),
            "2005"
        )
        # Invalid ECLI
        self.assertIsNone(extract_date_from_ecli("INVALID"))
    
    def test_extract_date_from_legend(self):
        """Test date extraction from legend text"""
        # French
        self.assertEqual(
            extract_date_from_legend("Jugement/arrêt du 22 juin 2007", "FR"),
            "2007-06-22"
        )
        # Dutch
        self.assertEqual(
            extract_date_from_legend("Vonnis/arrest van 22 juni 2007", "NL"),
            "2007-06-22"
        )
        # German
        self.assertEqual(
            extract_date_from_legend("Urteil vom 14 Juli 2022", "DE"),
            "2022-07-14"
        )
        # Invalid format
        self.assertIsNone(extract_date_from_legend("No date here", "FR"))
    
    def test_extract_court_code_from_ecli(self):
        """Test court code extraction from ECLI"""
        self.assertEqual(
            extract_court_code_from_ecli("ECLI:BE:CASS:2007:ARR.20070622.5"),
            "CASS"
        )
        self.assertEqual(
            extract_court_code_from_ecli("ECLI:BE:GHCC:2005:ARR.177"),
            "GHCC"
        )
        self.assertEqual(
            extract_court_code_from_ecli("ECLI:BE:CABRL:2000:ARR.20000125.2"),
            "CABRL"
        )
        self.assertIsNone(extract_court_code_from_ecli("INVALID"))
    
    def test_extract_decision_type_from_ecli(self):
        """Test decision type extraction from ECLI"""
        self.assertEqual(
            extract_decision_type_from_ecli("ECLI:BE:CASS:2007:ARR.20070622.5"),
            "ARR"
        )
        self.assertEqual(
            extract_decision_type_from_ecli("ECLI:BE:AHANT:1970:DEC.19700918.2"),
            "DEC"
        )
        self.assertEqual(
            extract_decision_type_from_ecli("ECLI:BE:GBAPD:2022:AVIS.20220309.11"),
            "AVIS"
        )
        self.assertEqual(
            extract_decision_type_from_ecli("ECLI:BE:CASS:2010:CONC.20100226.8"),
            "CONC"
        )
        self.assertIsNone(extract_decision_type_from_ecli("INVALID"))
    
    def test_build_url_from_ecli(self):
        """Test URL building from ECLI"""
        self.assertEqual(
            build_url_from_ecli("ECLI:BE:CASS:2007:ARR.20070622.5", "FR"),
            "https://juportal.be/content/ECLI:BE:CASS:2007:ARR.20070622.5/FR"
        )
        self.assertEqual(
            build_url_from_ecli("ECLI:BE:GHCC:2005:ARR.177", "NL"),
            "https://juportal.be/content/ECLI:BE:GHCC:2005:ARR.177/NL"
        )
    
    def test_format_ecli_alias(self):
        """Test ECLI alias formatting"""
        # Single alias
        result = format_ecli_alias("ECLI:BE:CASS:2007:ARR.001")
        self.assertEqual(result, ["ECLI:BE:CASS:2007:ARR.001"])
        
        # Multiple aliases separated by semicolon
        result = format_ecli_alias("ECLI:BE:CASS:2007:ARR.001; ECLI:BE:CASS:2007:ARR.002")
        self.assertEqual(result, ["ECLI:BE:CASS:2007:ARR.001", "ECLI:BE:CASS:2007:ARR.002"])
        
        # Empty string
        result = format_ecli_alias("")
        self.assertEqual(result, [])
        
        # Non-ECLI text - format_ecli_alias includes non-ECLI text too
        result = format_ecli_alias("Not an ECLI")
        # Based on implementation, it returns the text if not empty, even if not ECLI
        self.assertEqual(result, ["Not an ECLI"])
    
    def test_extract_pdf_url(self):
        """Test PDF URL extraction"""
        section = {
            "paragraphs": [
                {
                    "text": "Some text",
                    "links": [
                        {
                            "href": "/JUPORTAwork/ECLI:BE:CASS:2007:ARR.20070622.5_FR.pdf",
                            "text": "Document PDF"
                        }
                    ]
                }
            ]
        }
        
        result = extract_pdf_url(section)
        self.assertEqual(
            result, 
            "https://juportal.be/JUPORTAwork/ECLI:BE:CASS:2007:ARR.20070622.5_FR.pdf"
        )
        
        # No PDF link
        section_no_pdf = {"paragraphs": [{"text": "No links"}]}
        self.assertIsNone(extract_pdf_url(section_no_pdf))
    
    def test_parse_versions(self):
        """Test version parsing"""
        paragraphs = [
            {"text": "Version(s):", "html": "<p>Version(s):</p>"},
            {
                "text": "Original NL",
                "html": "<p><a href='/link'>Original NL</a></p>",
                "links": [{"text": "Original NL", "href": "/link"}]
            },
            {
                "text": "Traduction FR",
                "html": "<p>Traduction FR</p>"
            }
        ]
        
        result = parse_versions(paragraphs, 0)
        self.assertIn("Original NL", result)
        self.assertIn("Traduction FR", result)
        
        # No versions
        result = parse_versions([{"text": "No versions"}], 0)
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()