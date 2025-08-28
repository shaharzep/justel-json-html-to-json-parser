#!/usr/bin/env python3
import json
import os
import boto3
from pathlib import Path
from botocore.exceptions import ClientError
import sys
from datetime import datetime
from dotenv import load_dotenv
import zipfile
import tempfile
import shutil

# Load environment variables from .env file
load_dotenv()

def load_json_file(file_path):
    """Load and parse a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading {file_path}: {e}")
        return None

def create_zip_batch(files, batch_num, temp_dir):
    """Create a zip file containing a batch of JSON files."""
    zip_filename = f"juportal_valid_batch_{batch_num:04d}.zip"
    zip_path = Path(temp_dir) / zip_filename
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for file_path in files:
            # Add file to zip with just the filename (no directory structure)
            zipf.write(file_path, file_path.name)
    
    return zip_path

def upload_to_s3(s3_client, file_path, bucket_name, s3_key):
    """Upload a file to S3."""
    try:
        # Get file size for progress tracking
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"  Uploading {file_path.name} ({file_size_mb:.2f} MB)...")
        s3_client.upload_file(str(file_path), bucket_name, s3_key)
        return True
    except ClientError as e:
        print(f"Error uploading {file_path}: {e}")
        return False

def main():
    # Get S3 credentials from environment variables
    aws_access_key = os.environ.get('UPLOAD_AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('UPLOAD_AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('UPLOAD_AWS_REGION', 'eu-west-1')
    s3_bucket = os.environ.get('UPLOAD_S3_BUCKET')
    s3_prefix = os.environ.get('UPLOAD_S3_PREFIX', 'juportal-valid-decisions')
    
    # Batch size configuration
    batch_size = int(os.environ.get('UPLOAD_BATCH_SIZE', '10000'))
    
    # Validate environment variables
    if not all([aws_access_key, aws_secret_key, s3_bucket]):
        print("Error: Missing required environment variables")
        print("Please set:")
        print("  UPLOAD_AWS_ACCESS_KEY_ID")
        print("  UPLOAD_AWS_SECRET_ACCESS_KEY")
        print("  UPLOAD_S3_BUCKET")
        print("  UPLOAD_AWS_REGION (optional, defaults to eu-west-1)")
        print("  UPLOAD_S3_PREFIX (optional, defaults to 'juportal-valid-decisions')")
        print("  UPLOAD_BATCH_SIZE (optional, defaults to 10000)")
        sys.exit(1)
    
    # Initialize S3 client with upload credentials
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )
    
    # Directory containing JSON files
    output_dir = Path(__file__).parent / "output"
    
    # Get all JSON files
    json_files = list(output_dir.glob("*.json"))
    
    # Skip invalid_files.json
    json_files = [f for f in json_files if f.name != "invalid_files.json"]
    
    print(f"Found {len(json_files)} JSON files to process")
    print(f"Target S3 bucket: {s3_bucket}")
    print(f"S3 prefix: {s3_prefix}")
    print(f"Batch size: {batch_size} files per zip")
    print("-" * 80)
    
    # Filter for valid files (exclude invalid OR German language files)
    valid_files = []
    invalid_count = 0
    german_count = 0
    
    print("Checking file validity and language...")
    for json_file in json_files:
        # Load JSON to check isValid field and language
        data = load_json_file(json_file)
        
        if data is None:
            print(f"❌ Skipping {json_file.name} - Failed to load")
            invalid_count += 1
            continue
        
        # Check isValid field
        is_valid = data.get('isValid', False)
        
        # Check language
        meta_language = data.get('metaLanguage', '')
        
        # Skip if invalid OR German
        if not is_valid:
            invalid_count += 1
            continue
        
        if meta_language == 'DE':
            german_count += 1
            continue
        
        valid_files.append(json_file)
    
    print(f"\nFiles to upload: {len(valid_files)}")
    print(f"Invalid files skipped: {invalid_count}")
    print(f"German (DE) files skipped: {german_count}")
    print(f"Total files excluded: {invalid_count + german_count}")
    
    if not valid_files:
        print("No valid files to upload.")
        sys.exit(0)
    
    # Calculate number of batches
    num_batches = (len(valid_files) + batch_size - 1) // batch_size
    print(f"Will create {num_batches} zip file(s)")
    print("-" * 80)
    
    # Create temporary directory for zip files
    temp_dir = tempfile.mkdtemp(prefix="juportal_upload_")
    print(f"Using temporary directory: {temp_dir}\n")
    
    try:
        # Statistics
        uploaded_count = 0
        failed_uploads = []
        total_original_size = 0
        total_compressed_size = 0
        
        # Process files in batches
        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(valid_files))
            batch_files = valid_files[start_idx:end_idx]
            
            print(f"\nBatch {batch_num + 1}/{num_batches}:")
            print(f"  Files in batch: {len(batch_files)}")
            
            # Calculate original size
            batch_original_size = sum(f.stat().st_size for f in batch_files)
            total_original_size += batch_original_size
            print(f"  Original size: {batch_original_size / (1024 * 1024):.2f} MB")
            
            # Create zip file
            print(f"  Creating zip file...")
            zip_path = create_zip_batch(batch_files, batch_num + 1, temp_dir)
            
            # Get compressed size
            compressed_size = zip_path.stat().st_size
            total_compressed_size += compressed_size
            compression_ratio = (1 - compressed_size / batch_original_size) * 100
            print(f"  Compressed size: {compressed_size / (1024 * 1024):.2f} MB ({compression_ratio:.1f}% reduction)")
            
            # Construct S3 key
            s3_key = f"{s3_prefix}/{zip_path.name}"
            
            # Upload to S3
            if upload_to_s3(s3_client, zip_path, s3_bucket, s3_key):
                uploaded_count += 1
                print(f"✅ Successfully uploaded batch {batch_num + 1}")
            else:
                failed_uploads.append(zip_path.name)
                print(f"❌ Failed to upload batch {batch_num + 1}")
            
            # Delete the zip file after upload to save disk space
            zip_path.unlink()
        
        # Print summary
        print("\n" + "=" * 80)
        print("UPLOAD SUMMARY")
        print("=" * 80)
        print(f"Total files processed: {len(json_files)}")
        print(f"Files uploaded (valid & non-German): {len(valid_files)}")
        print(f"Invalid files skipped: {invalid_count}")
        print(f"German (DE) files skipped: {german_count}")
        print(f"Zip batches created: {num_batches}")
        print(f"Successfully uploaded: {uploaded_count}/{num_batches} batches")
        print(f"Failed uploads: {len(failed_uploads)}")
        
        # Compression statistics
        if total_original_size > 0:
            total_compression_ratio = (1 - total_compressed_size / total_original_size) * 100
            print(f"\nCompression Statistics:")
            print(f"  Total original size: {total_original_size / (1024 * 1024):.2f} MB")
            print(f"  Total compressed size: {total_compressed_size / (1024 * 1024):.2f} MB")
            print(f"  Overall compression ratio: {total_compression_ratio:.1f}% reduction")
        
        if failed_uploads:
            print("\nFailed uploads:")
            for filename in failed_uploads:
                print(f"  - {filename}")
        
        print(f"\nUpload completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Return exit code based on success
        if failed_uploads:
            sys.exit(1)
        else:
            sys.exit(0)
            
    finally:
        # Clean up temporary directory
        print(f"\nCleaning up temporary directory...")
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()