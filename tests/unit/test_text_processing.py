"""Unit tests for text processing functions"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from juportal_utils.utils import (
    clean_text,
    remove_pdf_suffix,
    extract_paragraphs_text,
    extract_paragraphs_html,
    extract_field_value_from_paragraphs,
    extract_links_from_paragraph,
    parse_legal_basis
)


class TestTextProcessing(unittest.TestCase):
    """Test text processing functions"""
    
    def test_clean_text(self):
        """Test text cleaning and normalization"""
        # Remove excessive whitespace
        self.assertEqual(
            clean_text("Text  with   multiple    spaces"),
            "Text with multiple spaces"
        )
        
        # Remove leading/trailing whitespace
        self.assertEqual(
            clean_text("  Text with spaces  "),
            "Text with spaces"
        )
        
        # Remove empty lines
        self.assertEqual(
            clean_text("Line1\n\n\nLine2"),
            "Line1\nLine2"
        )
        
        # Handle None
        self.assertEqual(clean_text(None), "")
        
        # Handle empty string
        self.assertEqual(clean_text(""), "")
    
    def test_remove_pdf_suffix(self):
        """Test PDF suffix removal"""
        # French PDF suffix
        text_fr = "This is the decision text. Document PDF ECLI:BE:CASS:2007:ARR.20070622.5"
        self.assertEqual(
            remove_pdf_suffix(text_fr),
            "This is the decision text."
        )
        
        # English PDF suffix variant
        text_en = "This is the decision text. PDF document ECLI:BE:CASS:2007:ARR.20070622.5"
        self.assertEqual(
            remove_pdf_suffix(text_en),
            "This is the decision text."
        )
        
        # No PDF suffix
        text_normal = "This is normal text without PDF suffix."
        self.assertEqual(
            remove_pdf_suffix(text_normal),
            "This is normal text without PDF suffix."
        )
        
        # Handle None
        self.assertEqual(remove_pdf_suffix(None), "")
        
        # Handle empty string
        self.assertEqual(remove_pdf_suffix(""), "")
        
        # PDF suffix with complex ECLI
        text_complex = "Decision text here. Document PDF ECLI:BE:CASS:2024:ARR.20241105.2N.13"
        self.assertEqual(
            remove_pdf_suffix(text_complex),
            "Decision text here."
        )
    
    def test_extract_paragraphs_text(self):
        """Test extracting text from paragraphs array"""
        paragraphs = [
            {"text": "First paragraph"},
            {"text": "Second paragraph"},
            {"text": "  Third paragraph  "},
            {"text": ""},  # Empty should be skipped
            {"html": "<p>HTML only</p>"},  # No text field
            {"text": "Fourth paragraph"}
        ]
        
        result = extract_paragraphs_text(paragraphs)
        expected = "First paragraph\nSecond paragraph\nThird paragraph\nFourth paragraph"
        self.assertEqual(result, expected)
        
        # Empty list
        self.assertEqual(extract_paragraphs_text([]), "")
        
        # Non-dict items
        paragraphs_mixed = [
            {"text": "Valid"},
            "Not a dict",
            {"text": "Also valid"},
            None
        ]
        result = extract_paragraphs_text(paragraphs_mixed)
        self.assertEqual(result, "Valid\nAlso valid")
    
    def test_extract_paragraphs_html(self):
        """Test extracting HTML from paragraphs array"""
        paragraphs = [
            {"html": "<p>First paragraph</p>"},
            {"html": "<p>Second paragraph</p>"},
            {"html": "  <p>Third paragraph</p>  "},
            {"html": ""},  # Empty should be skipped
            {"text": "Text only"},  # No HTML field
            {"html": "<p>Fourth paragraph</p>"}
        ]
        
        result = extract_paragraphs_html(paragraphs)
        expected = "<p>First paragraph</p>\n<p>Second paragraph</p>\n<p>Third paragraph</p>\n<p>Fourth paragraph</p>"
        self.assertEqual(result, expected)
        
        # Empty list
        self.assertEqual(extract_paragraphs_html([]), "")
    
    def test_extract_field_value_from_paragraphs(self):
        """Test extracting field value from paragraphs"""
        # Value in next paragraph
        paragraphs = [
            {"text": "Field Label:"},
            {"text": "Field Value"}
        ]
        result = extract_field_value_from_paragraphs(paragraphs, "Field Label")
        self.assertEqual(result, "Field Value")
        
        # Value in same paragraph after colon
        paragraphs = [
            {"text": "Field Label: Field Value"},
            {"text": "Other text"}
        ]
        result = extract_field_value_from_paragraphs(paragraphs, "Field Label")
        self.assertEqual(result, "Field Value")
        
        # Field not found
        paragraphs = [
            {"text": "Different Label:"},
            {"text": "Some Value"}
        ]
        result = extract_field_value_from_paragraphs(paragraphs, "Field Label")
        self.assertIsNone(result)
        
        # Case insensitive matching
        paragraphs = [
            {"text": "FIELD LABEL:"},
            {"text": "Value"}
        ]
        result = extract_field_value_from_paragraphs(paragraphs, "field label")
        self.assertEqual(result, "Value")
    
    def test_extract_links_from_paragraph(self):
        """Test extracting links from paragraph"""
        paragraph = {
            "text": "Text with links",
            "links": [
                {"href": "/link1", "text": "Link 1"},
                {"href": "/link2", "text": "Link 2"}
            ]
        }
        
        result = extract_links_from_paragraph(paragraph)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["href"], "/link1")
        self.assertEqual(result[0]["text"], "Link 1")
        self.assertEqual(result[1]["href"], "/link2")
        
        # No links field
        paragraph_no_links = {"text": "No links"}
        result = extract_links_from_paragraph(paragraph_no_links)
        self.assertEqual(result, [])
        
        # Invalid links structure
        paragraph_invalid = {
            "links": ["not", "dict", "list"]
        }
        result = extract_links_from_paragraph(paragraph_invalid)
        self.assertEqual(result, [])
    
    def test_parse_legal_basis(self):
        """Test parsing legal basis text"""
        # Single legal basis
        text = "Code Judiciaire - Art. 39"
        result = parse_legal_basis(text)
        self.assertEqual(result, ["Code Judiciaire - Art. 39"])
        
        # Multiple separated by semicolon
        text = "Code Judiciaire - Art. 39; Code Civil - Art. 111"
        result = parse_legal_basis(text)
        self.assertEqual(len(result), 2)
        self.assertIn("Code Judiciaire - Art. 39", result)
        self.assertIn("Code Civil - Art. 111", result)
        
        # Multiple separated by newline
        text = "Law 1\nLaw 2\nLaw 3"
        result = parse_legal_basis(text)
        self.assertEqual(len(result), 3)
        
        # With extra whitespace
        text = "  Law 1  ;  Law 2  "
        result = parse_legal_basis(text)
        self.assertEqual(result, ["Law 1", "Law 2"])
        
        # Empty string
        self.assertEqual(parse_legal_basis(""), [])
        
        # None
        self.assertEqual(parse_legal_basis(None), [])


if __name__ == '__main__':
    unittest.main()