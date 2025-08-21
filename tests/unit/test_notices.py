"""Unit tests for notices field extraction"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from juportal_utils.utils import merge_keyword_values
from juportal_utils.transform_juportal import JuportalTransformer


class TestNoticesExtraction(unittest.TestCase):
    """Test notices field extraction"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.transformer = JuportalTransformer()
    
    def test_merge_keyword_values_cassation(self):
        """Test merging Cassation keywords"""
        paragraphs = [
            {"text": "Thésaurus Cassation:", "html": "<p>Thésaurus Cassation:</p>"},
            {
                "text": "KEYWORD1 KEYWORD2 KEYWORD3",
                "html": "<p>KEYWORD1<br/>KEYWORD2<br/>KEYWORD3</p>"
            },
            {"text": "KEYWORD4", "html": "<p>KEYWORD4</p>"},
            {"text": "Thésaurus UTU:", "html": "<p>Thésaurus UTU:</p>"}  # Should stop here
        ]
        
        result = merge_keyword_values(paragraphs, 0, keyword_type='cassation')
        self.assertEqual(len(result), 3)
        self.assertIn("KEYWORD1", result)
        self.assertIn("KEYWORD2", result)
        self.assertIn("KEYWORD3", result)
    
    def test_merge_keyword_values_utu(self):
        """Test merging UTU keywords"""
        paragraphs = [
            {"text": "Thésaurus UTU:", "html": "<p>Thésaurus UTU:</p>"},
            {
                "text": "DROIT JUDICIAIRE - PRINCIPES GÉNÉRAUX",
                "html": "<p>DROIT JUDICIAIRE - PRINCIPES GÉNÉRAUX</p>"
            },
            {
                "text": "DROIT CIVIL - CONTRATS",
                "html": "<p>DROIT CIVIL - CONTRATS</p>"
            },
            {"text": "Mots libres:", "html": "<p>Mots libres:</p>"}  # Should stop here
        ]
        
        result = merge_keyword_values(paragraphs, 0, keyword_type='utu')
        self.assertEqual(len(result), 2)
        self.assertIn("DROIT JUDICIAIRE - PRINCIPES GÉNÉRAUX", result)
        self.assertIn("DROIT CIVIL - CONTRATS", result)
    
    def test_merge_keyword_values_free(self):
        """Test merging free keywords"""
        paragraphs = [
            {"text": "Mots libres:", "html": "<p>Mots libres:</p>"},
            {"text": "keyword1; keyword2, keyword3", "html": "<p>keyword1; keyword2, keyword3</p>"},
            {"text": "keyword4", "html": "<p>keyword4</p>"},
            {"text": "Bases légales:", "html": "<p>Bases légales:</p>"}  # Should stop here
        ]
        
        result = merge_keyword_values(paragraphs, 0, keyword_type='free')
        self.assertEqual(len(result), 4)
        self.assertIn("keyword1", result)
        self.assertIn("keyword2", result)
        self.assertIn("keyword3", result)
        self.assertIn("keyword4", result)
    
    def test_process_fiche_card_summary(self):
        """Test extracting summary from Fiche card"""
        section = {
            "legend": "Fiche 1",
            "paragraphs": [
                {"text": "This is the summary text.", "html": "<p>This is the summary text.</p>"},
                {"text": "Thésaurus Cassation:", "html": "<p>Thésaurus Cassation:</p>"},
                {"text": "KEYWORD", "html": "<p>KEYWORD</p>"}
            ]
        }
        
        output = {"notices": []}
        self.transformer._process_fiche_card(section, output, "Fiche 1")
        
        self.assertEqual(len(output["notices"]), 1)
        self.assertEqual(output["notices"][0]["summary"], "This is the summary text.")
        self.assertEqual(output["notices"][0]["noticeId"], "1")
    
    def test_process_fiche_card_keywords_deduplication(self):
        """Test keyword deduplication in Fiche cards"""
        section = {
            "legend": "Fiches 1 - 3",
            "paragraphs": [
                {"text": "Summary", "html": "<p>Summary</p>"},
                {"text": "Thésaurus Cassation:", "html": "<p>Thésaurus Cassation:</p>"},
                {"text": "KEYWORD1", "html": "<p>KEYWORD1<br/>KEYWORD2</p>"},
                {"text": "Thésaurus Cassation:", "html": "<p>Thésaurus Cassation:</p>"},
                {"text": "KEYWORD2", "html": "<p>KEYWORD2<br/>KEYWORD3</p>"},  # KEYWORD2 is duplicate
                {"text": "Thésaurus UTU:", "html": "<p>Thésaurus UTU:</p>"},
                {"text": "UTU1", "html": "<p>UTU1</p>"},
                {"text": "Thésaurus UTU:", "html": "<p>Thésaurus UTU:</p>"},
                {"text": "UTU1", "html": "<p>UTU1<br/>UTU2</p>"}  # UTU1 is duplicate
            ]
        }
        
        output = {"notices": []}
        self.transformer._process_fiche_card(section, output, "Fiches 1 - 3")
        
        self.assertEqual(len(output["notices"]), 1)
        notice = output["notices"][0]
        
        # Check Cassation keywords deduplication
        self.assertEqual(len(notice["keywordsCassation"]), 3)
        self.assertEqual(notice["keywordsCassation"], ["KEYWORD1", "KEYWORD2", "KEYWORD3"])
        
        # Check UTU keywords deduplication
        self.assertEqual(len(notice["keywordsUtu"]), 2)
        self.assertEqual(notice["keywordsUtu"], ["UTU1", "UTU2"])
    
    def test_process_fiche_card_legal_basis(self):
        """Test legal basis extraction with HTML parsing"""
        section = {
            "legend": "Fiche 1",
            "paragraphs": [
                {"text": "", "html": ""},
                {"text": "Bases légales:", "html": "<p>Bases légales:</p>"},
                {
                    "text": "Code Judiciaire - Art. 39 Code Civil - Art. 111",
                    "html": "<p>Code Judiciaire - Art. 39<br/>Code Civil - Art. 111<br/>Loi du 10-10-1967</p>"
                }
            ]
        }
        
        output = {"notices": []}
        self.transformer._process_fiche_card(section, output, "Fiche 1")
        
        self.assertEqual(len(output["notices"]), 1)
        legal_basis = output["notices"][0]["legalBasis"]
        self.assertEqual(len(legal_basis), 3)
        self.assertIn("Code Judiciaire - Art. 39", legal_basis)
        self.assertIn("Code Civil - Art. 111", legal_basis)
        self.assertIn("Loi du 10-10-1967", legal_basis)
    
    def test_process_fiche_card_empty_summary(self):
        """Test Fiche card with empty summary"""
        section = {
            "legend": "Fiche 1",
            "paragraphs": [
                {"text": "", "html": ""},  # Empty summary
                {"text": "Thésaurus Cassation:", "html": "<p>Thésaurus Cassation:</p>"},
                {"text": "KEYWORD", "html": "<p>KEYWORD</p>"}
            ]
        }
        
        output = {"notices": []}
        self.transformer._process_fiche_card(section, output, "Fiche 1")
        
        self.assertEqual(len(output["notices"]), 1)
        self.assertEqual(output["notices"][0]["summary"], "")
        self.assertEqual(output["notices"][0]["keywordsCassation"], ["KEYWORD"])
    
    def test_process_multi_fiche_card(self):
        """Test multi-fiche card processing"""
        section = {
            "legend": "Fiches 2 - 5",
            "paragraphs": [
                {"text": "Multi-fiche summary", "html": "<p>Multi-fiche summary</p>"},
                {"text": "Thésaurus Cassation:", "html": "<p>Thésaurus Cassation:</p>"},
                {"text": "KEYWORD1", "html": "<p>KEYWORD1</p>"}
            ]
        }
        
        output = {"notices": []}
        self.transformer._process_fiche_card(section, output, "Fiches 2 - 5")
        
        self.assertEqual(len(output["notices"]), 1)
        # Should use first fiche number as ID
        self.assertEqual(output["notices"][0]["noticeId"], "2")
        self.assertEqual(output["notices"][0]["summary"], "Multi-fiche summary")
    
    def test_keywords_free_as_string(self):
        """Test that free keywords are concatenated as string"""
        section = {
            "legend": "Fiche 1",
            "paragraphs": [
                {"text": "", "html": ""},
                {"text": "Mots libres:", "html": "<p>Mots libres:</p>"},
                {"text": "keyword1, keyword2", "html": "<p>keyword1, keyword2</p>"},
                {"text": "keyword3", "html": "<p>keyword3</p>"},
                {"text": "Bases légales:", "html": "<p>Bases légales:</p>"}
            ]
        }
        
        output = {"notices": []}
        self.transformer._process_fiche_card(section, output, "Fiche 1")
        
        self.assertEqual(len(output["notices"]), 1)
        # Free keywords should be concatenated
        self.assertIsInstance(output["notices"][0]["keywordsFree"], str)
        self.assertIn("keyword1", output["notices"][0]["keywordsFree"])
        self.assertIn("keyword2", output["notices"][0]["keywordsFree"])
        self.assertIn("keyword3", output["notices"][0]["keywordsFree"])


if __name__ == '__main__':
    unittest.main()