#!/usr/bin/env python3
"""
Pipeline orchestrator for JuPortal decisions processing
1. Scrape new decision URLs (fast - just discovers URLs)
2. Download HTML files sequentially with long timeouts (reliable for slow sites)
3. Convert HTML to JSON using html-2-json.py
4. Transform JSONs to final format with deduplication and validation
5. Upload valid files to S3 in compressed batches
"""

import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def clear_s3_folder():
    """Clear the S3 upload folder before starting the pipeline"""
    logger.info("=" * 60)
    logger.info("STEP 0: Clearing S3 upload folder...")
    logger.info("=" * 60)
    
    # Check if AWS credentials are configured
    aws_access_key = os.environ.get('UPLOAD_AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('UPLOAD_AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('UPLOAD_AWS_REGION', 'us-east-2')
    s3_bucket = os.environ.get('UPLOAD_S3_BUCKET')
    s3_prefix = os.environ.get('UPLOAD_S3_PREFIX', 'juportal-valid-decisions')
    
    if not all([aws_access_key, aws_secret_key, s3_bucket]):
        logger.warning("AWS credentials not configured - skipping S3 cleanup")
        return True  # Not an error, just skipped
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        logger.info(f"Target S3 location: s3://{s3_bucket}/{s3_prefix}/")
        
        # List all objects with the prefix
        try:
            response = s3_client.list_objects_v2(
                Bucket=s3_bucket,
                Prefix=s3_prefix + '/'
            )
            
            if 'Contents' in response:
                # Delete all objects
                objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
                
                if objects_to_delete:
                    logger.info(f"Found {len(objects_to_delete)} files to delete")
                    
                    # Delete objects in batches (max 1000 per request)
                    for i in range(0, len(objects_to_delete), 1000):
                        batch = objects_to_delete[i:i+1000]
                        s3_client.delete_objects(
                            Bucket=s3_bucket,
                            Delete={'Objects': batch}
                        )
                        logger.info(f"  Deleted batch of {len(batch)} files")
                    
                    logger.info(f"✅ Successfully cleared {len(objects_to_delete)} files from S3")
                else:
                    logger.info("No files found in S3 folder")
            else:
                logger.info("S3 folder is already empty")
            
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucket':
                logger.error(f"Bucket '{s3_bucket}' does not exist")
            else:
                logger.error(f"Error accessing S3: {e}")
            return False
            
    except ImportError:
        logger.error("boto3 is not installed. Please install it with: pip install boto3")
        return False
    except Exception as e:
        logger.error(f"Failed to clear S3 folder: {e}")
        return False


def run_url_scraper():
    """Run the URL scraper to discover new decision URLs (Phase 1)"""
    logger.info("=" * 60)
    logger.info("STEP 1: Discovering new decision URLs...")
    logger.info("=" * 60)
    
    try:
        # Run without capturing output so we see real-time progress
        result = subprocess.run(
            [sys.executable, "src/new_decisions_scraper.py"],
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Scraper failed with exit code {result.returncode}")
            return False
        
        # Check if new URLs were discovered
        session_file = Path("new_urls_session.txt")
        if session_file.exists():
            with open(session_file, 'r') as f:
                # Count lines minus header
                new_urls_count = sum(1 for _ in f) - 1
            if new_urls_count > 0:
                logger.info(f"✅ URL discovery completed - {new_urls_count} new URLs found")
            else:
                logger.info("✅ URL discovery completed - no new URLs found")
        else:
            logger.info("✅ URL discovery completed - no new URLs to process")
        
        return True
        
    except KeyboardInterrupt:
        logger.warning("Scraper interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Failed to run scraper: {e}")
        return False


def count_files_to_process():
    """Count how many .txt files need to be processed"""
    htmls_dir = Path("src/htmls")
    json_dir = Path("src/html_jsons")
    
    if not htmls_dir.exists():
        return 0
    
    txt_files = list(htmls_dir.glob("*.txt"))
    
    # Count how many don't have corresponding JSON yet
    new_files = 0
    for txt_file in txt_files:
        json_file = json_dir / f"{txt_file.stem}.json"
        if not json_file.exists():
            new_files += 1
    
    return new_files


def run_sequential_downloader():
    """Download HTML files sequentially with long timeouts for reliability"""
    logger.info("=" * 60)
    logger.info("STEP 2: Downloading HTML files sequentially...")
    logger.info("=" * 60)
    
    # Check if there are new URLs to download
    session_file = Path("new_urls_session.txt")
    if session_file.exists():
        with open(session_file, 'r') as f:
            # Count lines minus header
            new_urls_count = sum(1 for _ in f) - 1
        if new_urls_count == 0:
            logger.info("No new URLs to download - skipping HTML download step")
            return True
        logger.info(f"Will download {new_urls_count} new HTML files")
        logger.info("Note: This will take a long time but ensures maximum reliability")
    else:
        logger.info("No session file found - will run in full scan mode")
        logger.info("Note: This will check ALL URLs and may take a very long time")
    
    try:
        # Run sequential downloader with real-time output
        result = subprocess.run(
            [sys.executable, "src/sequential_html_downloader.py"],
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"HTML download failed with exit code {result.returncode}")
            # Check if there are failed downloads
            failed_downloads_path = Path("failed_downloads.txt")
            if failed_downloads_path.exists():
                logger.warning("⚠️  Some downloads failed. Check failed_downloads.txt for details")
            return False
        
        logger.info("✅ HTML downloads completed")
        
        # Check for failed downloads
        failed_downloads_path = Path("failed_downloads.txt")
        if failed_downloads_path.exists():
            with open(failed_downloads_path, 'r') as f:
                failed_count = sum(1 for _ in f) - 1  # Subtract header
            if failed_count > 0:
                logger.warning(f"⚠️  {failed_count} downloads failed. Check failed_downloads.txt")
        
        return True
        
    except KeyboardInterrupt:
        logger.warning("HTML download interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Failed to run HTML downloader: {e}")
        return False


def run_transformer():
    """Transform JSON files to final format with deduplication and validation"""
    logger.info("=" * 60)
    logger.info("STEP 4: Transforming JSONs to final format...")
    logger.info("=" * 60)
    
    # Check if there are JSON files to transform
    json_dir = Path("src/html_jsons")
    if not json_dir.exists():
        logger.info("No JSON directory found - skipping transformation")
        return True
    
    json_files = list(json_dir.glob("*.json"))
    if len(json_files) == 0:
        logger.info("No JSON files to transform")
        return True
    
    logger.info(f"Found {len(json_files)} JSON files to transform")
    
    try:
        # Run transformer with real-time output
        result = subprocess.run(
            [
                sys.executable,
                "src/transformer.py",
                "--input", "src/html_jsons",
                "--output", "src/output",
                "-v"  # Verbose output
            ],
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Transformation failed with exit code {result.returncode}")
            return False
        
        logger.info("✅ Transformation completed successfully")
        
        # Check for output files
        output_dir = Path("src/output")
        if output_dir.exists():
            output_files = list(output_dir.glob("*.json"))
            # Don't count summary files
            data_files = [f for f in output_files if f.name not in ['invalid_files.json', 'missing_dates.json']]
            logger.info(f"Generated {len(data_files)} transformed files")
            
            # Check for invalid files
            invalid_file = output_dir / "invalid_files.json"
            if invalid_file.exists():
                import json
                with open(invalid_file, 'r') as f:
                    invalid_list = json.load(f)
                logger.warning(f"⚠️  {len(invalid_list)} files have invalid language")
            
            # Check for missing dates
            missing_dates_file = output_dir / "missing_dates.json"
            if missing_dates_file.exists():
                import json
                with open(missing_dates_file, 'r') as f:
                    missing_data = json.load(f)
                logger.warning(f"⚠️  {missing_data['count']} files have missing/incomplete dates")
        
        return True
        
    except KeyboardInterrupt:
        logger.warning("Transformation interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Failed to run transformer: {e}")
        return False


def run_html_to_json():
    """Convert HTML (.txt files) to structured JSONs"""
    logger.info("=" * 60)
    logger.info("STEP 3: Converting HTML to JSON...")
    logger.info("=" * 60)
    
    # Count files to process
    new_files = count_files_to_process()
    if new_files == 0:
        logger.info("No new HTML files to process")
        return True
    
    logger.info(f"Found {new_files} new HTML files to process")
    
    try:
        # Run html-2-json.py with real-time output
        result = subprocess.run(
            [
                sys.executable,
                "src/html-2-json.py",
                "--input", "src/htmls",
                "--output", "src/html_jsons",
                "--skip-existing",  # Skip files that already have JSON
                "--use-mp",         # Use multiprocessing for speed
                "--workers", "4",   # Use 4 workers
                "-v"                # Verbose output
            ],
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"HTML to JSON conversion failed with exit code {result.returncode}")
            return False
        
        logger.info("✅ HTML to JSON conversion completed")
        return True
        
    except KeyboardInterrupt:
        logger.warning("HTML to JSON conversion interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Failed to run HTML to JSON converter: {e}")
        return False


def run_s3_upload():
    """Upload valid JSON files to S3 in compressed batches"""
    logger.info("=" * 60)
    logger.info("STEP 5: Uploading valid files to S3...")
    logger.info("=" * 60)
    
    # Check if output directory has files
    output_dir = Path("src/output")
    if not output_dir.exists():
        logger.info("No output directory found - skipping S3 upload")
        return True
    
    output_files = list(output_dir.glob("*.json"))
    # Don't count summary files
    data_files = [f for f in output_files if f.name not in ['invalid_files.json', 'missing_dates.json']]
    
    if len(data_files) == 0:
        logger.info("No output files to upload")
        return True
    
    logger.info(f"Found {len(data_files)} files to potentially upload")
    
    # Check if AWS credentials are configured
    from dotenv import load_dotenv
    import os
    load_dotenv()
    
    if not all([
        os.environ.get('UPLOAD_AWS_ACCESS_KEY_ID'),
        os.environ.get('UPLOAD_AWS_SECRET_ACCESS_KEY'),
        os.environ.get('UPLOAD_S3_BUCKET')
    ]):
        logger.warning("AWS credentials not configured - skipping S3 upload")
        logger.info("To enable S3 upload, set the following environment variables:")
        logger.info("  UPLOAD_AWS_ACCESS_KEY_ID")
        logger.info("  UPLOAD_AWS_SECRET_ACCESS_KEY")
        logger.info("  UPLOAD_S3_BUCKET")
        return True  # Not an error, just skipped
    
    try:
        # Run S3 upload script
        result = subprocess.run(
            [sys.executable, "src/upload_to_s3.py"],
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"S3 upload failed with exit code {result.returncode}")
            return False
        
        logger.info("✅ S3 upload completed successfully")
        return True
        
    except KeyboardInterrupt:
        logger.warning("S3 upload interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Failed to run S3 upload: {e}")
        return False


def show_statistics():
    """Show statistics about the pipeline run"""
    logger.info("=" * 60)
    logger.info("PIPELINE STATISTICS")
    logger.info("=" * 60)
    
    # Count files in each directory
    htmls_dir = Path("src/htmls")
    json_dir = Path("src/html_jsons")
    output_dir = Path("src/output")
    
    html_count = len(list(htmls_dir.glob("*.txt"))) if htmls_dir.exists() else 0
    json_count = len(list(json_dir.glob("*.json"))) if json_dir.exists() else 0
    
    logger.info(f"📁 HTML files in src/htmls: {html_count}")
    logger.info(f"📁 JSON files in src/html_jsons: {json_count}")
    
    # Count output files
    if output_dir.exists():
        output_files = list(output_dir.glob("*.json"))
        # Don't count summary files
        data_files = [f for f in output_files if f.name not in ['invalid_files.json', 'missing_dates.json']]
        logger.info(f"📁 Final output files in src/output: {len(data_files)}")
    else:
        logger.info(f"📁 Final output files in src/output: 0")
    
    # Check CSV
    csv_path = Path("urls_data/urls.csv")
    if csv_path.exists():
        with open(csv_path, 'r') as f:
            csv_lines = sum(1 for _ in f)
        logger.info(f"📁 Total URLs in CSV: {csv_lines}")


def main():
    """Main pipeline orchestrator"""
    start_time = datetime.now()
    
    logger.info("🚀 Starting JuPortal Pipeline")
    logger.info(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("Pipeline will:")
    logger.info("  0. Clear S3 upload folder")
    logger.info("  1. Discover new URLs")
    logger.info("  2. Download HTML files")
    logger.info("  3. Convert HTML to JSON")
    logger.info("  4. Transform to final format")
    logger.info("  5. Upload to S3")
    
    # Ensure directories exist
    Path("src/htmls").mkdir(parents=True, exist_ok=True)
    Path("src/html_jsons").mkdir(parents=True, exist_ok=True)
    Path("src/output").mkdir(parents=True, exist_ok=True)
    
    # Clear any leftover session file from previous run
    session_file = Path("new_urls_session.txt")
    if session_file.exists():
        logger.info("Clearing previous session file")
        session_file.unlink()
    
    # Run pipeline steps
    success = True
    
    # Step 0: Clear S3 folder (optional, continues even if it fails)
    if not clear_s3_folder():
        logger.warning("⚠️  S3 cleanup failed or skipped, continuing pipeline...")
    
    # Step 1: Discover URLs
    if not run_url_scraper():
        logger.error("❌ Pipeline failed at URL discovery step")
        success = False
    else:
        # Step 2: Download HTML files sequentially
        if not run_sequential_downloader():
            logger.error("❌ Pipeline failed at HTML download step")
            success = False
        else:
            # Step 3: Convert to JSON (only if downloads succeeded)
            if not run_html_to_json():
                logger.error("❌ Pipeline failed at HTML to JSON step")
                success = False
            else:
                # Step 4: Transform to final format (only if JSON conversion succeeded)
                if not run_transformer():
                    logger.error("❌ Pipeline failed at transformation step")
                    success = False
                else:
                    # Step 5: Upload to S3 (only if transformation succeeded)
                    if not run_s3_upload():
                        logger.error("❌ Pipeline failed at S3 upload step")
                        success = False  # Mark as failed but pipeline continues
    
    # Show statistics
    show_statistics()
    
    # Final status
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("=" * 60)
    if success:
        logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY!")
        # Clean up session file after successful completion
        if session_file.exists():
            session_file.unlink()
            logger.info("Session file cleaned up")
    else:
        logger.info("❌ PIPELINE COMPLETED WITH ERRORS")
        # Keep session file for debugging/retry if there were errors
        if session_file.exists():
            logger.info("Session file preserved for debugging/retry")
    
    logger.info(f"Duration: {duration}")
    logger.info(f"Ended at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())