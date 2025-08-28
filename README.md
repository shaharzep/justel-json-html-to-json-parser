# Juportal Decisions Parser

A Python-based tool for transforming Belgian legal decision JSON files from the Juportal.be database into a standardized schema format with enhanced validation and deduplication capabilities.

## Overview

This tool processes raw JSON files containing Belgian legal decisions and transforms them into a consistent, validated format suitable for further analysis or storage. The transformation includes:

- Schema standardization with flattened structure
- Language validation using both rule-based and LLM approaches
- Deduplication based on ECLI aliases
- Full text and HTML content extraction
- Related publications and citation extraction

## Project Structure

```
juportal-decisions-parser/
├── src/
│   └── transformer.py     # Main transformation script
├── utils/                          # Core utilities and classes
│   ├── __init__.py
│   ├── transform_juportal.py       # Base transformer class
│   ├── validators.py               # Schema validation
│   ├── utils.py                    # Text processing utilities
│   ├── mapping_config.py           # Field mapping configuration
│   ├── language_validator.py       # Language validation logic
│   ├── llm_validator.py           # LLM-based validation
│   └── batch_language_validator.py # Batch LLM processing
├── raw_jsons/                      # Input directory (raw JSON files)
├── send_jsons/                     # Output directory (transformed files)
├── schema.json                     # Target schema definition
├── .env.example                    # Environment variables template
└── README.md                       # This file
```

## Setup

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd juportal-decisions-parser
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key for LLM validation
```

### Required Environment Variables

**For transformation:**
- `OPENAI_API_KEY` (optional): Required only for LLM-based language validation in Phase 2

**For S3 sync (downloading):**
- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `AWS_REGION`: AWS region (e.g., us-east-1)
- `S3_BUCKET_NAME`: Name of the S3 bucket containing JSON files
- `S3_PREFIX`: Path prefix within the bucket (optional)

**For S3 upload (valid files):**
- `UPLOAD_AWS_ACCESS_KEY_ID`: AWS access key for upload account
- `UPLOAD_AWS_SECRET_ACCESS_KEY`: AWS secret key for upload account
- `UPLOAD_AWS_REGION`: AWS region for upload (e.g., us-east-2)
- `UPLOAD_S3_BUCKET`: S3 bucket name for uploading valid files
- `UPLOAD_S3_PREFIX`: S3 prefix for uploads (optional, defaults to 'juportal-valid-decisions')
- `UPLOAD_BATCH_SIZE`: Files per zip batch (optional, defaults to 10000)

## Usage

### S3 Sync Script (Download Raw Data)

Before transformation, download the raw JSON files from S3:

```bash
# Download all missing files from S3
python src/sync_s3_jsons.py

# Dry run to see what would be downloaded
python src/sync_s3_jsons.py --dry-run

# Use custom directory and more workers
python src/sync_s3_jsons.py --local-dir raw_jsons --workers 20
```

**S3 Sync Options:**
```bash
python src/sync_s3_jsons.py [OPTIONS]

Options:
  --local-dir, -d PATH  Local directory to sync files to (default: raw_jsons)
  --workers, -w INT     Number of parallel download workers (default: 10)
  --dry-run            Show what would be downloaded without downloading
  --verbose, -v        Enable verbose logging
```

### Main Transformation Script

The primary script is `src/transformer.py`, which performs a three-phase transformation:

```bash
python src/transformer.py --input raw_jsons --output output
```

### Command Line Options

```bash
python src/transformer.py [OPTIONS]

Options:
  --input, -i PATH     Input directory containing raw JSON files (default: raw_jsons)
  --output, -o PATH    Output directory for transformed files (default: send_jsons)
  --verbose, -v        Enable verbose logging
  --help              Show help message
