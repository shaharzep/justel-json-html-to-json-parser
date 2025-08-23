# Test Suite Documentation

## Overview

This comprehensive test suite ensures the reliability and correctness of the Juportal Decisions Parser. It covers all critical field extractions, text processing, and transformation logic.

## Test Structure

```
tests/
├── __init__.py
├── README.md
├── fixtures/               # Test data and fixtures
│   └── sample_input_data.py
├── unit/                  # Unit tests for individual functions
│   ├── test_field_extraction.py
│   ├── test_text_processing.py
│   └── test_notices.py
└── integration/           # End-to-end transformation tests
    └── test_full_transformation.py
```

## Running Tests

### Quick Start

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
python run_tests.py

# Run with coverage
python run_tests.py --type coverage
```

### Using Make

```bash
# Run all tests
make test

# Run specific test categories
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-field        # Field extraction tests
make test-text         # Text processing tests
make test-notices      # Notices extraction tests

# Generate coverage report
make coverage
```

### Using pytest directly

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_field_extraction.py

# Run with coverage
pytest tests/ --cov=juportal_utils --cov-report=html
```

## Test Categories

### 1. Field Extraction Tests (`test_field_extraction.py`)

Tests all field extraction functions:
- **ECLI extraction** from filename
- **Date extraction** from ECLI, legend, and filename
- **Court code** extraction
- **Decision type** extraction
- **Language** extraction from filename
- **URL building** from ECLI
- **PDF URL** extraction
- **Version** parsing
- **ECLI alias** formatting

### 2. Text Processing Tests (`test_text_processing.py`)

Tests text manipulation functions:
- **Text cleaning** and normalization
- **PDF suffix removal** (critical for full_text)
- **Paragraph text extraction**
- **Paragraph HTML extraction**
- **Field value extraction** from paragraphs
- **Link extraction** from paragraphs
- **Legal basis parsing**

### 3. Notices Field Tests (`test_notices.py`)

Tests notice extraction and processing:
- **Summary extraction** (first paragraph rule)
- **Keywords Cassation** extraction with deduplication
- **Keywords UTU** extraction with deduplication
- **Keywords Free** extraction and concatenation
- **Legal basis** extraction with HTML parsing
- **Multi-fiche card** handling
- **Notice ID** assignment
- **Keyword deduplication** across multiple sections

### 4. Integration Tests (`test_full_transformation.py`)

End-to-end transformation tests:
- **French document** transformation
- **Dutch document** transformation  
- **German document** transformation
- **Multi-fiche document** handling
- **Empty sections** handling
- **Complex legal basis** extraction
- **CONC file skipping**
- **Language validation**
- **ECLI alias extraction**

## Critical Fields Tested

### Core Fields
- ✅ `fileName` - Preserved from input
- ✅ `ecli` - Extracted from filename/content
- ✅ `url` - Built from ECLI and language
- ✅ `metaLanguage` - Extracted from filename
- ✅ `decisionDate` - Multiple extraction methods

### Text Fields
- ✅ `full_text` - Complete text with PDF suffix removal
- ✅ `full_textHtml` - HTML preservation and formatting
- ✅ `pdfUrl` - Extraction from links

### Notice Fields
- ✅ `notices[].summary` - First paragraph extraction
- ✅ `notices[].keywordsCassation` - Array with deduplication
- ✅ `notices[].keywordsUtu` - Array with deduplication
- ✅ `notices[].keywordsFree` - String concatenation
- ✅ `notices[].legalBasis` - HTML parsing with <br> handling
- ✅ `notices[].noticeId` - Proper ID assignment

### Metadata Fields
- ✅ `rolNumber` - Role number extraction
- ✅ `chamber` - Chamber extraction
- ✅ `fieldOfLaw` - Field of law extraction
- ✅ `courtEcliCode` - Court code from ECLI
- ✅ `decisionTypeEcliCode` - Decision type from ECLI

### Related Publications
- ✅ `citing` - ECLI array extraction
- ✅ `precedent` - ECLI array extraction
- ✅ `citedIn` - ECLI array extraction
- ✅ `justel` - Link extraction
- ✅ `seeMoreRecently` - ECLI array extraction
- ✅ `precededBy` - ECLI array extraction
- ✅ `followedBy` - ECLI array extraction

## Edge Cases Covered

1. **Empty/Missing Data**
   - Empty sections
   - Missing paragraphs
   - Null values
   - Empty strings

2. **Special Characters**
   - HTML entities
   - Unicode characters
   - Special punctuation

3. **Multi-language Support**
   - French (FR)
   - Dutch (NL)
   - German (DE)

4. **Complex Structures**
   - Multi-fiche cards
   - Duplicate keywords
   - Complex legal basis with HTML breaks
   - Nested HTML tags

## Coverage Goals

- **Target Coverage**: 80% minimum
- **Critical Functions**: 100% coverage for:
  - full_text extraction
  - full_textHtml extraction
  - All notice fields
  - Date extraction
  - Language detection

## Continuous Integration

The test suite is designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions configuration
- name: Run tests
  run: |
    pip install -r requirements-test.txt
    python run_tests.py --type coverage
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Adding New Tests

When adding new features or fixing bugs:

1. **Write test first** (TDD approach)
2. **Add to appropriate test file** or create new one
3. **Include edge cases**
4. **Update this documentation**
5. **Ensure coverage remains > 80%**

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're in the project root directory
2. **Missing dependencies**: Run `pip install -r requirements-test.txt`
3. **Path issues**: Tests use relative imports, run from project root

### Debug Mode

```bash
# Run tests with detailed output
pytest tests/ -vv --tb=long

# Run specific test with debug
pytest tests/unit/test_field_extraction.py::TestFieldExtraction::test_extract_date_from_ecli -vv
```

## Performance

- Unit tests: ~1-2 seconds
- Integration tests: ~5-10 seconds
- Full test suite: ~15-20 seconds

## Maintenance

- Review test coverage monthly
- Update fixtures when schema changes
- Add regression tests for bugs
- Keep test data minimal but comprehensive