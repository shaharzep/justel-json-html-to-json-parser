#!/usr/bin/env python3
"""
AWS S3 JSON Sync Script for Juportal Data
Downloads remaining JSON files from S3 bucket, avoiding duplicates.
"""

import os
import sys
import logging
import json
import time
from pathlib import Path
from typing import Set, List, Dict, Optional
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Add parent directory for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Load environment variables
load_dotenv()

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Error: boto3 is required. Install with: pip install boto3")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("Error: tqdm is required. Install with: pip install tqdm")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class S3JsonSyncer:
    """Syncs JSON files from S3 bucket to local directory."""
    
    def __init__(self, local_dir: str = "raw_jsons", max_workers: int = 10):
        """
        Initialize S3 syncer.
        
        Args:
            local_dir: Local directory to sync files to
            max_workers: Number of parallel download threads
        """
        self.local_dir = Path(local_dir)
        self.max_workers = max_workers
        
        # Get AWS configuration from environment
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        self.s3_prefix = os.getenv('S3_PREFIX', '')
        
        # Validate configuration
        self._validate_config()
        
        # Initialize S3 client
        self.s3_client = self._init_s3_client()
        
        # Ensure local directory exists
        self.local_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            'total_s3_files': 0,
            'local_files': 0,
            'files_to_download': 0,
            'downloaded': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def _validate_config(self):
        """Validate AWS configuration."""
        missing = []
        
        if not self.aws_access_key:
            missing.append('AWS_ACCESS_KEY_ID')
        if not self.aws_secret_key:
            missing.append('AWS_SECRET_ACCESS_KEY')
        if not self.bucket_name:
            missing.append('S3_BUCKET_NAME')
        
        if missing:
            logger.error(f"Missing required environment variables: {', '.join(missing)}")
            logger.error("Please check your .env file and ensure all AWS credentials are set.")
            sys.exit(1)
    
    def _init_s3_client(self):
        """Initialize and test S3 client."""
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )
            
            # Test connection
            s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
            return s3_client
            
        except NoCredentialsError:
            logger.error("AWS credentials not found or invalid")
            sys.exit(1)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"S3 bucket '{self.bucket_name}' not found")
            elif error_code == '403':
                logger.error(f"Access denied to S3 bucket '{self.bucket_name}'")
            else:
                logger.error(f"Error connecting to S3: {e}")
            sys.exit(1)
    
    def get_local_files(self) -> Set[str]:
        """Get set of existing local JSON filenames."""
        logger.info("Scanning local directory for existing files...")
        
        local_files = set()
        if self.local_dir.exists():
            for file_path in self.local_dir.glob("*.json"):
                local_files.add(file_path.name)
        
        self.stats['local_files'] = len(local_files)
        logger.info(f"Found {len(local_files)} existing local files")
        return local_files
    
    def get_s3_files(self) -> List[str]:
        """Get list of all JSON files in S3 bucket."""
        logger.info(f"Listing files in S3 bucket: {self.bucket_name}")
        if self.s3_prefix:
            logger.info(f"Using prefix: {self.s3_prefix}")
        
        s3_files = []
        paginator = self.s3_client.get_paginator('list_objects_v2')
        
        try:
            # Configure pagination parameters
            page_config = {'Bucket': self.bucket_name}
            if self.s3_prefix:
                page_config['Prefix'] = self.s3_prefix
            
            # Use tqdm for progress on listing
            with tqdm(desc="Listing S3 files", unit="pages") as pbar:
                for page in paginator.paginate(**page_config):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            key = obj['Key']
                            # Only include JSON files
                            if key.endswith('.json'):
                                # Extract just the filename
                                filename = Path(key).name
                                s3_files.append(filename)
                    pbar.update(1)
            
            self.stats['total_s3_files'] = len(s3_files)
            logger.info(f"Found {len(s3_files)} JSON files in S3")
            return s3_files
            
        except ClientError as e:
            logger.error(f"Error listing S3 files: {e}")
            sys.exit(1)
    
    def download_file(self, filename: str, retries: int = 3) -> bool:
        """
        Download a single file from S3.
        
        Args:
            filename: Name of the file to download
            retries: Number of retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        # Construct S3 key, handling trailing slashes properly
        if self.s3_prefix:
            s3_key = f"{self.s3_prefix.rstrip('/')}/{filename}"
        else:
            s3_key = filename
        local_path = self.local_dir / filename
        
        for attempt in range(retries + 1):
            try:
                self.s3_client.download_file(
                    self.bucket_name,
                    s3_key,
                    str(local_path)
                )
                return True
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    logger.warning(f"File not found in S3: {s3_key}")
                    return False
                elif attempt < retries:
                    logger.warning(f"Download attempt {attempt + 1} failed for {filename}: {e}")
                    time.sleep(1)  # Brief delay before retry
                else:
                    logger.error(f"Failed to download {filename} after {retries + 1} attempts: {e}")
                    return False
            except Exception as e:
                if attempt < retries:
                    logger.warning(f"Download attempt {attempt + 1} failed for {filename}: {e}")
                    time.sleep(1)
                else:
                    logger.error(f"Failed to download {filename} after {retries + 1} attempts: {e}")
                    return False
        
        return False
    
    def sync_files(self, dry_run: bool = False):
        """
        Sync files from S3 to local directory.
        
        Args:
            dry_run: If True, only show what would be downloaded
        """
        self.stats['start_time'] = time.time()
        
        logger.info("Starting S3 sync process...")
        
        # Get file lists
        local_files = self.get_local_files()
        s3_files = self.get_s3_files()
        
        # Calculate files to download
        files_to_download = [f for f in s3_files if f not in local_files]
        self.stats['files_to_download'] = len(files_to_download)
        
        logger.info(f"Files to download: {len(files_to_download)}")
        logger.info(f"Files already local: {len(local_files)}")
        
        if not files_to_download:
            logger.info("All files are already downloaded!")
            return
        
        if dry_run:
            logger.info("DRY RUN - Files that would be downloaded:")
            for filename in files_to_download[:10]:  # Show first 10
                logger.info(f"  {filename}")
            if len(files_to_download) > 10:
                logger.info(f"  ... and {len(files_to_download) - 10} more files")
            return
        
        # Download files in parallel
        logger.info(f"Starting download of {len(files_to_download)} files with {self.max_workers} workers...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_filename = {
                executor.submit(self.download_file, filename): filename
                for filename in files_to_download
            }
            
            # Process results with progress bar
            with tqdm(total=len(files_to_download), desc="Downloading", unit="files") as pbar:
                for future in as_completed(future_to_filename):
                    filename = future_to_filename[future]
                    
                    try:
                        success = future.result()
                        if success:
                            self.stats['downloaded'] += 1
                        else:
                            self.stats['errors'] += 1
                    except Exception as e:
                        logger.error(f"Unexpected error downloading {filename}: {e}")
                        self.stats['errors'] += 1
                    
                    pbar.update(1)
                    pbar.set_postfix({
                        'Downloaded': self.stats['downloaded'],
                        'Errors': self.stats['errors']
                    })
        
        self.stats['end_time'] = time.time()
        self._print_summary()
    
    def _print_summary(self):
        """Print download summary statistics."""
        duration = self.stats['end_time'] - self.stats['start_time']
        
        logger.info("=" * 60)
        logger.info("SYNC COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total S3 files: {self.stats['total_s3_files']:,}")
        logger.info(f"Local files (before): {self.stats['local_files']:,}")
        logger.info(f"Files to download: {self.stats['files_to_download']:,}")
        logger.info(f"Successfully downloaded: {self.stats['downloaded']:,}")
        logger.info(f"Errors: {self.stats['errors']:,}")
        logger.info(f"Duration: {duration:.1f}s")
        
        if self.stats['downloaded'] > 0:
            rate = self.stats['downloaded'] / duration
            logger.info(f"Download rate: {rate:.1f} files/second")
        
        final_count = self.stats['local_files'] + self.stats['downloaded']
        progress = (final_count / self.stats['total_s3_files']) * 100 if self.stats['total_s3_files'] > 0 else 0
        logger.info(f"Total local files: {final_count:,} ({progress:.1f}% of S3 files)")
        logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync JSON files from S3 bucket to local directory"
    )
    parser.add_argument(
        '--local-dir', '-d',
        default='raw_jsons',
        help='Local directory to sync files to (default: raw_jsons)'
    )
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=10,
        help='Number of parallel download workers (default: 10)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be downloaded without actually downloading'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize syncer
    syncer = S3JsonSyncer(
        local_dir=args.local_dir,
        max_workers=args.workers
    )
    
    try:
        # Start sync
        syncer.sync_files(dry_run=args.dry_run)
        
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()