```

## Transformation Process

### Phase 1: Core Transformation
- Transforms all raw JSON files to the target schema
- Extracts metadata, legal content, and citations
- Performs initial language validation (rule-based)
- Populates both `full_text` and `full_text_html` fields
- Extracts all related publications as top-level fields

### Phase 1.5: Deduplication
- Identifies duplicate files based on ECLI aliases
- Removes duplicates while preserving the best version
- Logs all deduplication actions

### Phase 2: LLM Validation
- Identifies files that failed initial language validation
- Uses OpenAI GPT-4o-mini for batch language validation
- Updates `isValid` flags based on LLM assessment
- Cost-effective batch processing for large datasets

## Schema Changes

The output schema has been updated to flatten the `relatedPublications` structure. All related publication fields are now at the top level:

- `decision`: String - Related decision reference
- `citing`: Array - ECLIs that cite this decision
- `precedent`: Array - Precedent ECLIs
- `citedIn`: Array - ECLIs that this decision is cited in
- `justel`: Array - Justel database links
- `seeMoreRecently`: Array - More recent related decisions
- `precededBy`: Array - Preceding decisions
- `followedBy`: Array - Following decisions
- `rectification`: Array - Rectification decisions
- `relatedCase`: Array - Related case ECLIs

## Typical Workflow

1. **Setup Environment**
   ```bash
   # Copy and configure environment variables
   cp .env.example .env
   # Edit .env with your AWS and OpenAI credentials
   ```

2. **Download Raw Data**
   ```bash
   # Sync all JSON files from S3 (first time or to get updates)
   python src/sync_s3_jsons.py
   ```

3. **Transform Data**
   ```bash
   # Run the full 3-phase transformation with deduplication
   python src/transformer.py --input raw_jsons --output output
   ```

4. **Upload Valid Files to S3**
   ```bash
   # Upload valid (non-German) files to S3 in compressed batches
   python upload_valid_to_s3_zipped.py
   ```

5. **Result**
   - Transformed files in `send_jsons/` directory
   - Statistics and logs showing processing results
   - Deduplicated and validated JSON files ready for use
   - Valid files uploaded to S3 in compressed batches

## Output Format

Each transformed file contains:

```json
{
  "fileName": "original_filename.json",
  "ecli": "ECLI:BE:COURT:YEAR:TYPE.NUMBER",
  "url": "https://juportal.be/content/...",
  "source": "juportal.be",
  "metaLanguage": "FR|NL|DE",
  "jurisdiction": "BE",
  "courtEcliCode": "COURT_CODE",
  "decisionTypeEcliCode": "ARR|DEC|AVIS|CONC",
  "decisionDate": "YYYY-MM-DD",
  "full_text": "Full decision text...",
  "full_textHtml": "<p>HTML formatted text...</p>",
  "citing": ["ECLI:...", "ECLI:..."],
  "citedIn": ["ECLI:...", "ECLI:..."],
  "isValid": true
}
```

## Performance

- **Phase 1**: Fast transformation (~1-2 files per second)
- **Phase 1.5**: Quick deduplication based on ECLI matching
- **Phase 2**: LLM validation in batches for cost efficiency

Typical processing times:
- 1,000 files: ~10-15 minutes total
- 10,000 files: ~2-3 hours total

## Validation

### Language Validation
- Initial rule-based validation using `langdetect`
- Fallback LLM validation for edge cases
- Confidence scoring and detailed logging

### Schema Validation
- Validates against target JSON schema
- Type checking for all fields
- Required field validation

## Troubleshooting

### Common Issues

1. **Missing OpenAI API key**: LLM validation will be skipped (Phase 2)
2. **Import errors**: Ensure all files are in correct directories
3. **Memory issues**: Large files are processed in batches

### Logs

All processing is logged with timestamps. Check the console output for:
- Transformation progress
- Validation results
- Error messages
- Performance statistics

## S3 Upload Script

### Upload Valid Files to S3

The `upload_valid_to_s3_zipped.py` script uploads valid, non-German JSON files to S3 in compressed batches:

```bash
python upload_valid_to_s3_zipped.py
```

**Features:**
- Filters files by `isValid: true` AND `metaLanguage != 'DE'`
- Compresses files into zip batches (default 10,000 files per batch)
- Shows compression statistics and upload progress
- Uses separate AWS credentials for upload account
- Automatically cleans up temporary files

**Configuration:**
Set these environment variables in your `.env` file:
```
UPLOAD_AWS_ACCESS_KEY_ID=your_upload_access_key
UPLOAD_AWS_SECRET_ACCESS_KEY=your_upload_secret_key
UPLOAD_AWS_REGION=us-east-2
UPLOAD_S3_BUCKET=your-destination-bucket
UPLOAD_S3_PREFIX=incoming
UPLOAD_BATCH_SIZE=10000
```

**Output:**
- Creates zip files named `juportal_valid_batch_0001.zip`, `juportal_valid_batch_0002.zip`, etc.
- Uploads to S3 with path: `s3://bucket/prefix/juportal_valid_batch_XXXX.zip`
- Shows compression ratios and upload statistics

## Additional Scripts

### Keyword Extraction

Extract keywords from all JSON files into a CSV:

```bash
python extract_keywords.py
```

This creates `keywords_extracted.csv` with columns: keyword, type, language

## Contributing

1. Follow the existing code style
2. Update tests when adding new features
3. Ensure backward compatibility with existing JSON files
4. Document any new configuration options