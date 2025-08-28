#!/usr/bin/env python3
"""
Unit tests for text processing functions.
Tests text cleaning, HTML extraction, and PDF URL extraction.
"""

import pytest
from pathlib import Path
import sys
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from juportal_utils.utils import (
    clean_text,
    extract_paragraphs_text,
    extract_paragraphs_html,
    extract_pdf_url,
    remove_pdf_suffix
)
from src.transformer import EnhancedJuportalTransformer


class TestTextCleaning:
    """Test text cleaning functions."""
    
    def test_clean_text_basic(self):
        """Test basic text cleaning."""
        text = "  This   has   extra   spaces  "
        result = clean_text(text)
        assert result == "This has extra spaces"
    
    def test_clean_text_newlines(self):
        """Test cleaning of newlines."""
        text = "Line 1\n\nLine 2\n\n\nLine 3"
        result = clean_text(text)
        assert result == "Line 1 Line 2 Line 3"
    
    def test_clean_text_tabs(self):
        """Test cleaning of tabs."""
        text = "Text\twith\ttabs"
        result = clean_text(text)
        assert result == "Text with tabs"
    
    def test_clean_text_mixed_whitespace(self):
        """Test cleaning of mixed whitespace."""
        text = "  Text\n\twith  \r\n  mixed   whitespace  "
        result = clean_text(text)
        assert result == "Text with mixed whitespace"
    
    def test_clean_text_empty(self):
        """Test cleaning of empty string."""
        result = clean_text("")
        assert result == ""
    
    def test_clean_text_none(self):
        """Test cleaning of None."""
        result = clean_text(None)
        assert result == ""
    
    def test_clean_text_only_whitespace(self):
        """Test cleaning of whitespace-only string."""
        text = "   \n\t\r\n   "
        result = clean_text(text)
        assert result == ""


class TestParagraphExtraction:
    """Test paragraph text and HTML extraction."""
    
    @pytest.fixture
    def sample_paragraphs(self):
        """Create sample paragraphs."""
        return [
            {
                'text': 'First paragraph text',
                'html': '<p>First paragraph text</p>'
            },
            {
                'text': 'Second paragraph text',
                'html': '<p>Second paragraph text</p>'
            },
            {
                'text': '',
                'html': '<p></p>'
            },
            {
                'text': 'Third paragraph text',
                'html': '<p>Third paragraph text</p>'
            }
        ]
    
    def test_extract_paragraphs_text(self, sample_paragraphs):
        """Test extraction of paragraph texts."""
        result = extract_paragraphs_text(sample_paragraphs)
        expected = 'First paragraph text Second paragraph text Third paragraph text'
        assert result == expected
    
    def test_extract_paragraphs_text_empty_list(self):
        """Test extraction from empty paragraph list."""
        result = extract_paragraphs_text([])
        assert result == ''
    
    def test_extract_paragraphs_text_none(self):
        """Test extraction from None."""
        result = extract_paragraphs_text(None)
        assert result == ''
    
    def test_extract_paragraphs_text_with_empty(self, sample_paragraphs):
        """Test that empty paragraphs are skipped."""
        result = extract_paragraphs_text(sample_paragraphs)
        assert 'Third paragraph' in result
        # Empty paragraph should not create double spaces
        assert '  ' not in result
    
    def test_extract_paragraphs_html(self, sample_paragraphs):
        """Test extraction of paragraph HTML."""
        result = extract_paragraphs_html(sample_paragraphs)
        assert '<p>First paragraph text</p>' in result
        assert '<p>Second paragraph text</p>' in result
        assert '<p>Third paragraph text</p>' in result
    
    def test_extract_paragraphs_html_empty_list(self):
        """Test HTML extraction from empty list."""
        result = extract_paragraphs_html([])
        assert result == ''
    
    def test_extract_paragraphs_html_none(self):
        """Test HTML extraction from None."""
        result = extract_paragraphs_html(None)
        assert result == ''
    
    def test_extract_paragraphs_html_missing_html(self):
        """Test HTML extraction when html field is missing."""
        paragraphs = [
            {'text': 'Text without HTML'},
            {'text': 'Another text', 'html': '<p>Another text</p>'}
        ]
        result = extract_paragraphs_html(paragraphs)
        assert result == '<p>Another text</p>'


class TestPDFExtraction:
    """Test PDF URL extraction."""
    
    def test_extract_pdf_url_from_link(self):
        """Test PDF URL extraction from link."""
        section = {
            'paragraphs': [
                {
                    'text': 'Some text',
                    'html': '<p>Some text</p>'
                },
                {
                    'text': 'PDF document',
                    'html': '<p><a href="/path/to/document.pdf">PDF document</a></p>',
                    'links': [
                        {'href': '/path/to/document.pdf', 'text': 'PDF document'}
                    ]
                }
            ]
        }
        result = extract_pdf_url(section)
        assert result == '/path/to/document.pdf'
    
    def test_extract_pdf_url_no_pdf(self):
        """Test PDF URL extraction when no PDF present."""
        section = {
            'paragraphs': [
                {'text': 'Some text', 'html': '<p>Some text</p>'}
            ]
        }
        result = extract_pdf_url(section)
        assert result is None
    
    def test_extract_pdf_url_multiple_links(self):
        """Test PDF URL extraction with multiple links."""
        section = {
            'paragraphs': [
                {
                    'text': 'Link 1',
                    'links': [{'href': '/other.html', 'text': 'Other'}]
                },
                {
                    'text': 'PDF link',
                    'links': [{'href': '/document.pdf', 'text': 'PDF'}]
                }
            ]
        }
        result = extract_pdf_url(section)
        assert result == '/document.pdf'
    
    def test_extract_pdf_url_juporta_work_pattern(self):
        """Test PDF URL extraction with JUPORTAwork pattern."""
        section = {
            'paragraphs': [
                {
                    'text': 'PDF document ECLI:BE:CASS:2023:ARR.20230117.2N.7',
                    'links': [
                        {
                            'href': '/JUPORTAwork/ECLI:BE:CASS:2023:ARR.20230117.2N.7_NL.pdf?Version=1674486295',
                            'text': 'PDF document'
                        }
                    ]
                }
            ]
        }
        result = extract_pdf_url(section)
        assert '/JUPORTAwork/' in result
        assert '.pdf' in result


