#!/usr/bin/env python3
"""
Shared pytest fixtures and configuration for all tests.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
import sys
from unittest.mock import Mock, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def sample_ecli():
    """Sample ECLI for testing."""
    return "ECLI:BE:CASS:2023:ARR.20230117.2N.7"


@pytest.fixture(scope="session")
def sample_raw_json_fr():
    """Sample French raw JSON document."""
    return {
        "file": "test_fr.txt",
        "lang": "FR",
        "title": "ECLI:BE:CASS:2023:ARR.20230315.1F.2",
        "sections": [
            {
                "legend": "Jugement/arrêt du 15 mars 2023",
                "paragraphs": [
                    {"text": "ECLI nr:", "html": "<p>ECLI nr:</p>"},
                    {"text": "ECLI:BE:CASS:2023:ARR.20230315.1F.2", "html": "<p>ECLI:BE:CASS:2023:ARR.20230315.1F.2</p>"},
                    {"text": "Numéro de rôle:", "html": "<p>Numéro de rôle:</p>"},
                    {"text": "C.22.0123.F", "html": "<p>C.22.0123.F</p>"},
                    {"text": "Affaire:", "html": "<p>Affaire:</p>"},
                    {"text": "X c. Y", "html": "<p>X c. Y</p>"},
                    {"text": "Chambre:", "html": "<p>Chambre:</p>"},
                    {"text": "1F - première chambre", "html": "<p>1F - première chambre</p>"},
                    {"text": "Domaine juridique:", "html": "<p>Domaine juridique:</p>"},
                    {"text": "Droit civil", "html": "<p>Droit civil</p>"}
                ]
            },
            {
                "legend": "Fiche",
                "paragraphs": [
                    {"text": "Résumé de l'affaire concernant un contrat.", "html": "<p>Résumé de l'affaire concernant un contrat.</p>"},
                    {"text": "Thésaurus CAS:", "html": "<p>Thésaurus CAS:</p>"},
                    {"text": "CONTRAT", "html": "<p>CONTRAT</p>"},
                    {"text": "Mots-clés UTU:", "html": "<p>Mots-clés UTU:</p>"},
                    {"text": "Responsabilité contractuelle", "html": "<p>Responsabilité contractuelle</p>"},
                    {"text": "Mots-clés libres:", "html": "<p>Mots-clés libres:</p>"},
                    {"text": "cassation droit civil contrat", "html": "<p>cassation droit civil contrat</p>"},
                    {"text": "Base légale:", "html": "<p>Base légale:</p>"},
                    {"text": "Art. 1134 Code civil", "html": "<p>Art. 1134 Code civil</p>"}
                ]
            },
            {
                "legend": "Texte de la décision",
                "paragraphs": [
                    {"text": "La Cour de cassation rejette le pourvoi.", "html": "<p>La Cour de cassation rejette le pourvoi.</p>"},
                    {"text": "Attendu que le moyen ne peut être accueilli.", "html": "<p>Attendu que le moyen ne peut être accueilli.</p>"}
                ]
            }
        ]
    }


@pytest.fixture(scope="session")
def sample_raw_json_nl():
    """Sample Dutch raw JSON document."""
    return {
        "file": "test_nl.txt",
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
                    {"text": "Zaak:", "html": "<p>Zaak:</p>"},
                    {"text": "M.", "html": "<p>M.</p>"},
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
                    {"text": "STRAFUITVOERING", "html": "<p>STRAFUITVOERING</p>"},
                    {"text": "Trefwoorden UTU:", "html": "<p>Trefwoorden UTU:</p>"},
                    {"text": "Voorlopige invrijheidstelling", "html": "<p>Voorlopige invrijheidstelling</p>"},
                    {"text": "Vrije trefwoorden:", "html": "<p>Vrije trefwoorden:</p>"},
                    {"text": "cassatie strafrecht", "html": "<p>cassatie strafrecht</p>"},
                    {"text": "Wettelijke basis:", "html": "<p>Wettelijke basis:</p>"},
                    {"text": "Art. 47 Wet Strafuitvoering", "html": "<p>Art. 47 Wet Strafuitvoering</p>"}
                ]
            },
            {
                "legend": "Tekst van de beslissing",
                "paragraphs": [
                    {"text": "Het Hof verwerpt het cassatieberoep.", "html": "<p>Het Hof verwerpt het cassatieberoep.</p>"}
                ]
            }
        ]
    }


@pytest.fixture
def temp_directory():
    """Create a temporary directory that is cleaned up after the test."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_llm_validator():
    """Mock LLM validator to avoid API calls during testing."""
    mock = MagicMock()
    mock.is_available.return_value = False  # Default to unavailable
    mock.validate_document.return_value = (False, 0.0, "Mock validation")
    return mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Mock response"))]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def sample_transformed_document():
    """Sample transformed document matching the target schema."""
    return {
        "file_name": "juportal.be_BE_CASS_2023_ARR.20230117.2N.7_NL.json",
        "decision_id": "ECLI:BE:CASS:2023:ARR.20230117.2N.7",
        "url_official_publication": "https://juportal.be/content/ECLI:BE:CASS:2023:ARR.20230117.2N.7/NL",
        "source": "juportal.be",
        "language_metadata": "NL",
        "jurisdiction": "BE",
        "court_ecli_code": "CASS",
        "decision_type_ecli_code": "ARR",
        "decision_date": "2023-01-17",
        "ecli_alias": [],
        "rol_number": "P.22.1741.N",
        "case": "M.",
        "chamber": "2N - tweede kamer",
        "field_of_law": "Strafrecht",
        "versions": [],
        "opinion_public_attorney": "",
        "summaries": [
            {
                "summaryId": "1",
                "summary": "Samenvatting van de zaak",
                "keywordsCassation": ["STRAFUITVOERING"],
                "keywordsUtu": ["Voorlopige invrijheidstelling"],
                "keywordsFree": "cassatie strafrecht",
                "legalBasis": ["Art. 47 Wet Strafuitvoering"]
            }
        ],
        "full_text": "Het Hof verwerpt het cassatieberoep.",
        "full_html": "<p>Het Hof verwerpt het cassatieberoep.</p>",
        "url_pdf": "",
        "citing": [],
        "precedent": [],
        "cited_in": [],
        "see_more_recently": [],
        "preceded_by": [],
        "followed_by": [],
        "rectification": [],
        "related_case": [],
        "isValid": True
    }


@pytest.fixture
def sample_invalid_document():
    """Sample document with invalid language."""
    doc = {
        "file_name": "test_invalid.json",
        "decision_id": "ECLI:BE:CASS:2023:ARR.123",
        "language_metadata": "FR",
        "full_text": "Dit is Nederlandse tekst maar metadata zegt Frans.",
        "summaries": [],
        "isValid": False
    }
    return doc


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset any singleton instances between tests."""
    # Reset language validator if needed
    from juportal_utils import language_validator
    if hasattr(language_validator, 'llm_validator'):
        language_validator.llm_validator = None
    yield
    # Cleanup after test if needed


@pytest.fixture
def mock_env_variables(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    yield
    # Variables are automatically restored after the test


# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "field_extraction: mark test as field extraction test"
    )
    config.addinivalue_line(
        "markers", "text_processing: mark test as text processing test"
    )
    config.addinivalue_line(
        "markers", "validation: mark test as validation test"
    )