#!/usr/bin/env python3
"""
Unit tests for field extraction from Juportal JSON sections.
Tests extraction of decision card fields, Fiche card fields, and related publications.
"""

import pytest
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from juportal_utils.transform_juportal import JuportalTransformer
from juportal_utils.mapping_config import FieldMapper


class TestDecisionCardExtraction:
    """Test extraction of fields from decision card section."""
    
    @pytest.fixture
    def transformer(self):
        """Create a transformer instance."""
        return JuportalTransformer()
    
    @pytest.fixture
    def sample_decision_card(self):
        """Sample decision card section."""
        return {
            'legend': 'Vonnis/arrest van 17 januari 2023',
            'paragraphs': [
                {'text': 'ECLI nr:', 'html': '<p>ECLI nr:</p>'},
                {'text': 'ECLI:BE:CASS:2023:ARR.20230117.2N.7', 'html': '<p>ECLI:BE:CASS:2023:ARR.20230117.2N.7</p>'},
                {'text': 'Rolnummer:', 'html': '<p>Rolnummer:</p>'},
                {'text': 'P.22.1741.N', 'html': '<p>P.22.1741.N</p>'},
                {'text': 'Zaak:', 'html': '<p>Zaak:</p>'},
                {'text': 'M.', 'html': '<p>M.</p>'},
                {'text': 'Kamer:', 'html': '<p>Kamer:</p>'},
                {'text': '2N - tweede kamer', 'html': '<p>2N - tweede kamer</p>'},
                {'text': 'Rechtsgebied:', 'html': '<p>Rechtsgebied:</p>'},
                {'text': 'Strafrecht', 'html': '<p>Strafrecht</p>'},
            ]
        }
    
    def test_ecli_extraction(self, transformer, sample_decision_card):
        """Test ECLI extraction from decision card."""
        output = transformer.validator.create_empty_document()
        transformer._process_decision_card(sample_decision_card, output, 'NL')
        
        assert output['decision_id'] == 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
    
    def test_rol_number_extraction(self, transformer, sample_decision_card):
        """Test rol number extraction from decision card."""
        output = transformer.validator.create_empty_document()
        transformer._process_decision_card(sample_decision_card, output, 'NL')
        
        assert output['rol_number'] == 'P.22.1741.N'
    
    def test_chamber_extraction(self, transformer, sample_decision_card):
        """Test chamber extraction from decision card."""
        output = transformer.validator.create_empty_document()
        transformer._process_decision_card(sample_decision_card, output, 'NL')
        
        assert output['chamber'] == '2N - tweede kamer'
    
    def test_field_of_law_extraction(self, transformer, sample_decision_card):
        """Test field of law extraction from decision card."""
        output = transformer.validator.create_empty_document()
        transformer._process_decision_card(sample_decision_card, output, 'NL')
        
        assert output['field_of_law'] == 'Strafrecht'
    
    def test_case_extraction(self, transformer, sample_decision_card):
        """Test case extraction from decision card."""
        output = transformer.validator.create_empty_document()
        transformer._process_decision_card(sample_decision_card, output, 'NL')
        
        assert output['case'] == 'M.'


