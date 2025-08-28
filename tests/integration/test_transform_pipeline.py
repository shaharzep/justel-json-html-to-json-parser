#!/usr/bin/env python3
"""
Integration tests for the complete transformation pipeline.
Tests end-to-end transformation of JSON files.
"""

import pytest
import json
import tempfile
import shutil
import asyncio
from pathlib import Path
import sys
from unittest.mock import patch, Mock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.transformer import TwoPhaseTransformerWithDedup, EnhancedJuportalTransformer
from juportal_utils.transform_juportal import JuportalTransformer


class TestCompleteTransformation:
    """Test complete transformation pipeline."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary input and output directories."""
        temp_base = tempfile.mkdtemp()
        temp_input = Path(temp_base) / 'input'
        temp_output = Path(temp_base) / 'output'
        temp_input.mkdir()
        temp_output.mkdir()
        
        yield temp_input, temp_output
        
        # Cleanup
        shutil.rmtree(temp_base)
    
    @pytest.fixture
    def sample_raw_json(self):
        """Create a sample raw JSON document."""
        return {
            "file": "test.txt",
            "lang": "NL",
            "title": "ECLI:BE:CASS:2023:ARR.20230117.2N.7",
            "sections": [
                {
                    "legend": "Vonnis/arrest van 17 januari 2023",
                    "paragraphs": [
                        {"text": "ECLI nr:", "html": "<p>ECLI nr:</p>"},
                        {"text": "ECLI:BE:CASS:2023:ARR.20230117.2N.7", "html": "<p>ECLI:BE:CASS:2023:ARR.20230117.2N.7</p>"},
                        {"text": "Rolnummer:", "html": "<p>Rolnummer:</p>"},
                        {"text": "P.22.1741.N", "html": "<p>P.22.1741.N</p>"},
                        {"text": "Kamer:", "html": "<p>Kamer:</p>"},
                        {"text": "2N - tweede kamer", "html": "<p>2N - tweede kamer</p>"},
                        {"text": "Rechtsgebied:", "html": "<p>Rechtsgebied:</p>"},
                        {"text": "Strafrecht", "html": "<p>Strafrecht</p>"}
                    ]
                },
                {
                    "legend": "Fiche",
                    "paragraphs": [
                        {"text": "Samenvatting van de zaak", "html": "<p>Samenvatting van de zaak</p>"},
                        {"text": "Thesaurus CAS:", "html": "<p>Thesaurus CAS:</p>"},
                        {"text": "STRAFUITVOERING", "html": "<p>STRAFUITVOERING</p>"}
                    ]
                },
                {
                    "legend": "Tekst van de beslissing",
                    "paragraphs": [
                        {"text": "Dit is de volledige tekst van de beslissing.", "html": "<p>Dit is de volledige tekst van de beslissing.</p>"}
                    ]
                }
            ]
        }
    
    def test_single_file_transformation(self, temp_dirs, sample_raw_json):
        """Test transformation of a single file."""
        temp_input, temp_output = temp_dirs
        
        # Create input file
        input_file = temp_input / "juportal.be_BE_CASS_2023_ARR.20230117.2N.7_NL.json"
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(sample_raw_json, f)
        
        # Run transformation
        transformer = JuportalTransformer(str(temp_input), str(temp_output))
        output = transformer.transform_file(input_file)
        
        # Verify output
        assert output is not None
        assert output['decision_id'] == 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        assert output['rol_number'] == 'P.22.1741.N'
        assert output['chamber'] == '2N - tweede kamer'
        assert output['field_of_law'] == 'Strafrecht'
        assert output['language_metadata'] == 'NL'
        assert len(output['summaries']) > 0
        assert output['full_text'] != ""
    
    def test_enhanced_transformer_html_extraction(self, temp_dirs, sample_raw_json):
        """Test enhanced transformer with HTML extraction."""
        temp_input, temp_output = temp_dirs
        
        # Create input file
        input_file = temp_input / "test_NL.json"
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(sample_raw_json, f)
        
        # Run enhanced transformation
        transformer = EnhancedJuportalTransformer(str(temp_input), str(temp_output))
        output = transformer.transform_file(input_file)
        
        # Verify HTML extraction
        assert output is not None
        assert 'full_html' in output
        assert '<p>' in output.get('full_html', '')
    
    @pytest.mark.asyncio
    async def test_two_phase_transformation(self, temp_dirs, sample_raw_json):
        """Test complete two-phase transformation."""
        temp_input, temp_output = temp_dirs
        
        # Create multiple input files
        for i in range(3):
            filename = f"juportal.be_BE_CASS_2023_ARR.{i}_NL.json"
            input_file = temp_input / filename
            doc = sample_raw_json.copy()
            doc['title'] = f"ECLI:BE:CASS:2023:ARR.{i}"
            with open(input_file, 'w', encoding='utf-8') as f:
                json.dump(doc, f)
        
        # Run two-phase transformation
        transformer = TwoPhaseTransformerWithDedup(str(temp_input), str(temp_output))
        
        # Mock LLM to avoid API calls
        with patch('juportal_utils.language_validator.llm_validator', None):
            await transformer.run()
        
        # Verify output files were created
        output_files = list(temp_output.glob("*.json"))
        assert len(output_files) > 0
        
        # Verify statistics
        assert transformer.stats['total_files'] == 3
        assert transformer.stats['successful'] > 0
    
    def test_conc_file_skipping(self, temp_dirs):
        """Test that CONC files are skipped."""
        temp_input, temp_output = temp_dirs
        
        # Create CONC file
        conc_json = {
            "title": "ECLI:BE:CASS:2023:CONC.20230117.1",
            "sections": []
        }
        
        input_file = temp_input / "juportal.be_BE_CASS_2023_CONC.20230117.1_FR.json"
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(conc_json, f)
        
        # Run transformation
        transformer = JuportalTransformer(str(temp_input), str(temp_output))
        transformer.process_all()
        
        # Verify CONC file was skipped
        output_file = temp_output / "juportal.be_BE_CASS_2023_CONC.20230117.1_FR.json"
        assert not output_file.exists()
        assert transformer.stats['skipped_conc'] == 1
    
    def test_language_mismatch_detection(self, temp_dirs):
        """Test detection of language mismatch (German content in FR/NL file)."""
        temp_input, temp_output = temp_dirs
        
        # Create file with German content but NL metadata
        german_json = {
            "title": "ECLI:BE:CASS:2023:ARR.123",
            "sections": [{
                "legend": "Urteil vom 17 Januar 2023",
                "paragraphs": [
                    {"text": "Aktenzeichen:", "html": "<p>Aktenzeichen:</p>"},
                    {"text": "123", "html": "<p>123</p>"},
                    {"text": "Sache:", "html": "<p>Sache:</p>"},
                    {"text": "Test", "html": "<p>Test</p>"},
                    {"text": "Rechtsgebiet:", "html": "<p>Rechtsgebiet:</p>"},
                    {"text": "Strafrecht", "html": "<p>Strafrecht</p>"}
                ],
                "body_text": "Aktenzeichen: 123 Sache: Test Rechtsgebiet: Strafrecht"
            }]
        }
        
        input_file = temp_input / "test_NL.json"
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(german_json, f)
        
        # Run transformation
        transformer = JuportalTransformer(str(temp_input), str(temp_output))
        output = transformer.transform_file(input_file)
        
        # Should be marked as invalid due to language mismatch
        assert output is not None
        assert output['isValid'] is False
        assert transformer.stats['language_mismatch_invalid'] == 1


