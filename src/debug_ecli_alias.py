#!/usr/bin/env python3
"""
Debug script to test ecliAlias extraction issue.
Downloads specific test files from S3 and runs transformer to debug ecliAlias field extraction.
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

# Add parent directory for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def download_test_files():
    """Download specific test files from S3."""
    
    # Get AWS configuration
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-2')
    bucket_name = os.getenv('S3_BUCKET_NAME')
    s3_prefix = os.getenv('S3_PREFIX', '')
    
    if not all([aws_access_key, aws_secret_key, bucket_name]):
        logger.error("Missing AWS credentials in .env file")
        return False
    
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )
    
    # Create test directory
    test_dir = Path("test_jsons")
    test_dir.mkdir(exist_ok=True)
    
    # Files to download - using an existing file from S3
    # NOTE: The originally requested file doesn't exist, using a different GHCC file for testing
    test_files = [
        "juportal.be_BE_GHCC_1985_ARR.003_FR.json",
        "juportal.be_BE_GHCC_1985_ARR.003_NL.json"
    ]
    
    downloaded = []
    
    for filename in test_files:
        try:
            # Construct S3 key
            if s3_prefix:
                s3_key = f"{s3_prefix.rstrip('/')}/{filename}"
            else:
                s3_key = filename
            
            local_path = test_dir / filename
            
            logger.info(f"Downloading {s3_key} from S3...")
            s3_client.download_file(bucket_name, s3_key, str(local_path))
            logger.info(f"✅ Downloaded to {local_path}")
            downloaded.append(local_path)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"❌ File not found in S3: {s3_key}")
            else:
                logger.error(f"❌ Error downloading {filename}: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error downloading {filename}: {e}")
    
    return downloaded

def analyze_json_structure(filepath):
    """Analyze the JSON structure to find ecliAlias."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Analyzing: {filepath.name}")
    logger.info(f"{'='*60}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Look for ecliAlias patterns in sections
    ecli_alias_found = False
    
    if 'sections' in data:
        for section in data['sections']:
            legend = section.get('legend', '')
            
            # Check for ecliAlias patterns
            ecli_patterns = [
                "Remplace le Numéro",
                "Remplace le numéro", 
                "Vervangt nummer",
                "Ersetzt alte Nummer"
            ]
            
            for pattern in ecli_patterns:
                if pattern in legend:
                    logger.info(f"✅ Found ecliAlias legend: '{legend}'")
                    ecli_alias_found = True
                    
                    # Check paragraphs
                    if 'paragraphs' in section:
                        for i, para in enumerate(section['paragraphs']):
                            text = para.get('text', '')
                            if pattern in text:
                                logger.info(f"  Paragraph {i}: '{text}'")
                                # Check next paragraph for value
                                if i + 1 < len(section['paragraphs']):
                                    next_text = section['paragraphs'][i + 1].get('text', '')
                                    logger.info(f"  Next paragraph (potential value): '{next_text}'")
    
    if not ecli_alias_found:
        logger.warning("❌ No ecliAlias legend found in sections")
        
        # Look for it in all text
        json_str = json.dumps(data, ensure_ascii=False)
        for pattern in ["Remplace", "Vervangt", "Ersetzt"]:
            if pattern in json_str:
                logger.info(f"  But found '{pattern}' somewhere in the JSON")
    
    return data

def run_transformer(filepath):
    """Run the transformer on the test file."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Running transformer on: {filepath.name}")
    logger.info(f"{'='*60}")
    
    # Import transformer
    from src.transformer import TwoPhaseTransformerWithDedup
    
    # Create output directory
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    
    # Clear output directory
    for f in output_dir.glob("*.json"):
        f.unlink()
    
    # Copy test file to input directory
    input_dir = Path("test_input")
    input_dir.mkdir(exist_ok=True)
    
    import shutil
    shutil.copy(filepath, input_dir / filepath.name)
    
    # Run transformer
    transformer = TwoPhaseTransformerWithDedup(str(input_dir), str(output_dir))
    
    # Run phase 1 only (no LLM)
    transformer.run_phase1()
    
    # Check output
    output_files = list(output_dir.glob("*.json"))
    
    if output_files:
        output_file = output_files[0]
        with open(output_file, 'r', encoding='utf-8') as f:
            result = json.load(f)
        
        # Check for ecli_alias field
        if 'ecli_alias' in result:
            logger.info(f"✅ ecli_alias field found: {result['ecli_alias']}")
        else:
            logger.warning("❌ ecli_alias field NOT found in output")
            logger.info("Fields in output:")
            for key in result.keys():
                if key != 'full_text' and key != 'full_html':  # Skip large fields
                    logger.info(f"  - {key}: {result[key]}")
        
        return result
    else:
        logger.error("❌ No output file generated")
        return None

def main():
    """Main debug function."""
    
    logger.info("Starting ecliAlias debug script")
    
    # Step 1: Download test files
    logger.info("\nStep 1: Downloading test files from S3...")
    downloaded_files = download_test_files()
    
    if not downloaded_files:
        logger.error("Failed to download test files")
        return
    
    # Step 2: Analyze JSON structure
    logger.info("\nStep 2: Analyzing JSON structure...")
    for filepath in downloaded_files:
        data = analyze_json_structure(filepath)
    
    # Step 3: Run transformer
    logger.info("\nStep 3: Running transformer...")
    for filepath in downloaded_files:
        result = run_transformer(filepath)
        
        if result:
            # Compare language versions
            lang = "FR" if "_FR.json" in str(filepath) else "NL"
            logger.info(f"\nResults for {lang} version:")
            logger.info(f"  ECLI: {result.get('decision_id', 'N/A')}")
            logger.info(f"  ecli_alias: {result.get('ecli_alias', 'NOT FOUND')}")
    
    logger.info("\n" + "="*60)
    logger.info("Debug script completed")
    logger.info("="*60)

if __name__ == "__main__":
    main()