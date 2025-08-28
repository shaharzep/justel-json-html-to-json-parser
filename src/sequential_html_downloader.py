#!/usr/bin/env python3
"""
Sequential HTML Downloader for JuPortal Decisions (Phase 2)
Downloads HTML content for URLs in the CSV file one by one with very long timeouts.
Designed for reliability over speed - perfect for unattended server execution.
"""

import csv
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Set, Optional

from playwright.sync_api import sync_playwright, Page, Browser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
URLS_CSV_PATH = Path(__file__).parent.parent / "urls_data" / "urls.csv"
HTMLS_DIR = Path(__file__).parent / "htmls"
FAILED_DOWNLOADS_PATH = Path(__file__).parent.parent / "failed_downloads.txt"
NEW_URLS_SESSION_PATH = Path(__file__).parent.parent / "new_urls_session.txt"

# Configuration
PAGE_LOAD_TIMEOUT = 120000  # 120 seconds for page load
CONTENT_WAIT_TIME = 30000   # 30 seconds additional wait for content
MAX_RETRIES = 5              # Number of retries per URL
RETRY_BACKOFF_BASE = 5       # Base seconds for exponential backoff
PROGRESS_SAVE_INTERVAL = 10  # Save progress every N files


def get_urls_from_session_file() -> Optional[List[Tuple[str, str, str]]]:
    """
    Read URLs from the session file created by new_decisions_scraper.
    Returns list of (url, ecli_id, date) tuples or None if file doesn't exist.
    """
    if not NEW_URLS_SESSION_PATH.exists():
        return None
    
    urls = []
    with open(NEW_URLS_SESSION_PATH, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        # Skip header
        next(reader, None)
        for row in reader:
            if len(row) >= 3:
                urls.append((row[0], row[1], row[2]))
            elif len(row) >= 2:
                urls.append((row[0], row[1], ""))
    
    logger.info(f"Found {len(urls)} new URLs in session file")
    return urls


def get_urls_from_csv() -> List[Tuple[str, str, str]]:
    """
    Read all URLs from the CSV file.
    Returns list of (url, ecli_id, date) tuples.
    """
    urls = []
    
    if not URLS_CSV_PATH.exists():
        logger.error(f"CSV file not found: {URLS_CSV_PATH}")
        return urls
    
    with open(URLS_CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                urls.append((row[0], row[1], row[2]))
            elif len(row) >= 2:
                urls.append((row[0], row[1], ""))  # Handle missing date
    
    logger.info(f"Found {len(urls)} total URLs in CSV")
    return urls


def get_existing_htmls() -> Set[str]:
    """
    Get set of already downloaded HTML files (without extension).
    """
    if not HTMLS_DIR.exists():
        return set()
    
    existing = set()
    for file in HTMLS_DIR.glob("*.txt"):
        # Remove .txt extension to get the base filename
        existing.add(file.stem)
    
    return existing


def get_pending_downloads() -> List[Tuple[str, str, str]]:
    """
    Get list of URLs that need to be downloaded.
    Prioritizes session file (new URLs only) over full CSV scan.
    Returns list of (url, ecli_id, date) tuples.
    """
    # First, try to get URLs from session file (new URLs only)
    urls = get_urls_from_session_file()
    
    if urls is not None:
        logger.info("Using new URLs from session file")
        # For session file URLs, we download all of them (they're all new)
        # But still check if they already exist to be safe
        existing = get_existing_htmls()
        pending = []
        
        for url, ecli_id, date in urls:
            filename = ecli_id.replace('-', '_')
            if filename not in existing:
                pending.append((url, ecli_id, date))
        
        logger.info(f"Found {len(pending)} new URLs to download from session")
        return pending
    
    # Fall back to old behavior: scan all CSV and compare with existing files
    logger.info("No session file found, falling back to full CSV scan")
    urls = get_urls_from_csv()
    existing = get_existing_htmls()
    
    pending = []
    for url, ecli_id, date in urls:
        # Generate filename from ecli_id
        # ecli_id format: ECLI_BE_XXXX_2024_123456-FR
        filename = ecli_id.replace('-', '_')
        
        if filename not in existing:
            pending.append((url, ecli_id, date))
    
    logger.info(f"Found {len(pending)} URLs that need downloading")
    return pending


def log_failed_download(url: str, ecli_id: str, error_msg: str):
    """
    Log failed download to a file for later reprocessing.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create or append to failed downloads file
    with open(FAILED_DOWNLOADS_PATH, 'a', encoding='utf-8') as f:
        # Write header if file is new
        if f.tell() == 0:
            f.write("timestamp,url,ecli_id,error\n")
        
        # Write failed download info
        f.write(f'"{timestamp}","{url}","{ecli_id}","{error_msg}"\n')
    
    logger.warning(f"Logged failed download: {ecli_id}")


def download_html_with_browser(page: Page, url: str, ecli_id: str) -> Tuple[bool, str]:
    """
    Download HTML content from a URL using Playwright browser.
    Returns (success, error_message/content).
    """
    filename = ecli_id.replace('-', '_') + '.txt'
    filepath = HTMLS_DIR / filename
    
    # Skip if already exists
    if filepath.exists():
        return True, "Already exists"
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"  Attempt {attempt + 1}/{MAX_RETRIES}: Navigating to {url}")
            
            # Navigate with very long timeout
            page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            
            # Wait for network to be idle
            logger.debug(f"  Waiting for network idle...")
            page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT)
            
            # Additional wait for dynamic content
            logger.debug(f"  Waiting {CONTENT_WAIT_TIME/1000}s for content stabilization...")
            page.wait_for_timeout(CONTENT_WAIT_TIME)
            
            # Get the full HTML content
            html_content = page.content()
            
            # Verify we got actual content (not error page)
            if len(html_content) < 1000:
                error_msg = f"Content too short ({len(html_content)} bytes)"
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(f"  {error_msg}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    return False, error_msg
            
            # Save to file
            filepath.write_text(html_content, encoding='utf-8')
            logger.info(f"  ✓ Saved {len(html_content)} bytes to {filename}")
            return True, html_content
            
        except Exception as e:
            error_msg = str(e)
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(f"  Error: {error_msg[:100]}...")
                logger.info(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"  ✗ Failed after {MAX_RETRIES} attempts: {error_msg[:200]}...")
                return False, error_msg
    
    return False, "Max retries exceeded"


def estimate_remaining_time(processed: int, total: int, elapsed_seconds: float) -> str:
    """
    Estimate remaining time based on current progress.
    """
    if processed == 0:
        return "calculating..."
    
    avg_time_per_item = elapsed_seconds / processed
    remaining_items = total - processed
    remaining_seconds = remaining_items * avg_time_per_item
    
    # Convert to human-readable format
    hours = int(remaining_seconds // 3600)
    minutes = int((remaining_seconds % 3600) // 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def main():
    """Main sequential download function."""
    logger.info("Starting Sequential HTML Downloader")
    logger.info("=" * 60)
    logger.info("Configuration:")
    logger.info(f"  Page load timeout: {PAGE_LOAD_TIMEOUT/1000}s")
    logger.info(f"  Content wait time: {CONTENT_WAIT_TIME/1000}s")
    logger.info(f"  Max retries: {MAX_RETRIES}")
    logger.info(f"  Failed downloads log: {FAILED_DOWNLOADS_PATH}")
    
    # Check if we're running in session mode
    if NEW_URLS_SESSION_PATH.exists():
        logger.info(f"  Mode: SESSION (processing new URLs only)")
        logger.info(f"  Session file: {NEW_URLS_SESSION_PATH}")
    else:
        logger.info(f"  Mode: FULL SCAN (checking all CSV entries)")
    
    logger.info("=" * 60)
    
    # Ensure htmls directory exists
    HTMLS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get list of pending downloads
    pending = get_pending_downloads()
    
    if not pending:
        logger.info("No URLs need downloading. All HTML files are up to date!")
        return
    
    logger.info(f"Will download {len(pending)} HTML files sequentially")
    logger.info("This will take a long time but ensures maximum reliability")
    
    # Start Playwright
    with sync_playwright() as p:
        # Launch browser in headless mode
        headless = os.environ.get('BROWSER_HEADLESS', 'true').lower() == 'true'
        
        browser = p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--lang=fr-FR',
                '--accept-lang=fr-FR,fr'
            ]
        )
        
        logger.info(f"Browser launched (headless={headless})")
        
        # Create context and page
        context = browser.new_context(
            locale='fr-FR',
            timezone_id='Europe/Brussels',
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        
        # Statistics
        successful = 0
        failed = 0
        start_time = time.time()
        
        try:
            for i, (url, ecli_id, date) in enumerate(pending, 1):
                # Progress reporting
                elapsed = time.time() - start_time
                eta = estimate_remaining_time(i - 1, len(pending), elapsed)
                logger.info(f"\n[{i}/{len(pending)}] Processing: {ecli_id}")
                logger.info(f"  Progress: {i/len(pending)*100:.1f}% | ETA: {eta}")
                
                # Download the HTML
                success, result = download_html_with_browser(page, url, ecli_id)
                
                if success:
                    successful += 1
                else:
                    failed += 1
                    log_failed_download(url, ecli_id, result)
                
                # Save progress periodically
                if i % PROGRESS_SAVE_INTERVAL == 0:
                    logger.info(f"\n--- Progress Update ---")
                    logger.info(f"  Processed: {i}/{len(pending)}")
                    logger.info(f"  Successful: {successful}")
                    logger.info(f"  Failed: {failed}")
                    logger.info(f"  Success rate: {successful/i*100:.1f}%")
                    logger.info(f"  Time elapsed: {timedelta(seconds=int(elapsed))}")
                
                # Small delay between requests to be polite
                if i < len(pending):  # Don't wait after last item
                    time.sleep(2)
                    
        except KeyboardInterrupt:
            logger.warning("\nDownload interrupted by user")
        except Exception as e:
            logger.error(f"\nUnexpected error: {e}")
        finally:
            browser.close()
            
            # Final statistics
            total_time = time.time() - start_time
            logger.info("\n" + "=" * 60)
            logger.info("DOWNLOAD SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total processed: {successful + failed}")
            logger.info(f"Successful: {successful}")
            logger.info(f"Failed: {failed}")
            if (successful + failed) > 0:
                logger.info(f"Success rate: {successful/(successful+failed)*100:.1f}%")
            logger.info(f"Total time: {timedelta(seconds=int(total_time))}")
            if successful > 0:
                logger.info(f"Average time per file: {total_time/successful:.1f}s")
            
            if failed > 0:
                logger.info(f"\n⚠️  {failed} downloads failed.")
                logger.info(f"Failed downloads logged to: {FAILED_DOWNLOADS_PATH}")
                logger.info("You can reprocess these later by reading the failed_downloads.txt file")
            
            logger.info("=" * 60)


if __name__ == "__main__":
    main()