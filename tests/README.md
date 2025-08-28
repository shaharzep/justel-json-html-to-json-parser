# Test Suite for Juportal Decisions Parser

## Overview

This comprehensive test suite covers all critical components of the `transformer.py` transformation pipeline, including:

- Field extraction from JSON sections
- Date parsing and extraction 
- Language validation and detection
- Text processing and cleaning
- ECLI parsing and manipulation
- Deduplication logic
- End-to-end transformation pipeline
- Batch LLM validation

## Test Structure

```
tests/
├── unit/                           # Unit tests for individual components
│   ├── test_field_extraction.py   # Field extraction from JSON sections
│   ├── test_date_extraction.py    # Date parsing logic
│   ├── test_language_validation.py # Language detection and validation
│   ├── test_text_processing.py    # Text cleaning and HTML processing
│   ├── test_ecli_processing.py    # ECLI parsing and manipulation
│   └── test_deduplication.py      # Deduplication logic
├── integration/                    # Integration tests
│   └── test_transform_pipeline.py # End-to-end transformation tests
├── fixtures/                       # Test fixtures and sample data
│   └── sample_data/               # Sample JSON files for testing
└── conftest.py                    # Shared pytest fixtures

```

## Running the Tests

### Run all tests
```bash
python -m pytest tests/
```

### Run with verbose output
```bash
python -m pytest tests/ -v
```

### Run specific test file
```bash
python -m pytest tests/unit/test_field_extraction.py
```

### Run specific test class or method
```bash
python -m pytest tests/unit/test_field_extraction.py::TestDecisionCardExtraction
python -m pytest tests/unit/test_field_extraction.py::TestDecisionCardExtraction::test_ecli_extraction
```

### Run by test type using markers
```bash
# Unit tests only
python -m pytest tests/ -m unit

# Integration tests only  
python -m pytest tests/ -m integration

# Field extraction tests
python -m pytest tests/ -m field_extraction

# Text processing tests
python -m pytest tests/ -m text_processing

# Validation tests
python -m pytest tests/ -m validation
```

### Run with coverage report
```bash
# Generate terminal coverage report
python -m pytest tests/ --cov=juportal_utils --cov=src --cov-report=term-missing

# Generate HTML coverage report
python -m pytest tests/ --cov=juportal_utils --cov=src --cov-report=html

# View HTML report
open htmlcov/index.html
```

### Run with different verbosity levels
```bash
# Quiet mode (less output)
python -m pytest tests/ -q

# Verbose mode (more output)
python -m pytest tests/ -v

# Show print statements
python -m pytest tests/ -s
```

### Stop on first failure
```bash
python -m pytest tests/ -x
```

### Run failed tests from last run
```bash
python -m pytest tests/ --lf
```

## Test Coverage Areas

### Unit Tests

1. **Field Extraction** (`test_field_extraction.py`)
   - Decision card field extraction (ECLI, rol number, chamber, etc.)
   - Fiche card field extraction (summaries, keywords, legal basis)
   - Related publications extraction (citing, precedent, cited_in)
   - Multi-fiche consolidation
   - Field mapping configuration

2. **Date Extraction** (`test_date_extraction.py`)
   - ECLI date extraction (YYYYMMDD format)
   - Legend date extraction (multi-language)
   - LLM fallback for date extraction
   - Partial date handling (year-only)
   - Invalid date handling

3. **Language Validation** (`test_language_validation.py`)
   - Language detection from text
   - Language metadata matching
   - Dutch/Afrikaans confusion handling
   - German content detection in FR/NL files
   - LLM validation fallback
   - Empty document handling

4. **Text Processing** (`test_text_processing.py`)
   - Text cleaning and normalization
   - HTML extraction from paragraphs
   - PDF URL extraction
   - PDF suffix removal
   - Empty content handling ("<>" placeholder)

5. **ECLI Processing** (`test_ecli_processing.py`)
   - ECLI extraction from filename
   - Jurisdiction extraction
   - Court code extraction
   - Decision type extraction
   - ECLI alias formatting
   - URL building from ECLI

6. **Deduplication** (`test_deduplication.py`)
   - ECLI index building
   - Duplicate detection via aliases
   - File removal logic
   - Circular reference handling
   - German file removal

### Integration Tests

1. **Transform Pipeline** (`test_transform_pipeline.py`)
   - Complete file transformation (raw JSON → output JSON)
   - Enhanced transformer with HTML extraction
   - Two-phase transformation workflow
   - CONC file skipping
   - Language mismatch detection
   - Schema validation
   - Error handling

## Key Test Patterns

### Mocking External Dependencies
Tests mock external dependencies like the OpenAI API to avoid making real API calls:

```python
@patch('juportal_utils.utils.LLMValidator')
def test_llm_fallback(self, mock_llm_class):
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    # ... test logic
```

### Temporary File Handling
Tests use temporary directories for file operations:

```python
@pytest.fixture
def temp_dirs(self):
    temp_base = tempfile.mkdtemp()
    yield Path(temp_base)
    shutil.rmtree(temp_base)  # Cleanup
```

### Parameterized Tests
Some tests use parameterization for testing multiple scenarios:

```python
test_cases = [
    ('ECLI:BE:COURT:2023:JUG.123', 'JUG'),
    ('ECLI:BE:COURT:2023:DEC.456', 'DEC'),
]
for ecli, expected in test_cases:
    result = extract_decision_type_from_ecli(ecli)
    assert result == expected
```

## Dependencies

The test suite requires the following packages:
- pytest
- pytest-cov
- pytest-mock
- python-dotenv
- langdetect
- openai (for mocking)

Install with:
```bash
pip install pytest pytest-cov pytest-mock python-dotenv langdetect openai
```

## Environment Variables

Some tests may require environment variables. Create a `.env.test` file:

```bash
OPENAI_API_KEY=test-api-key
```

## Continuous Integration

The test suite is designed to run in CI/CD pipelines. Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ --cov --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Troubleshooting

### Missing CSV mapping file
If `Sheet1.csv` is missing, the FieldMapper will use default mappings. To use custom mappings, create the CSV file with field mappings.

### LLM tests failing
LLM-related tests are mocked by default. If you want to test with real API calls, set the `OPENAI_API_KEY` environment variable.

### Coverage requirements
The pytest.ini file sets a coverage requirement of 80%. To disable:
```bash
python -m pytest tests/ --no-cov
```

## Contributing

When adding new functionality:
1. Write unit tests for individual functions
2. Write integration tests for end-to-end workflows
3. Ensure tests are properly mocked to avoid external dependencies
4. Update this README with any new test patterns or requirements
5. Aim for >80% code coverage