class TestSchemaValidation:
    """Test schema validation of transformed documents."""
    
    @pytest.fixture
    def transformer(self):
        """Create a transformer instance."""
        return JuportalTransformer()
    
    def test_valid_document_schema(self, transformer):
        """Test that valid documents pass schema validation."""
        doc = transformer.validator.create_empty_document()
        doc['file_name'] = 'test.json'
        doc['decision_id'] = 'ECLI:BE:CASS:2023:ARR.123'
        doc['url_official_publication'] = 'https://juportal.be/...'
        doc['source'] = 'juportal.be'
        doc['language_metadata'] = 'FR'
        
        is_valid, errors = transformer.validator.validate(doc)
        assert is_valid
        assert len(errors) == 0
    
    def test_missing_required_fields(self, transformer):
        """Test that missing required fields are detected."""
        doc = transformer.validator.create_empty_document()
        # Don't set required fields
        
        is_valid, errors = transformer.validator.validate(doc)
        assert not is_valid
        assert len(errors) > 0
        assert any('file_name' in error for error in errors)
    
    def test_wrong_field_types(self, transformer):
        """Test that wrong field types are detected."""
        doc = transformer.validator.create_empty_document()
        doc['file_name'] = 'test.json'
        doc['decision_id'] = 'ECLI:BE:CASS:2023:ARR.123'
        doc['url_official_publication'] = 'https://juportal.be/...'
        doc['source'] = 'juportal.be'
        doc['language_metadata'] = 'FR'
        
        # Set wrong type for a field
        doc['summaries'] = "should be a list"  # Should be list
        
        is_valid, errors = transformer.validator.validate(doc)
        assert not is_valid
        assert any('summaries' in error and 'list' in error for error in errors)