class TestFicheCardExtraction:
    """Test extraction of fields from Fiche cards."""
    
    @pytest.fixture
    def transformer(self):
        """Create a transformer instance."""
        return JuportalTransformer()
    
    @pytest.fixture
    def sample_fiche_card(self):
        """Sample Fiche card section."""
        return {
            'legend': 'Fiche 1',
            'paragraphs': [
                {'text': 'Dit is een samenvatting van de zaak.', 'html': '<p>Dit is een samenvatting van de zaak.</p>'},
                {'text': 'Thesaurus CAS:', 'html': '<p>Thesaurus CAS:</p>'},
                {'text': 'STRAFUITVOERING', 'html': '<p>STRAFUITVOERING</p>'},
                {'text': 'UTU-thesaurus:', 'html': '<p>UTU-thesaurus:</p>'},
                {'text': 'Voorlopige invrijheidstelling', 'html': '<p>Voorlopige invrijheidstelling</p>'},
                {'text': 'Vrije woorden:', 'html': '<p>Vrije woorden:</p>'},
                {'text': 'cassatie strafrecht', 'html': '<p>cassatie strafrecht</p>'},
                {'text': 'Wettelijke bepalingen:', 'html': '<p>Wettelijke bepalingen:</p>'},
                {'text': 'Art. 47 Wet Strafuitvoering', 'html': '<p>Art. 47 Wet Strafuitvoering</p>'},
            ]
        }
    
    def test_summary_extraction(self, transformer, sample_fiche_card):
        """Test summary extraction from Fiche card."""
        output = transformer.validator.create_empty_document()
        transformer._process_fiche_card(sample_fiche_card, output, 'Fiche 1')
        
        assert len(output['summaries']) == 1
        assert output['summaries'][0]['summary'] == 'Dit is een samenvatting van de zaak.'
        assert output['summaries'][0]['summaryId'] == '1'
    
    def test_keywords_cassation_extraction(self, transformer, sample_fiche_card):
        """Test keywords cassation extraction from Fiche card."""
        output = transformer.validator.create_empty_document()
        transformer._process_fiche_card(sample_fiche_card, output, 'Fiche 1')
        
        assert 'STRAFUITVOERING' in output['summaries'][0]['keywordsCassation']
    
    def test_keywords_utu_extraction(self, transformer, sample_fiche_card):
        """Test keywords UTU extraction from Fiche card."""
        output = transformer.validator.create_empty_document()
        transformer._process_fiche_card(sample_fiche_card, output, 'Fiche 1')
        
        assert 'Voorlopige invrijheidstelling' in output['summaries'][0]['keywordsUtu']
    
    def test_keywords_free_extraction(self, transformer, sample_fiche_card):
        """Test free keywords extraction from Fiche card."""
        output = transformer.validator.create_empty_document()
        transformer._process_fiche_card(sample_fiche_card, output, 'Fiche 1')
        
        assert 'cassatie strafrecht' in output['summaries'][0]['keywordsFree']
    
    def test_legal_basis_extraction(self, transformer, sample_fiche_card):
        """Test legal basis extraction from Fiche card."""
        output = transformer.validator.create_empty_document()
        transformer._process_fiche_card(sample_fiche_card, output, 'Fiche 1')
        
        assert 'Art. 47 Wet Strafuitvoering' in output['summaries'][0]['legalBasis']
    
    def test_multi_fiche_consolidation(self, transformer):
        """Test consolidation of multiple Fiche cards."""
        output = transformer.validator.create_empty_document()
        
        # Process multiple Fiche cards with range
        fiche_card = {
            'legend': 'Fiches 2 - 4',
            'paragraphs': [
                {'text': 'Summary text', 'html': '<p>Summary text</p>'},
                {'text': 'Thesaurus CAS:', 'html': '<p>Thesaurus CAS:</p>'},
                {'text': 'KEYWORD1', 'html': '<p>KEYWORD1</p>'},
            ]
        }
        
        transformer._process_fiche_card(fiche_card, output, 'Fiches 2 - 4')
        
        assert len(output['summaries']) == 1
        assert output['summaries'][0]['summaryId'] == '2'  # Uses first number in range


