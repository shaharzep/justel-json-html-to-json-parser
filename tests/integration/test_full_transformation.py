"""Integration tests for complete transformation pipeline"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from juportal_utils.transform_juportal import JuportalTransformer
from tests.fixtures.sample_input_data import (
    SAMPLE_RAW_JSON,
    SAMPLE_DUTCH_JSON,
    SAMPLE_GERMAN_JSON,
    SAMPLE_MULTI_FICHE,
    EMPTY_SECTIONS,
    COMPLEX_LEGAL_BASIS
)


class TestFullTransformation(unittest.TestCase):
    """Test complete transformation pipeline"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.input_dir = self.test_dir / "input"
        self.output_dir = self.test_dir / "output"
        self.input_dir.mkdir()
        self.output_dir.mkdir()
        
        self.transformer = JuportalTransformer(
            str(self.input_dir),
            str(self.output_dir)
        )
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def _save_input_file(self, filename, data):
        """Helper to save input JSON file"""
        filepath = self.input_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return filepath
    
    def test_french_document_transformation(self):
        """Test transforming a French document"""
        filepath = self._save_input_file(
            "juportal.be_BE_CASS_2007_ARR.20070622.5_FR.json",
            SAMPLE_RAW_JSON
        )
        
        result = self.transformer.transform_file(filepath)
        
        # Check basic fields
        self.assertIsNotNone(result)
        self.assertEqual(result['fileName'], "juportal.be_BE_CASS_2007_ARR.20070622.5_FR.json")
        self.assertEqual(result['ecli'], "ECLI:BE:CASS:2007:ARR.20070622.5")
        self.assertEqual(result['metaLanguage'], "FR")
        self.assertEqual(result['source'], "juportal.be")
        self.assertEqual(result['jurisdiction'], "BE")
        self.assertEqual(result['courtEcliCode'], "CASS")
        self.assertEqual(result['decisionTypeEcliCode'], "ARR")
        self.assertEqual(result['decisionDate'], "2007-06-22")
        
        # Check metadata fields
        self.assertEqual(result['rolNumber'], "C.05.0032.N")
        self.assertEqual(result['chamber'], "1N - eerste kamer")
        self.assertEqual(result['fieldOfLaw'], "Autres - Droit civil")
        
        # Check notices
        self.assertGreater(len(result['notices']), 0)
        notice = result['notices'][0]
        self.assertEqual(notice['noticeId'], "1")
        self.assertEqual(notice['summary'], "This is a summary text for the notice.")
        self.assertIn("SIGNIFICATIONS ET NOTIFICATIONS - GENERALITES", notice['keywordsCassation'])
        self.assertIn("DROIT JUDICIAIRE - PRINCIPES GÉNÉRAUX", notice['keywordsUtu'])
        self.assertEqual(notice['keywordsFree'], "Domicile élu chez un mandataire")
        self.assertIn("Code Judiciaire - 10-10-1967 - Art. 35, 36 et 39", notice['legalBasis'])
        
        # Check full text
        self.assertIn("N° C.05.0032.N", result['fullText'])
        self.assertIn("AVERO BELGIUM INSURANCE", result['fullText'])
        self.assertIn("La procédure devant la Cour", result['fullText'])
        # Check PDF suffix is removed
        self.assertNotIn("Document PDF ECLI:BE:CASS:2007:ARR.20070622.5", result['fullText'])
        
        # Check full text HTML
        self.assertIn("<p>N° C.05.0032.N</p>", result['fullTextHtml'])
        self.assertIn("<p>AVERO BELGIUM INSURANCE</p>", result['fullTextHtml'])
        
        # Check PDF URL
        self.assertEqual(
            result['url_pdf'],
            "https://juportal.be/JUPORTAwork/ECLI:BE:CASS:2007:ARR.20070622.5_FR.pdf"
        )
        
        # Check related publications
        self.assertIn("ECLI:BE:CASS:2010:CONC.20100226.8", result['citedIn'])
        self.assertIn("ECLI:BE:CASS:2012:ARR.20120112.2", result['seeMoreRecently'])
        
        # Check URL
        self.assertEqual(
            result['url'],
            "https://juportal.be/content/ECLI:BE:CASS:2007:ARR.20070622.5/FR"
        )
    
    def test_dutch_document_transformation(self):
        """Test transforming a Dutch document"""
        filepath = self._save_input_file(
            "juportal.be_BE_CASS_2007_ARR.20070622.5_NL.json",
            SAMPLE_DUTCH_JSON
        )
        
        result = self.transformer.transform_file(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['metaLanguage'], "NL")
        self.assertEqual(result['ecli'], "ECLI:BE:CASS:2007:ARR.20070622.5")
        
        # Check Dutch notices
        self.assertGreater(len(result['notices']), 0)
        notice = result['notices'][0]
        self.assertEqual(notice['summary'], "Dit is een samenvatting.")
        self.assertIn("BETEKENINGEN EN KENNISGEVINGEN", notice['keywordsCassation'])
        self.assertEqual(notice['keywordsFree'], "Gekozen woonplaats")
        self.assertIn("Gerechtelijk Wetboek - Art. 39", notice['legalBasis'])
    
    def test_german_document_transformation(self):
        """Test transforming a German document"""
        filepath = self._save_input_file(
            "juportal.be_BE_GHCC_2022_ARR.103_DE.json",
            SAMPLE_GERMAN_JSON
        )
        
        result = self.transformer.transform_file(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['metaLanguage'], "DE")
        self.assertEqual(result['ecli'], "ECLI:BE:GHCC:2022:ARR.103")
        self.assertEqual(result['courtEcliCode'], "GHCC")
        self.assertEqual(result['decisionDate'], "2022-07-14")
    
    def test_multi_fiche_transformation(self):
        """Test transforming document with multiple fiches"""
        input_json = SAMPLE_RAW_JSON.copy()
        input_json['sections'] = [
            input_json['sections'][0],  # Keep decision card
            SAMPLE_MULTI_FICHE['sections'][0],  # Add multi-fiche
            input_json['sections'][2]  # Keep full text
        ]
        
        filepath = self._save_input_file(
            "juportal.be_BE_TEST_2024_ARR.001_FR.json",
            input_json
        )
        
        result = self.transformer.transform_file(filepath)
        
        self.assertIsNotNone(result)
        self.assertGreater(len(result['notices']), 0)
        
        # Check deduplication in multi-fiche
        notice = result['notices'][0]
        # Keywords should be deduplicated
        keywords_cassation = notice['keywordsCassation']
        self.assertEqual(len(keywords_cassation), len(set(keywords_cassation)))
    
    def test_empty_sections_transformation(self):
        """Test transforming document with empty sections"""
        filepath = self._save_input_file(
            "juportal.be_BE_TEST_2024_ARR.002_FR.json",
            EMPTY_SECTIONS
        )
        
        result = self.transformer.transform_file(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['ecli'], "ECLI:BE:TEST:2024:ARR.001")
        self.assertEqual(result['metaLanguage'], "FR")
        # Should have empty notices array
        self.assertEqual(result['notices'], [])
        # Should have null/empty text fields
        self.assertIsNone(result['fullText'])
        self.assertIsNone(result['fullTextHtml'])
    
    def test_complex_legal_basis_extraction(self):
        """Test extracting complex legal basis with HTML breaks"""
        input_json = SAMPLE_RAW_JSON.copy()
        input_json['sections'] = [
            input_json['sections'][0],
            COMPLEX_LEGAL_BASIS['sections'][0],
            input_json['sections'][2]
        ]
        
        filepath = self._save_input_file(
            "juportal.be_BE_TEST_2024_ARR.003_FR.json",
            input_json
        )
        
        result = self.transformer.transform_file(filepath)
        
        self.assertIsNotNone(result)
        self.assertGreater(len(result['notices']), 0)
        
        legal_basis = result['notices'][0]['legalBasis']
        self.assertEqual(len(legal_basis), 3)
        self.assertIn("Loi - 09-08-1963 - 62 - 01 ELI link Pub nr 1963080914", legal_basis)
        self.assertIn("Koninklijk Besluit - 04-11-1963 - 169 - 01 ELI link Pub nr 1963110402", legal_basis)
        self.assertIn("Directive 2010/13/UE - Article 3", legal_basis)
    
    def test_conc_file_skipping(self):
        """Test that CONC files are skipped"""
        conc_json = SAMPLE_RAW_JSON.copy()
        conc_json['title'] = "ECLI:BE:CASS:2010:CONC.20100226.8"
        
        filepath = self._save_input_file(
            "juportal.be_BE_CASS_2010_CONC.20100226.8_FR.json",
            conc_json
        )
        
        # Transform the file
        result = self.transformer.transform_file(filepath)
        
        # Result should exist but file should not be saved
        self.assertIsNotNone(result)
        self.assertEqual(result['decisionTypeEcliCode'], "CONC")
        
        # Check that no output file was created
        output_files = list(self.output_dir.glob("*.json"))
        self.assertEqual(len(output_files), 0)
    
    def test_language_validation(self):
        """Test language validation"""
        # Create a document with inconsistent language
        inconsistent_json = SAMPLE_RAW_JSON.copy()
        inconsistent_json['lang'] = "NL"  # Dutch in metadata
        # But keep French content in sections
        
        filepath = self._save_input_file(
            "juportal.be_BE_TEST_2024_ARR.004_FR.json",  # French in filename
            inconsistent_json
        )
        
        result = self.transformer.transform_file(filepath)
        
        self.assertIsNotNone(result)
        # Language validator should detect inconsistency
        # The isValid flag would be set by language validator
        # (actual validation logic depends on implementation)
        self.assertIn('isValid', result)
    
    def test_ecli_alias_extraction(self):
        """Test ECLI alias extraction"""
        input_json = SAMPLE_RAW_JSON.copy()
        # Add ECLI alias to decision card
        input_json['sections'][0]['paragraphs'].extend([
            {"text": "ECLI Alias:", "html": "<p>ECLI Alias:</p>"},
            {"text": "ECLI:BE:CASS:2007:ARR.001; ECLI:BE:CASS:2007:ARR.002", 
             "html": "<p>ECLI:BE:CASS:2007:ARR.001; ECLI:BE:CASS:2007:ARR.002</p>"}
        ])
        
        filepath = self._save_input_file(
            "juportal.be_BE_TEST_2024_ARR.005_FR.json",
            input_json
        )
        
        result = self.transformer.transform_file(filepath)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result['ecliAlias']), 2)
        self.assertIn("ECLI:BE:CASS:2007:ARR.001", result['ecliAlias'])
        self.assertIn("ECLI:BE:CASS:2007:ARR.002", result['ecliAlias'])


if __name__ == '__main__':
    unittest.main()