class TestErrorHandling:
    """Test error handling in transformation pipeline."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        temp_base = tempfile.mkdtemp()
        temp_input = Path(temp_base) / 'input'
        temp_output = Path(temp_base) / 'output'
        temp_input.mkdir()
        temp_output.mkdir()
        
        yield temp_input, temp_output
        
        # Cleanup
        shutil.rmtree(temp_base)
    
    def test_malformed_json_handling(self, temp_dirs):
        """Test handling of malformed JSON files."""
        temp_input, temp_output = temp_dirs
        
        # Create malformed JSON file
        bad_file = temp_input / "bad.json"
        with open(bad_file, 'w') as f:
            f.write("{ invalid json")
        
        # Create good file
        good_json = {"title": "ECLI:BE:CASS:2023:ARR.123", "sections": []}
        good_file = temp_input / "good.json"
        with open(good_file, 'w') as f:
            json.dump(good_json, f)
        
        # Run transformation
        transformer = JuportalTransformer(str(temp_input), str(temp_output))
        transformer.process_all()
        
        # Should handle error and continue with good file
        assert transformer.stats['failed'] == 1
        assert transformer.stats['successful'] >= 0
    
    def test_missing_sections_handling(self, temp_dirs):
        """Test handling of documents with missing sections."""
        temp_input, temp_output = temp_dirs
        
        # Create file with no sections
        no_sections = {"title": "ECLI:BE:CASS:2023:ARR.123"}
        input_file = temp_input / "no_sections.json"
        with open(input_file, 'w') as f:
            json.dump(no_sections, f)
        
        # Run transformation
        transformer = JuportalTransformer(str(temp_input), str(temp_output))
        output = transformer.transform_file(input_file)
        
        # Should handle missing sections gracefully
        assert output is not None
        assert output['decision_id'] == 'ECLI:BE:CASS:2023:ARR.123'
    
    def test_empty_paragraphs_handling(self, temp_dirs):
        """Test handling of empty paragraphs."""
        temp_input, temp_output = temp_dirs
        
        # Create file with empty paragraphs
        empty_paras = {
            "title": "ECLI:BE:CASS:2023:ARR.123",
            "sections": [{
                "legend": "Test",
                "paragraphs": []
            }]
        }
        input_file = temp_input / "empty_paras.json"
        with open(input_file, 'w') as f:
            json.dump(empty_paras, f)
        
        # Run transformation
        transformer = JuportalTransformer(str(temp_input), str(temp_output))
        output = transformer.transform_file(input_file)
        
        # Should handle empty paragraphs gracefully
        assert output is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])