class TestPDFSuffixRemoval:
    """Test PDF suffix removal from text."""
    
    def test_remove_pdf_suffix_basic(self):
        """Test basic PDF suffix removal."""
        text = "This is the decision text. PDF document"
        result = remove_pdf_suffix(text)
        assert result == "This is the decision text."
    
    def test_remove_pdf_suffix_with_ecli(self):
        """Test PDF suffix removal with ECLI."""
        text = "Decision content here. PDF document ECLI:BE:CASS:2023:ARR.20230117"
        result = remove_pdf_suffix(text)
        assert result == "Decision content here."
    
    def test_remove_pdf_suffix_multiple_paragraphs(self):
        """Test PDF suffix removal with multiple paragraphs."""
        text = "First paragraph. Second paragraph. Document PDF"
        result = remove_pdf_suffix(text)
        assert result == "First paragraph. Second paragraph."
    
    def test_remove_pdf_suffix_no_suffix(self):
        """Test when there's no PDF suffix."""
        text = "Normal text without PDF reference."
        result = remove_pdf_suffix(text)
        assert result == text
    
    def test_remove_pdf_suffix_empty(self):
        """Test with empty string."""
        result = remove_pdf_suffix("")
        assert result == ""
    
    def test_remove_pdf_suffix_none(self):
        """Test with None."""
        result = remove_pdf_suffix(None)
        assert result == ""


class TestFullTextProcessing:
    """Test full text processing in transformer."""
    
    @pytest.fixture
    def transformer(self):
        """Create an enhanced transformer instance."""
        return EnhancedJuportalTransformer()
    
    def test_process_full_text_basic(self, transformer):
        """Test basic full text processing."""
        section = {
            'paragraphs': [
                {'text': 'First paragraph of decision.', 'html': '<p>First paragraph of decision.</p>'},
                {'text': 'Second paragraph of decision.', 'html': '<p>Second paragraph of decision.</p>'},
            ]
        }
        output = {}
        transformer._process_full_text(section, output)
        
        assert 'full_text' in output
        assert 'First paragraph' in output['full_text']
        assert 'Second paragraph' in output['full_text']
        assert 'full_html' in output
    
    def test_process_full_text_skip_pdf_link(self, transformer):
        """Test that PDF links are skipped in full text."""
        section = {
            'paragraphs': [
                {'text': 'Decision text.', 'html': '<p>Decision text.</p>'},
                {'text': 'Document PDF', 'html': '<p>Document PDF</p>'},
                {'text': 'More text.', 'html': '<p>More text.</p>'},
            ]
        }
        output = {}
        transformer._process_full_text(section, output)
        
        assert 'Document PDF' not in output['full_text']
        assert 'Decision text' in output['full_text']
        assert 'More text' in output['full_text']
    
    def test_process_full_text_skip_metadata_labels(self, transformer):
        """Test that metadata labels are skipped."""
        section = {
            'paragraphs': [
                {'text': 'texte intégral:', 'html': '<p>texte intégral:</p>'},
                {'text': 'Actual decision text.', 'html': '<p>Actual decision text.</p>'},
            ]
        }
        output = {}
        transformer._process_full_text(section, output)
        
        assert 'texte intégral:' not in output['full_text']
        assert 'Actual decision text' in output['full_text']
    
    def test_process_full_text_empty_placeholder(self, transformer):
        """Test handling of empty placeholder '<>'."""
        section = {
            'paragraphs': [
                {'text': '<>', 'html': '<p>&lt;&gt;</p>'},
            ]
        }
        output = {}
        transformer._process_full_text(section, output)
        
        assert output['full_text'] == ""
        assert output['full_html'] == ""
    
    def test_process_full_text_with_pdf_url(self, transformer):
        """Test extraction of PDF URL along with text."""
        section = {
            'paragraphs': [
                {'text': 'Decision text.', 'html': '<p>Decision text.</p>'},
                {
                    'text': 'PDF document',
                    'html': '<p><a href="/doc.pdf">PDF document</a></p>',
                    'links': [{'href': '/doc.pdf', 'text': 'PDF document'}]
                }
            ]
        }
        output = {}
        transformer._process_full_text(section, output)
        
        assert 'url_pdf' in output
        assert output['url_pdf'] == '/doc.pdf'
    
    def test_process_full_text_empty_paragraphs(self, transformer):
        """Test handling of empty paragraphs."""
        section = {
            'paragraphs': [
                {'text': 'Text 1', 'html': '<p>Text 1</p>'},
                {'text': '', 'html': '<p></p>'},
                {'text': '   ', 'html': '<p>   </p>'},
                {'text': 'Text 2', 'html': '<p>Text 2</p>'},
            ]
        }
        output = {}
        transformer._process_full_text(section, output)
        
        assert 'Text 1' in output['full_text']
        assert 'Text 2' in output['full_text']
        # Should not have excessive spaces from empty paragraphs
        assert '  ' not in output['full_text']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])