class TestRelatedPublicationsExtraction:
    """Test extraction of related publications."""
    
    @pytest.fixture
    def transformer(self):
        """Create a transformer instance."""
        return JuportalTransformer()
    
    @pytest.fixture
    def sample_related_section(self):
        """Sample related publications section."""
        return {
            'legend': 'Gerelateerde publicaties',
            'paragraphs': [
                {'text': 'Citeert:', 'html': '<p>Citeert:</p>'},
                {'text': 'ECLI:BE:CASS:2020:ARR.20200101.1', 'html': '<p>ECLI:BE:CASS:2020:ARR.20200101.1</p>'},
                {'text': 'ECLI:BE:CASS:2019:ARR.20190101.1', 'html': '<p>ECLI:BE:CASS:2019:ARR.20190101.1</p>'},
                {'text': 'Precedenten:', 'html': '<p>Precedenten:</p>'},
                {'text': 'ECLI:BE:CASS:2018:ARR.20180101.1', 'html': '<p>ECLI:BE:CASS:2018:ARR.20180101.1</p>'},
                {'text': 'Geciteerd door:', 'html': '<p>Geciteerd door:</p>'},
                {'text': 'ECLI:BE:CASS:2024:ARR.20240101.1', 'html': '<p>ECLI:BE:CASS:2024:ARR.20240101.1</p>'},
            ]
        }
    
    def test_citing_extraction(self, transformer, sample_related_section):
        """Test extraction of citing references."""
        output = transformer.validator.create_empty_document()
        transformer._process_related_publications(sample_related_section, output)
        
        assert len(output['citing']) == 2
        assert 'ECLI:BE:CASS:2020:ARR.20200101.1' in output['citing']
        assert 'ECLI:BE:CASS:2019:ARR.20190101.1' in output['citing']
    
    def test_precedent_extraction(self, transformer, sample_related_section):
        """Test extraction of precedent references."""
        output = transformer.validator.create_empty_document()
        transformer._process_related_publications(sample_related_section, output)
        
        assert len(output['precedent']) == 1
        assert 'ECLI:BE:CASS:2018:ARR.20180101.1' in output['precedent']
    
    def test_cited_in_extraction(self, transformer, sample_related_section):
        """Test extraction of cited_in references."""
        output = transformer.validator.create_empty_document()
        transformer._process_related_publications(sample_related_section, output)
        
        assert len(output['cited_in']) == 1
        assert 'ECLI:BE:CASS:2024:ARR.20240101.1' in output['cited_in']
    
    def test_opinion_public_attorney_extraction(self, transformer):
        """Test extraction of opinion public attorney."""
        section = {
            'legend': 'Gerelateerde publicaties',
            'paragraphs': [
                {'text': 'Conclusie O.M.:', 'html': '<p>Conclusie O.M.:</p>'},
                {'text': 'Het openbaar ministerie concludeert...', 'html': '<p>Het openbaar ministerie concludeert...</p>'},
            ]
        }
        
        output = transformer.validator.create_empty_document()
        transformer._process_related_publications(section, output)
        
        assert output['opinion_public_attorney'] == 'Het openbaar ministerie concludeert...'


class TestFieldMapping:
    """Test field mapping configuration."""
    
    @pytest.fixture
    def mapper(self):
        """Create a field mapper instance."""
        return FieldMapper()
    
    def test_decision_card_detection(self, mapper):
        """Test detection of decision card sections."""
        assert mapper.is_decision_card('Vonnis/arrest van 17 januari 2023')
        assert mapper.is_decision_card('Jugement/arrêt du 15 mars 2023')
        assert mapper.is_decision_card('Beschikking van 10 februari 2023')
        assert not mapper.is_decision_card('Fiche 1')
        assert not mapper.is_decision_card('Tekst van de beslissing')
    
    def test_fiche_card_detection(self, mapper):
        """Test detection of Fiche card sections."""
        assert mapper.is_fiche_card('Fiche')
        assert mapper.is_fiche_card('Fiche 1')
        assert mapper.is_fiche_card('Fiches 2 - 5')
        assert not mapper.is_fiche_card('Vonnis/arrest van 17 januari 2023')
        assert not mapper.is_fiche_card('Tekst van de beslissing')
    
    def test_full_text_section_detection(self, mapper):
        """Test detection of full text sections."""
        assert mapper.is_full_text_section('Texte de la décision')
        assert mapper.is_full_text_section('Tekst van de beslissing')
        assert mapper.is_full_text_section('Text der Entscheidung')
        assert not mapper.is_full_text_section('Fiche 1')
        assert not mapper.is_full_text_section('Vonnis/arrest van 17 januari 2023')
    
    def test_field_identification(self, mapper):
        """Test identification of field names from text."""
        assert mapper.identify_field('ECLI nr:') == 'ecli'
        assert mapper.identify_field('Rolnummer:') == 'rolNumber'
        assert mapper.identify_field('Kamer:') == 'chamber'
        assert mapper.identify_field('Rechtsgebied:') == 'fieldOfLaw'
        assert mapper.identify_field('Thesaurus CAS:') == 'keywordsCassation'
        assert mapper.identify_field('Random text') is None
    
    def test_fiche_number_extraction(self, mapper):
        """Test extraction of Fiche numbers from legend."""
        assert mapper.extract_fiche_numbers('Fiche') == ['1']
        assert mapper.extract_fiche_numbers('Fiche 3') == ['3']
        assert mapper.extract_fiche_numbers('Fiches 2 - 5') == ['2', '3', '4', '5']
        assert mapper.extract_fiche_numbers('Fiches 1 – 3') == ['1', '2', '3']
        assert mapper.extract_fiche_numbers('Random text') == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])